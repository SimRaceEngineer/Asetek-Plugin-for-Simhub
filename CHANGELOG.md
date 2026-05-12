# Asetek Control — Changelog

> All notable changes to this plugin will be documented in this file.

---

## v1.3.4 — Recovery overhaul & live in-game tuning (May 12, 2026)

### Changed
- **High Torque restore now uses a soft drive cold-boot** instead of the
  challenge/answer handshake on register 6071. The new path sends
  `goto_test_mode + restart_drive` (no SMP register writes), which triggers
  the firmware's automatic High Torque enable at cold boot. Result : a
  reliable, fast, non-destructive recovery that works consistently after
  any RaceHub session, on every base model.
- **Recovery section in Debug tab split in two** :
  - **"Standard procedure after using RaceHub"** is now visible directly,
    with a clean step-by-step procedure and the **Restore High Torque**
    button as the primary action. No more scary disclaimer for a normal
    operation.
  - **"Advanced Recovery"** stays collapsed behind an expander, only for
    confirmed SMP corruption (when the Firmware PEAK in Dump Diagnostic is
    below the model's factory spec). The Reset SMP Registers button is
    now gated behind an explicit confirmation checkbox to prevent misuse.
- **`Reconnect` on Overview tab** also switched to the new soft-restart
  path internally, so the one-click recovery is now bulletproof.

### Added
- **In-game live tuning for HF Limit and Torque Accel Limit.** Two new
  control bindings in the *Controls (Beta)* tab, *Torque Shaping* section :
  - `HF Limit +/- 100 Hz`
  - `Torque Accel Limit +/- 0.1 Nm/ms`

  Bind them to wheel / button-box keys to adjust those two parameters
  **on the fly while driving**, with the same step values as the FFB
  Settings sliders. When you come back to the plugin, the sliders show
  the values you've dialled in live ; one **Save to Wheelbase** click
  persists the perfect setup. RAM-only — no flash write during the
  tuning session, so SMP_PEAK stays untouched.

### Fixed
- Pre-flight check in High Torque restore now cross-verifies the
  challenge probe against the HT status bit. Avoids skipping the
  recovery when the firmware reports inconsistent state.

---

## v1.3.3 — HF Limit slider fix (May 8, 2026)

### Fixed
- **HF Limit slider jumping back to 100 Hz after Save.** Three root causes:
  1. Default `ioni_lpf` was 10 (invalid — valid range is 0 or 100-4700).
     The WPF slider clamped it to its minimum of 100, producing a phantom
     "100 Hz" that the user never chose. Default is now 0 (No Limit).
  2. Values 1-99 from old profiles/defaults were treated as valid Hz.
     Now any value below 100 maps to "No Limit" (slider position 4800),
     matching the firmware semantics where 0 = unfiltered.
  3. "Save to Wheelbase" did not sync the new values back into the active
     profile. On next auto-match or startup, the stale profile overwrote
     the cache with the old HF Limit. Now auto-saves to the active profile
     after a successful flash write.

---

## v1.3.2 — La Prima MAX_OUTPUT_POWER fix (May 8, 2026)

### Fixed
- **La Prima stock PSU stuck at 7 Nm.** `ResetWheelbaseTorqueLimits` and
  `RunDiagnosticDump` always wrote/expected `MAX_OUTPUT_POWER = 400`
  (the HiPSU value) regardless of the `LaPrimaHighPowerPsu` flag.
  On a stock PSU La Prima, the firmware sees 400W configured but the PSU
  can't deliver it, so it failsafes the motor to ~7 Nm.
  Now respects the PSU flag: stock La Prima writes 220 (confirmed from
  RaceHub cold-boot diagnostic), HiPSU writes 400.
- Diagnostic dump header and expected-value comparisons now also reflect
  the PSU mode for peak Nm and max power.

---

## v1.3.1 — Game detection via DataCorePlugin.CurrentGame (May 6, 2026)

### Changed
- Auto-match now polls `DataCorePlugin.CurrentGame` every 2s via a background
  timer — profile loads as soon as SimHub detects a sim, even before telemetry
  flows. No longer depends on `DataUpdate` for game detection.
- Removed redundant properties `Asetek.Profile.ActiveGame` and
  `Asetek.Profile.DetectedGame` — `DataCorePlugin.CurrentGame` already
  exists in SimHub and is the single source of truth.
- Timer directly loads the ★ per-game favourite when a game is detected,
  bypassing `FindMatchingProfile` which couldn't match starred profiles
  that have car/track tags when called without telemetry context.
- New actions `Asetek.Profile.GameCycle.Next` / `.Prev` — cycle only
  through profiles tagged with the currently detected game.
- Controls tab renamed to "Controls (Beta)" and now includes a PROFILES
  section with all 4 cycle bindings (all / game-filtered).
- Auto-reconnect: timer verifies HID handle every 2s via
  `HidD_GetPreparsedData` probe — detects stale handles after SimHub
  game switches and reconnects automatically.
- UI auto-refresh: profile list + game pill auto-updates when the active
  profile or detected game changes (1s poll in the settings control).
- Game-change reconnect: after auto-reconnect on game switch, shows a
  warning banner prompting the user to press the physical power button
  (the LED blinks in standby — no HID command can control it). Banner
  auto-dismisses when the base reports HT ON (button pressed).
  Removed all prior wake attempts (`re_enable_torque_mode`, `activate_profile`,
  forced HT handshake) — none could control the hardware LED.
- Heartbeat: `request_status` ping every 2s detects power-off even when
  USB remains connected.
- `WriteWheelbase` marks `_wheelbaseConnected = false` when all write
  methods fail (was only on exception).

### Fixed
- **CRITICAL: SMP_TORQUELIMIT_PEAK degradation on every save_to_flash**.
  The firmware rescales PEAK by `main_gain/100` whenever addr 3 (main_gain) is
  included in a setprofiledata batch. Flash batches now ALWAYS skip addr 3 —
  main_gain is only applied at runtime via SetOverallForce (single-addr, RAM only).
  Previously: 27 Nm → 22.9 → 19.5 → … after each Save to Wheelbase click.
- HF Limit slider: restored correct left-to-right order (100 Hz → 4700 Hz → No Limit).
  Was inverted (No Limit at left) due to `IsDirectionReversed`. Now uses 4800↔0 remapping.
- Physical button LED blinks after auto-reconnect on game change —
  now shows a clear banner instead of silently failing HT handshake attempts.
- Profile creation moved from Overview to FFB Settings (single "+ Create" entry
  point). "Save to profile" combo is now editable — type a new name to create,
  pick an existing one to overwrite.
- FFB Settings sliders now live-sync with the parameter cache every second
  (guarded by `_refreshingSliders` to prevent false dirty state). Previously
  sliders retained stale values after profile auto-match or game switch.

---

## v1.3.0 — Major UI restructure + recovery polish (May 6, 2026)

The release rolls up everything from v1.0.20 → v1.0.28 dev iterations into a
single clean 1.3.0 milestone. Headlines :

- One-click Reconnect that does Connect + Restore High Torque + Apply FFB
  profile — covers the full RaceHub-coexistence recovery path in a single
  button click on Overview.
- Profile list redesigned with clickable Game-tag pills, default-profile
  auto-load on startup, and the per-row Save / Load clutter removed.
- New Detection card on Overview shows the wheelbase model, factory peak,
  base slew ceiling, and live HT bit at a glance.
- New Debug tab (right-aligned) hosts the firmware diagnostic dump,
  Dump / Cold-Start Diag buttons, and a collapsed Recovery Actions
  expander with a step-by-step procedure for the rare cases where the
  bare Reconnect doesn't suffice.
- Save controls (SAVE TO WHEELBASE, Save to profile, Quick saves) now sit
  *above* the slider sections so the user always sees them without
  scrolling.
- Re-center Wheel moved to the Overview bottom row alongside Reconnect /
  Disconnect.
- 5 new SimHub properties for active profile + active game/car class so
  dashboards and wheel-button bindings can reflect the loaded preset
  (`Asetek.Profile.ActiveName`, `ActiveIndex`, `Count`, `ActiveGame`,
  `ActiveCarClass`).

Detailed notes (carry-over from the v1.0.28-beta development snapshot) :

### Added — UI restructure for clarity

- **Overview / Detection card.** New read-out at the top of the Overview tab
  showing the wheelbase model, factory peak torque, base slew ceiling, the
  active Overall Force / slew rate (live), and the High Torque mode bit.
  Replaces the raw firmware diagnostic dump that used to clutter the page.
- **Debug tab (right-aligned, separated from regular tabs).** Hosts the
  firmware diagnostic dump (`_diagText`), the Dump Diagnostic and Cold-Start
  Diag buttons, and a collapsed "Recovery actions" expander with a strong
  disclaimer + step-by-step procedure for the rare case where Reset Torque
  Limits + Restore High Torque are needed.
- **Profile list — pills filter.** The Overview profile list now starts with
  a row of clickable pills, one per Game tag (case-insensitive merge of
  variants like "iRacing" / "IRacing"), plus an "All" pill. Click a pill to
  filter ; the active pill is highlighted in orange. Untagged profiles
  always appear under the rightmost "Untagged" pill, never silently dropped.
- **Per-row Save / Load buttons removed.** Clicking the profile name loads
  the profile (existing behaviour from v1.0.3) ; the FFB Settings tab
  "APPLY & SAVE" button + "Save current sliders to..." dropdown handle
  writing back. Per-row buttons were redundant clutter.
- **★ Default profile auto-loaded at SimHub startup.** Setting a profile as
  default via the star icon now actually loads it on plugin Init (was
  decorative-only before). Falls back to the runtime cache if the default
  profile name no longer matches any saved profile.
- **Tag button has a usable fallback.** When no game is currently running
  (so SimHub's `data.GameName` is empty), clicking Tag opens the inline
  Game / CarClass editor instead of silently writing a status message to
  the diagnostic text block.

### Added — SimHub properties / actions

- **Active profile properties** for dashboards :
  - `Asetek.Profile.ActiveName` (string)
  - `Asetek.Profile.ActiveIndex` (1-based, alphabetical order)
  - `Asetek.Profile.Count`
  - `Asetek.Profile.ActiveGame`
  - `Asetek.Profile.ActiveCarClass`

  Pair these with the existing actions `Asetek.Profile.Cycle.Next` /
  `.Cycle.Prev` and `Asetek.Profile.LoadSlot.0..N` to bind in-wheel buttons
  for "next profile" / "GT3 setup" / "wet-track setup" without leaving the
  cockpit.

### Changed — Reconnect / RaceHub coexistence

- **One-click Reconnect** rolls Connect + Restore High Torque +
  Apply-FFB-profile into a single sequence. After closing RaceHub, this
  recovers HT bit + re-pushes the user's saved FFB profile in one click.
  No Reset Torque Limits in the chain — that path is reserved for explicit
  manual use because of the firmware quirk described in v1.0.27 notes.
- **High Torque banner is RaceHub-aware.** When RaceHub is running
  alongside the plugin, the warning explains that Restore High Torque is
  blocked (the challenge / answer handshake conflicts with RaceHub's own
  polling) and points the user to the Disconnect button to hand the
  wheelbase off to RaceHub instead. RaceHub re-enables HT on its own.
- **HF Limit slider direction.** Reverted v1.0.22's 100–4800 remap. The
  slider stays at 0–4700 with `IsDirectionReversed = true`, matching the
  v1.0.21 ordering — "No Limit" on the right, 100 Hz on the left.

### Fixed

- **Smart Tune slew-rate "Reduce" suggestion stops at the right floor.**
  v1.0.21 introduced a smoothed/raw ratio guard ; v1.0.28 adds two more
  stop conditions (peak headroom against `DeltaMaxNm`, absolute 2.0 Nm/ms
  floor) so the recommendation no longer descends asymptotically when the
  FFB is already at the useful minimum for the surface.
- **Smart Tune Increase logic mirrors Reduce** with three independent
  triggers (peaks clipping, detail loss, P95 clipping) and confidence
  rating reflecting which one fired.
- **LogAnalyzer reads slew rate from the CSV log, not the live cache.**
  The cache resets to firmware defaults at every SimHub restart, so
  reading `GetParam(slew_rate_limit)` after a fresh boot returned 9.4
  even when the slider showed the user's tuned value. Now uses
  `s.HwSlewNmPerMs` from the recorded CSV — what the user was actually
  feeling during the lap.
- **Detection card reads from the runtime cache, not SimHub properties.**
  Properties only update during DataUpdate ticks (game running) ; reading
  the cache gives a fresh value at startup / in the menu / paused.
- **HT bit force-refresh on Detection panel.** If `HealthHighTorqueOn`
  is null when the panel renders, the panel triggers a synchronous
  `RefreshHealthSnapshot()` instead of waiting up to 5 s for the next
  scheduled tick.
- **Inline Rename / Edit Tag dialogs insert below the pills row.**
  Inserting at `_profileListPanel.Children.Insert(0, …)` was pushing the
  pills below the dialog and visually swapping the active filter view.
  Now insert at index 1 when the first child is the pills `WrapPanel`.
- **Live Auto-tune AutoTune fixes (carry-over from v1.0.20).** `IoniLpf`
  values now in Hz (was indices 0–11 read as Hz on the slider, producing
  near-total filtering). "AO" suggestions write to `latency_comp_factor`
  (was wrongly writing to `ioni_damping`). `AutoTuneRefine` HF nudge is
  ±500 Hz with a clean 0 ↔ 3000 Hz transition across the No Limit edge.
  Slew-rate suggestions clamped to `MaxSlewRateForCurrentBase × 1000`.

### Notes

- Asetek themselves confirmed (Discord, 24 Mar 2026) that their "iRacing
  360Hz mode" is a software 60Hz→360Hz interpolation with a double buffer,
  ~16.7 ms slower than the default DirectInput FFB. The plugin's
  `360 Hz Compatibility Mode` toggle activates exactly that path. Future
  releases will document this trade-off explicitly rather than presenting
  it as a pure upgrade.

---

## v1.0.27-beta — One-click full recovery on Reconnect (May 5, 2026)

(Note : kept for changelog continuity ; the one-click flow is now the
permanent default in v1.0.28.)



### Changed

- **New "Debug" tab as the last tab.** Hosts the firmware diagnostic
  dump (`_diagText`) that used to take up the upper half of the Overview
  tab. The dump is still populated automatically at startup and after
  every Reconnect, and by the manual Dump Diagnostic / Cold-Start Diag
  buttons — but it's now tucked away in its own tab so the Overview
  stays focused on device status and live torque feedback.
- **Overview tab gains a "Live Read-out" card** in place of the dump,
  refreshed every second :
  - Peak / Max torque (Nm)
  - Utilisation % and clipping flag
  - Roughness raw and post-slew-clamp (Nm stddev)
  - Hardware and Software slew rates (Nm/ms)

  This is the unambiguous "what does the wheelbase actually deliver
  right now?" view — values come from live `Asetek.FFB.*` properties,
  independent of the saved profile shown by the FFB Settings sliders.
- **FFB Settings tab unchanged** — the Advanced FFB Diagnostic expander
  (Software Slew Limit, FFB Log, Smart Tune, Live Auto-tune) stays
  exactly where it was.

---

## v1.0.27-beta — One-click full recovery on Reconnect (May 5, 2026)

### Changed

- **The "Reconnect" button is now a one-click full recovery.** Whatever
  state the wheelbase is in — capped at the safe torque, High Torque
  toggled off, FFB profile overwritten by RaceHub — clicking Reconnect
  performs the full sequence in one shot :
  1. Refreshes the HID handle (idempotent if already connected).
  2. Restores SMP_TORQUELIMIT_PEAK / CONT / MAX_OUTPUT_POWER to the
     detected base's factory peak (27 Nm Invicta, 18 Nm Forte, 12 / 16 Nm
     La Prima depending on PSU).
  3. Re-engages HIGH_TORQUE_MODE_BIT via the firmware challenge / answer.
  4. Re-applies the user's saved FFB profile to RAM.
  No flash writes — everything is runtime-only, so power-cycle if you want
  to start fresh from the firmware's persistent state.
- The separate **"Reset Torque Limits"** and **"Restore High Torque"**
  buttons are removed from the UI — Reconnect now covers both. The
  underlying API methods (`ResetWheelbaseTorqueLimits`,
  `RestoreHighTorqueMode`) remain on `AsetekManager` for SimHub action
  bindings or surgical use.
- The Reconnect button in the RaceHub-closed banner uses the same
  recovery path, so closing RaceHub mid-session and clicking the inline
  Reconnect always brings you back to a known-good full-torque state.

---

## v1.0.26-beta — Smart Tune reads slew from log, not stale cache (May 5, 2026)

### Fixed

- **Smart Tune was reading the current slew rate from the live cache,
  which is reset to firmware defaults (9.4 Nm/ms on Invicta) at every
  SimHub restart.** Applied AutoTune / Live Auto-tune values are runtime
  only until the user clicks Apply & Save — but Smart Tune was using
  `GetParam(slew_rate_limit)` to know what to compare against, which
  returned 9.4 even when the slider visibly showed 3.9. Result: the
  analyzer would propose reducing 9.4 → 7.5 immediately after a restart,
  forgetting the user had already converged at 3.9.
- The CSV log captures `hw_slew_nm_per_ms` per sample; that's the actual
  hardware slew rate at the time of recording. `LogAnalyzer` now reads
  `s.HwSlewNmPerMs` as the current value (falling back to cache only if
  the log didn't capture it). The recommendations now reference what the
  user was actually feeling during the lap, not the post-restart default.

---

## v1.0.25-beta — Slew-rate Increase logic mirrors Reduce (May 5, 2026)

### Changed

- **Smart Tune "↑ Increase" suggestion now uses the same three-factor
  framework as Reduce.** The previous Increase rule only fired when P95
  reached 90 % of the budget — a single statistical trigger that ignored
  peak clipping (kerbs) and detail loss. The new logic surfaces an
  Increase if any of these holds :
  - **Peaks clipping** : `DeltaMaxNm > maxBudgetAtCurrent` — the worst
    transients are getting flattened. Strongest signal (confidence 3).
  - **Detail loss** : smoothed/raw ratio < 0.85 — the slew is absorbing
    real signal even on typical content, not just spikes.
  - **P95 clipping** : preserved from before, weakest of the three.
- The reco card cites which trigger fired so you can see *why* the
  algorithm thinks you have headroom to go up. Symmetric with the v1.0.24
  Reduce / Hold treatment.

---

## v1.0.24-beta — Slew-rate "Reduce" stop conditions (May 5, 2026)

### Fixed

- **Smart Tune kept proposing slew rate reductions even when the FFB was
  already good.** The v1.0.21 detail-loss guard checked the smoothed/raw
  ratio, but on smooth-ish surfaces that ratio stays at 1.00 down to very
  low slew values — by which point the wheel has gone mushy. Three stop
  conditions now gate every "↓ Reduce" suggestion :
  - **Peak headroom :** the proposed budget must stay > 1.5 × `DeltaMaxNm`
    (the worst transient ever observed in the log). P95 hides kerb hits ;
    DeltaMaxNm catches them. Without this, the recommendation could push
    slew below what kerbs need to keep their edge.
  - **Detail loss :** smoothed/raw ratio must stay above 0.85 (unchanged
    from v1.0.21).
  - **Absolute floor :** current slew must be > 2.0 Nm/ms. Below that,
    HFFB starts feeling lifeless on bumpy tracks regardless of what the
    statistics say (Jerome + Chris reproduced this at 0.9 Nm/ms on
    Nordschleife).
- When any of those conditions trigger, Smart Tune now emits a "→ Hold"
  info card explaining which gate fired and citing the relevant metric
  (max delta, ratio, or absolute floor). The user gets a clear "the
  algorithm has converged" signal instead of an endless descent.

---

## v1.0.23-beta — Revert HF Limit slider remap (May 5, 2026)

### Reverted

- v1.0.22's HF Limit slider 100-4800 remap is reverted to the v1.0.21
  behaviour (slider 0-4700 with `IsDirectionReversed = true`). LMU was
  crashing more aggressively under v1.0.22 — same crash signature as
  before (`hwinput.cpp:2029 Failed to read steering wheel range`) but
  triggered at startup instead of after long sessions. Reverting the
  remap to validate the slider change is involved before iterating again.

---

## v1.0.22-beta — HF Limit slider order fix (May 5, 2026)

### Fixed

- **HF Limit slider order corrected end-to-end.** v1.0.19 made the slider
  use `IsDirectionReversed = true` to put "No Limit" on the right, but
  this also reversed the 100-4700 Hz scale (max filtering ended up on the
  left). The conceptual order users expect is `100 Hz → 4700 Hz → No Limit`
  left-to-right (No Limit = least restrictive = right end). Slider now
  uses a normal direction with range 100–4800 (step 100), where position
  4800 represents "No Limit" — firmware value 0 maps to slider 4800 on
  display, slider 4800 maps to firmware 0 on apply.

---

## v1.0.21-beta — Slew-rate detail-loss guard (May 5, 2026)

### Changed

- **Smart Tune slew-rate "Reduce" recommendation now gated on detail loss.**
  The previous rule descended geometrically (-20 % per apply) until P95 delta
  reached 30 % of the slew budget — convergent in theory, but P95 doesn't
  capture peak transients (kerbs, sharp corner exits) and the slider could
  end up well below the useful floor for the surface, trading kerb clarity
  for no real benefit.
- New gate uses the existing `Asetek.FFB.SmoothedRoughnessNm` /
  `Asetek.FFB.RoughnessNm` properties (added in v1.0.18). Their ratio = how
  much of the raw signal is making it through the slew limiter. At 1.0 the
  slew is transparent ; below 0.85 it's already absorbing > 15 % of the
  high-frequency content. The Reduce recommendation now requires the ratio
  to stay above 0.85.
- When the statistical headroom suggests reducing but the ratio shows
  detail loss, Smart Tune now emits a **"→ Hold"** info card explaining why
  it's *not* recommending a step down — the user learns the slew floor for
  this surface rather than blindly following the recommendation downward.

---

## v1.0.20-beta — Live Auto-tune resurrected (May 5, 2026)

### Added

- **Live Auto-tune button** (FFB Settings → Advanced FFB Diagnostic).
  Reads the rolling 60 s torque buffer (roughness Nm, clipping %,
  utilisation %) and proposes filter values matched to the surface —
  HF Limit, Slew Rate, Anti-Oscillation, Inertia. No CSV log needed.
  Preview-then-apply flow: click "Auto-tune now" to see what would
  change, click "Apply suggestion" to push to the wheelbase. Stamps
  the snapshot as the active profile's baseline so subsequent Auto-tune
  calls behave as delta refinements (small ±500 Hz / ±1 Nm/ms / ±3 % AO
  nudges) rather than full re-assessments.

### Fixed (latent bugs in dormant Auto-tune code)

- **HF Limit suggestion values were indices, not Hz.** The pre-removal
  Auto-tune wrote 6 / 8 / 11 to `ioni_lpf` for street / bumpy / elevation
  archetypes — those map to 6 Hz / 8 Hz / 11 Hz on the real Hz scale,
  i.e. near-total filtering. Now uses 1500 / 2000 / 3000 Hz (and 0 = No
  Limit for smooth surfaces).
- **"AO" was being written to the Damping slider register** (`ioni_damping`)
  instead of the Anti-Oscillation register (`latency_comp_factor`).
  Both `AutoTuneRefine` reads and `ApplyAutoTuneSuggestion` writes now
  target `latency_comp_factor`. Field renamed `IoniDamping` →
  `LatencyCompFactor` in `AutoTuneSuggestion` for clarity.
- **`AutoTuneRefine` HF nudge was ±2 indices, not ±Hz.** Now ±500 Hz
  with proper handling of the 0 = No Limit edge (special-cased so we
  jump 0 ↔ 3000 Hz cleanly when crossing the threshold).
- **Slew rate suggestions could exceed the detected base ceiling.**
  `ApplyAutoTuneSuggestion` now clamps `slew_rate_limit` to
  `MaxSlewRateForCurrentBase × 1000` so a Forte never gets pushed 9.4
  Nm/ms when its hardware caps at 6.7.

These fixes were why the original Auto-tune produced "extreme swings"
and was disabled. Combined with the v1.0.16 PEAK stability fixes, the
feature is safe to re-enable.

---

## v1.0.19-beta — High Frequency Limit slider direction fix (May 5, 2026)

### Fixed

- **High Frequency Limit slider inverted** to match RaceHub direction:
  "No Limit" now on the right, most restrictive values on the left.

---

## v1.0.18-beta — Software slew rate limiter (May 1, 2026)

### Added

- **Software slew rate limiter** on the torque monitoring signal.
  Caps the maximum delta between consecutive 360Hz samples to a
  configurable Nm/ms value, matching the hardware slew rate setting.
  The smoothed signal feeds new SimHub properties that reflect what
  the user actually feels at the wheel, rather than the raw game
  signal that the hardware never fully reproduces.
  - `Asetek.FFB.SmoothedTorqueNm` — slew-limited |torque|
  - `Asetek.FFB.SmoothedRoughnessNm` — stddev of the limited signal
  - `Asetek.FFB.SoftwareSlewRate` — current limit (Nm/ms), 0 = off
- **Auto-sync mode** (default): software slew rate tracks the hardware
  `slew_rate_limit` register so the smoothed metrics always match the
  current profile's torque acceleration setting.
- **Manual override** via SimHub action `Asetek.FFB.SoftwareSlew.Set`
  (pass Nm/ms as argument). Disables auto-sync. Reset with
  `Asetek.FFB.SoftwareSlew.AutoSync`.

---

## v1.0.17-beta — Forte / La Prima Overall Force scale fix (April 30, 2026)

### Fixed

- **`SetOverallForce` was using the Invicta scale (27 Nm) for every base.**
  The slider's effective output saturated at `baseFactory / 27` on
  non-Invicta wheelbases : Forte 18 Nm full slider = 67 % main_gain →
  firmware re-aligned PEAK to 67 % × 13503 = 9047 SMP (~12 Nm flashed
  instead of 18). La Prima saturated at 12/27 = 44 %, La Prima HiPSU at
  16/27 = 59 %. Confirmed on Uzurod's Forte (PEAK = 9047 in Cold-Start
  Diag). Fix uses `baseMax = MaxTorqueForCurrentBase` so 100 % on the
  slider always means 100 % on the firmware regardless of model.
- Same correction in `AsetekSimHubPlugin.UpdateTorqueMonitoring` so the
  live `Asetek.FFB.MaxTorqueNm`, utilisation %, and clipping flag report
  against the detected base's real ceiling.

Invicta users were not affected by this scaling bug (ratio 27/27 = 1).

### Recovery procedure (Forte / La Prima users still capped after v1.0.16)

The fix removes the source of capping but cannot undo a flashed PEAK on
its own. Run Reset Torque Limits + Restore High Torque + power-cycle
once after updating to bring the wheelbase back to factory peak.

---

## v1.0.16-beta — PEAK drift killed + Cold-Start Diag + Advanced UI (April 30, 2026)

### Critical fixes — PEAK torque stability

- **Routine apply paths no longer push `main_gain`.** `ApplyAllCoreSettings(saveToFlash:false)`
  now omits addr 3 from batch1 (8 entries instead of 9). The firmware's
  `PEAK *= main_gain/100` rescale therefore doesn't fire at start-up,
  auto-match, profile load, or any non-flash apply. Confirmed via Jerome's
  test : reboot SimHub with Overall Force at 24.8 Nm, PEAK stays at 20255
  (27 Nm factory) — previously dropped to ~22.8 Nm per session.
- **Apply &amp; Save now uses a single batch pass.** The previous code
  re-sent the 3-batch + name + hash sequence twice before `save_to_flash`
  (mimicking RaceHub's USB capture pattern). Each pass triggered the
  firmware's PEAK rescale, so two passes with `main_gain = 81 %` ended
  up persisting `PEAK × 0.81² = 0.66 × factory`. Single pass : one
  rescale, exactly the user's intent.
- **`RecenterWheel` and `LoadFactoryCenter` no longer flush to flash.**
  Both are runtime-only — the wheel center has to be re-applied after a
  cold boot, but in exchange routine recenters can no longer shave PEAK
  on every click.
- **`ResetWheelbaseTorqueLimits` pushes `main_gain = 100` to RAM before
  writing factory SMP regs.** Without this, the firmware immediately
  re-aligned the SMP_PEAK we just wrote down to `current_main_gain × factory`
  (e.g. user at 92 % → 18634 instead of 20255). Now PEAK stays at factory
  and the slider reads 100 % — adjustable from the FFB tab.

### Added — UI &amp; diagnostics

- **`Cold-Start Diag` button** (Overview → Advanced). Refreshes the HID
  handle (closes / reopens without firing `restart_drive` on the firmware)
  and dumps the firmware state — SMP torque limits in Nm, HT bit (read
  from `request_status` byte 12 bit 1), challenge probe. Equivalent of
  the standalone Python diagnostic, integrated in the plugin.
- **Auto Cold-Start Diag at start-up and on every Reconnect.** The Overview
  tab populates with the current wheelbase state automatically — no need
  to hunt for any button.
- **`Advanced` collapsible section** on Overview. Hides Reconnect / Disconnect
  / Reset Torque Limits / Restore High Torque / Dump Diagnostic / Cold-Start
  Diag by default — clean default UI, advanced controls one click away.
- **Live FFB slider values exposed as SimHub properties.** Damping, Friction,
  Inertia, Anti-Oscillation, Torque Prediction, Slew Rate (Nm/ms), HF Limit
  (Hz), Cornering Force Assist, Bumpstop Hardness / Range — all publish via
  `Asetek.FFB.*`. `OverallForce` is in Nm.
- **`Asetek.FFB.TorqueSourcePath` debug property.** Reports which SimHub
  game property the live torque metrics are sourced from (iRacing 360 Hz
  array, iRacing scalar, LMU `mSteerTorque`, NeoRed LMU plugin, ACC physics).

### Changed

- **HT bit detection** uses `byte 12 bit 1` of `reply_status` (= 0 for ON,
  != 0 for OFF). The challenge probe at register 6071 is regenerated by
  the firmware after every interaction and is therefore unreliable
  post-handshake; status byte 12 is the firmware's own source of truth
  (matches RaceHub's `WheelbaseSimucubeStatusBits.HIGH_TORQUE_MODE_BIT`).
- **`RestoreHighTorqueMode`** is bounded (9 iterations max) and verifies
  success via status byte 12 instead of the challenge value. Returns a
  clear "fault state — power-cycle the wheelbase" message if no progress.
- **`ReadWheelbase` HID I/O hardened.** Pins buffer + overlapped struct
  with `GCHandle.Alloc(Pinned)` for the duration of each I/O, with a
  bounded cancel-wait on timeout. Eliminates a 0xc0000005 access violation
  observed during heavy diagnostic / recovery operations on long-running
  sessions.

### Why a single big release instead of v1.0.10–v1.0.15 patches

Each of v1.0.10 → v1.0.15 was a milestone in the diagnosis (HID parser fix,
status-byte HT detection, no auto-flash on auto-match, no flash on
Recenter, single-pass save, no main_gain in routine batches). The public
release rolls them all up into v1.0.16 because they need to ship together
to actually solve the drift — partial fixes were ineffective.

---

## v1.0.15-beta — Stop the auto-flash hammer (HOTFIX, April 30, 2026)

### Critical fix

- **`LoadAndApplyProfile` no longer triggers `save_to_flash`.** v1.0.14 went
  out with this method still calling `ApplyAllCoreSettings(saveToFlash: true)`
  on every load — and `LoadAndApplyProfile` is invoked by `AutoMatchAndLoad`
  on every game/car change. So opening SimHub fired a flash write
  immediately, before the user did anything. On Jerome's Invicta this
  dropped `SMP_TORQUELIMIT_PEAK` from 20255 (27.0 Nm) to 17518 (23.35 Nm)
  in a single startup cycle — confirmed via cold-boot Python diagnostic
  before / after launching SimHub v1.0.14. The flash-batch `main_gain = 100`
  protection added in v1.0.14 was therefore not enough on its own; whatever
  side effect drives the PEAK drift, the only safe answer is "don't flash
  on auto-paths".

  From v1.0.15 onward, `LoadAndApplyProfile` is a runtime-only push (no
  `save_to_flash`). Flash persistence happens **exclusively** through user
  actions:

  - The `SaveToFlash()` API method (no UI yet — used by the SimHub action
    `Asetek.ApplyAndSave` if a user binds it).
  - The post-confirmation flush inside `RestoreHighTorqueMode`, which
    triggers only when the user clicks "Restore High Torque" and the
    firmware reports HT enabled.
  - The new `LoadApplyAndSaveProfile()` API for callers that explicitly
    want the persisted-on-disk-and-in-flash behaviour.

  Net effect: a default SimHub session never writes to IONI flash. Profile
  changes are runtime apply only, so they survive until the next
  power-cycle of the wheelbase but don't risk the persistent PEAK value.

### Why v1.0.15 instead of v1.0.14.1

The behaviour change in `LoadAndApplyProfile` is significant enough to
warrant its own minor version. Existing callers that relied on auto-flash
must migrate to `LoadApplyAndSaveProfile`.

---

## v1.0.14-beta — Low-torque root-cause fixes + health auto-detection (April 30, 2026)

### Fixed (root-cause work)

- **Default `main_gain` 93 % → 100 %.** The plugin shipped with a runtime
  `main_gain = 93` baked in, derived from one of Jerome's old captures. RaceHub's
  exported XML presets (`Documents\RaceHub Profiles\Wheelbase\…`) all carry
  `addr_main_gain = 100` — confirmed in "LMU 900 27nm.xml". Matching that default
  removes a class of slow-drift symptoms where each profile change shaved another
  small slice off the perceived peak.
- **`addr_profile_settings_bits_1` (28) now sent as 0 instead of 2.** The
  decompiled RaceHub `WheelbaseProfile.SaveSettings` (Assembly-CSharp.dll line
  109955) clears the `Dirty` bit before pushing the profile to the wheelbase.
  Sending 2 (Dirty = true) on every Apply was harmless but inconsistent with the
  firmware's expected post-save state.
- **`save_to_flash` now writes `main_gain = 100` in the flash batches.** Working
  theory after observing repeated diagnostic dumps where `SMP_TORQUELIMIT_PEAK`
  drifted from 20255 (27 Nm) toward 14988 (≈ 20 Nm) on Jerome's Invicta — a 74 %
  ratio that matches `93 % ⁴`. RaceHub never triggers this drift because every
  preset it saves writes `main_gain = 100`. The plugin's user-facing main_gain
  is now applied as a runtime-only write *after* the flash commit, so the
  slider still behaves the same to the user but never shrinks the IONI flash
  copy of PEAK. Even if the multiplicative theory ends up wrong,
  `main_gain = 100` in flash is strictly safer.

### Changed

- **`RestoreHighTorqueMode` rewritten around the firmware status byte.** Now
  mirrors RaceHub's `WheelbaseCommunicationService.ActivateHighTorque`
  (decompiled Assembly-CSharp.dll line 113272): a `while (!HT_BIT_ON)` loop that
  reads a fresh challenge, sends the answer (cmd 150 + value2 = 107), waits
  100 ms, then verifies the result via `request_status` byte 12 (= 0x00 ON,
  = 0x02 OFF) — the same indicator RaceHub watches. The previous v1.0.13
  multi-variant probe used the challenge value itself for verification, which
  the firmware regenerates after every interaction and is therefore unreliable
  post-handshake. Capped at 12 iterations to avoid spinning forever in fault
  state.
- **`Dump Diagnostic` now reads the HT bit from `request_status` byte 12**
  alongside the legacy challenge probe. The status byte is the firmware's
  source of truth; the challenge probe stays for cross-reference but is
  documented as unreliable post-interaction.

### Added

- **Auto-detection at connect + one-click recovery.** On every successful
  `Connect()` the plugin reads `SMP_TORQUELIMIT_PEAK` and the HT status bit
  (read-only, no writes). When the base is in a known-bad state (HT off, or
  peak < 95 % of model spec), the Overview tab shows a yellow top-banner
  warning describing the issue with `Restore High Torque` and `Reset Torque
  Limits` buttons inline. The banner suppresses itself when RaceHub is
  running so two warnings never stack at once.
- **New public API: `IsHighTorqueModeEnabled()`, `RefreshHealthSnapshot()`,
  and read-only properties `HealthHighTorqueOn`, `HealthSmpPeakRaw`,
  `HealthSmpPeakExpected`, `HealthPeakDegraded`, `HealthNeedsAttention`,
  `HealthSummary`** — safe to call any time after a successful connect.

### Why "v1.0.14" instead of v1.0.13.x

We changed the semantics of what gets persisted to flash (`main_gain → 100`
in the flash batches, then re-asserted at runtime to the user value). That's
a behaviour change in the save path, even if the on-screen UX is the same.

---

## v1.0.12-beta — Fresh-challenge-per-round Restore (April 29, 2026)

### Fixed

- **Restore High Torque now reads a fresh challenge before EVERY answer it
  sends.** v1.0.11 read the challenge once, then sent the same precomputed
  answer up to 15 times — but the firmware regenerates the challenge after
  every interaction (any read, status query or write), so by the time the
  answers were sent the challenge was already stale and the firmware
  silently rejected each one. The new flow per round is :
    1. Read fresh challenge (strict match parser).
    2. If challenge == 0, the bit is already set → done.
    3. Compute answer for THIS challenge.
    4. Send the answer + request_status round-trip.
    5. Loop. The next round's read IS the verify.
- **Apply + saveToFlash deferred to AFTER bit confirmation.** Save_to_flash
  itself perturbs the firmware's challenge state, so doing it before the
  handshake completed in v1.0.11 invalidated the answer mid-flight. Now we
  only push main_gain → 100 % once the firmware has confirmed the HT bit
  is set, never before.

---

## v1.0.11-beta — Strict reply match + verified handshake (April 29, 2026)

### Fixed

- **Critical: HID reply parser was matching joystick frames as cmd-153
  replies.** The wheelbase's input pipe carries joystick state (axes,
  buttons) at ~60 Hz alongside cmd-reply frames. The previous parser
  matched on `byte[1] == 0x99` only, which is also a valid axis-byte
  value — so on each read it would lock onto a random joystick frame and
  read whatever bytes happened to be at offset 22 as "the challenge".
  Result: every Diagnostic dump returned a different non-zero challenge,
  and Restore High Torque sent answers computed from junk values, which
  the firmware silently rejected. New strict parser verifies all of
  `byte[0] == 0x6C` (REPORT_ID_IN) + `byte[1] == 0x99` (cmd 153) +
  `bytes[4..5] == requested register (LE)` before accepting the value
  at bytes 22-25. Discovered by comparing raw IN dumps from the Python
  reference recovery script against C# captures.
- **Restore High Torque** now actually verifies the firmware's High-Torque bit
  is enabled after sending the answer, rather than blindly assuming success.
  Previous v1.0.10 reported "High Torque re-enabled" even when the firmware
  silently rejected the answer and the base remained capped — confirmed
  via the new Diagnostic dump button (challenge stayed non-zero after
  Restore returned success).
- Each answer packet is now paired with a `request_status` round-trip and a
  read drain — this matches the working Python reference recovery script
  and gives the firmware time to commit the bit between writes.
- Up to 3 rounds of 5 answer packets are sent, with a verification read
  between each round. As soon as the firmware reports challenge = 0 (bit
  confirmed enabled) the loop exits early.
- The `Apply + saveToFlash` step (which restores the user's main_gain to
  the base's full peak) now runs **before** the challenge/answer sequence
  rather than after, so the flash-save can't interfere with the bit flip.

### Added

- **Honest failure path** — if all 3 rounds finish without the firmware
  confirming the bit, Restore High Torque now returns false with a clear
  message telling the user to fall back to the High Torque toggle in the
  RaceHub UI (top-right corner). RaceHub's own implementation always
  takes effect because it uses a private path — no point pretending we
  succeeded when we didn't.

### Why this matters

The High Torque bit is the difference between feeling 14 Nm and 27 Nm on
an Invicta. A button that silently lies about enabling it is worse than
no button at all. This release makes the bit-state verifiable in real
time and gives users an actionable next step when the soft path fails.

---

## v1.0.10-beta — Read-only firmware diagnostic dump (April 29, 2026)

### Added

- **"Dump Diagnostic" button** (Overview tab, next to Restore High Torque) —
  performs a read-only probe of the wheelbase firmware and saves a timestamped
  text file to `%APPDATA%\AsetekPlugin\diag\` containing :
  - Detected base / wheel models and PIDs
  - Current values stored in flash for `SMP_TORQUELIMIT_CONT`,
    `SMP_TORQUELIMIT_PEAK`, `SMP_SYSTEM_CONTROL` and `SMP_MAX_OUTPUT_POWER`
    (with raw + Nm conversion for the torque limits)
  - High Torque challenge response (0 means the bit is already enabled,
    non-zero means the firmware is in Low Torque state)
  No writes are issued — totally safe to run on a healthy or capped base.
  After the dump, the file's folder opens in Explorer and the dump text is
  copied to the clipboard so it can be pasted into Discord / a support
  thread immediately.

### Why this matters

The High Torque toggle in RaceHub reflects the user-requested state, not
the actual firmware state. When a base is stuck capped, this dump tells
you exactly what the firmware reports — no more guessing whether the
SMP limits are corrupted, whether High Torque really is enabled, or
whether the base is responding at all.

---

## v1.0.9-beta — Telemetry-driven LEDs + High Torque recovery (April 29, 2026)

### Added

- **Telemetry-driven RPM bar on the wheel** — when RaceHub is running with the
  wheel profile set to "SimHub", the plugin now drives the wheel's RPM LEDs
  (incl. the centre LED that wasn't reachable before) and the 6 Flag LEDs
  directly from SimHub telemetry. Auto-throttled to ~30 Hz, no extra config.
  Works on **all SimHub-supported sims** (LMU, iRacing, ACC, AMS2, F1,
  AC, rF2, EA WRC, Dakar, kART, …). Toggle in **LED Control → Wheel LEDs
  via RaceHub MMF**. The SimHub-native "Asetek RaceHub LEDs and display"
  device must be DISABLED to avoid flicker.
- **RPM fill direction selector** — three modes match the RaceHub options:
  Left to Right (classic shift bar), Center to Side (grows symmetrically
  from the centre LED), Side to Center (both ends fill toward the middle).
  Applies to both the wheel's RPM bar and the wheelbase strips so they
  stay in sync.
- **RPM start threshold slider** — below this percent of redline the bar
  stays dark. Default 75 % gives a useful approaching-shift indicator
  without lighting the LEDs at cruise.
- **Wheelbase contextual overlays** (LMU native telemetry):
  - **Pit limiter** flash orange (existing, kept)
  - **ABS engaged** → pulsing pink at ~6 Hz on all LEDs
  - **TC engaged** → strobing cyan at ~15 Hz (very fast, distinguishable from ABS in peripheral vision)
  - **Lift &amp; Coast** progressive violet bar (also fills the 6 wheel Flag
    LEDs progressively — driver sees coasting window remaining at a glance)
  - **Race flag** colour (yellow / blue / red / black / white / checkered / FCY)
  - **RPM bar** classic green→yellow→red gradient with redline flash
  - Priority: Pit > ABS > TC > Flag > Lift & Coast > RPM
- **"Restore High Torque" button** (Overview tab) — recovers a wheelbase
  that's stuck at its low-torque safe limit (~7 Nm Invicta, ~10.5 Nm Forte,
  ~3 Nm La Prima) when RaceHub disabled the High Torque toggle. Lighter
  weight than Reset Torque Limits — try this first.
- **RaceHub coexistence** — the plugin no longer disconnects when RaceHub
  starts. It keeps direct FFB control and re-applies your saved profile
  5 s after RaceHub launch (which would otherwise overwrite your settings).
  Wheel LEDs are routed through the RaceHub bridge automatically when the
  wheel profile is set to "SimHub".
- **Per-base diagnostic properties**: `Status.Wheelbase.Connected`,
  `Status.Wheelbase.Model` ("Invicta" / "Forte" / "La Prima"),
  `Status.Wheelbase.Pid`, plus equivalents for `Status.Wheel.*`. Use these
  in your dashboards to display the actual detected model rather than
  a generic boolean.
- **Debug properties** for telemetry verification: `Debug.LastFlag`,
  `Debug.RpmRatio`, `Debug.RpmThreshold`, `Debug.RpmFillMode`.

### Changed

- LED tab simplified — wheel-LED test palette and rev-lights customization
  panel removed; the new MMF bridge covers the same scope and adds the
  contextual overlays. SimHub-native "Asetek RaceHub LEDs and display"
  device should be disabled when the plugin's MMF push is active.
- Status banner re-styled — green/info instead of red/warning, with a
  short clear status line. Applies to RaceHub coexistence state.
- Plugin reads RPM from `CarSettings_CurrentDisplayedRPMPercent` — the
  same source SimHub itself uses for dashboards / shift-light plugins —
  for consistent behaviour across sims.
- Brighter UI text colours (secondary / tertiary greys lifted) for better
  readability on dark theme.

### Acknowledgements

- Thanks to **@Chris** on Discord for the early feedback on telemetry FFB
  direction and the per-base ceilings input.
- Thanks to **@Uzurod** on Discord for continued bug reports that pushed
  both the v1.0.8 and v1.0.9 recovery paths.

---

## v1.0.8-beta — Torque-limit recovery + Disconnect button (April 29, 2026)

### Fixed
- **Wheelbase could end up silently capped at a low torque after repeated
  Apply+Save cycles** on certain configurations — sometimes still visible in
  RaceHub after closing SimHub, and not always recoverable via a firmware
  reflash. The Apply+Save path has been simplified so the Overall Force
  slider only adjusts the user-facing gain and no longer writes any
  motor-controller setting that could persist into a stuck state.

### Added
- **"Reset Torque Limits" button** (Overview tab, bottom row). Restores the
  detected base to its factory torque configuration in one click and
  re-initialises the drive. After clicking, power-cycle the wheelbase
  (USB unplug + replug) and verify in RaceHub that the Overall Force slider
  reaches the full peak. Confirmation dialog before the write so it's not
  triggered accidentally.
- **"Disconnect" button** (Overview tab, between Reconnect and Reset Torque
  Limits). Releases the HID handle without closing SimHub, so RaceHub or any
  other tool can take over on demand. Click "Reconnect" afterwards to reattach.
- **RaceHub auto-pause**. The plugin now detects when RaceHub is running and
  automatically releases the wheelbase, surfacing a warning banner with an
  inline Reconnect button when RaceHub closes again. Plugin controls are
  greyed out while paused so the two apps never end up writing concurrently.

### Acknowledgements
- Thanks to **@Uzurod** on Discord for the bug report that triggered the
  investigation.

---

## v1.0.7-beta — La Prima+ slew-rate boost with high-power PSU (April 28, 2026)

### Changed
- **La Prima high-power PSU toggle now also lifts the Torque Accel Limit ceiling** from 4.0 Nm/ms (stock) to **6.7 Nm/ms** (matching the Forte spec). The PSU upgrade physically raises both the peak torque and the slew rate, so the slider now reflects that consistently.
- UI helper text on the PSU toggle updated to call out both ceilings being lifted.

### Acknowledgements
- Thanks to **@Chris** on Discord for confirming the La Prima+ slew rate is 6.7 Nm/ms when running the high-power PSU.

---

## v1.0.6-beta — Per-model Torque Accel Limit ceiling (April 28, 2026)

### Added
- **Per-model Torque Accel Limit (slew rate) ceiling** — the slider's max is now capped to what the detected base can physically deliver, mirroring the v1.0.5 Overall Force fix:
  - **4.0 Nm/ms** on La Prima
  - **6.7 Nm/ms** on Forte
  - **9.4 Nm/ms** on Invicta
- Slider falls back to 9.4 Nm/ms before the base is detected so you don't hit an artificially low ceiling on first connect.
- Values pulled from Asetek's official product specs (asetek.com/simsports/product pages).

### Acknowledgements
- Thanks to **@Chris** on Discord for pointing out that the slew rate also varies per model and shouldn't have been left at the Invicta-class 9.4 Nm/ms across the board.

---

## v1.0.5-beta — La Prima support & per-model Overall Force ceiling (April 28, 2026)

### Added
- **La Prima wheelbase detection** — PID `0xF303` is now recognized as "La Prima" instead of falling back to "Unknown (PID_F303)". Plugin auto-identifies the base on connect.
- **Invicta steering wheel detection** — PID `0xF400` is now explicitly recognized as the "Invicta" wheel (was previously caught by the generic auto-scan range without a proper label).
- **Per-model Overall Force ceiling** — the Overall Force slider's maximum is now capped to what the detected base can physically deliver: **12 Nm** on La Prima, **18 Nm** on Forte, **27 Nm** on Invicta. No more silent firmware clipping when sliding past the base's limit. Slider falls back to 27 Nm before the base is detected so you don't hit an artificially low ceiling on first connect.
- **La Prima high-power PSU toggle** (FFB Settings → Game Integration). Tick if you've upgraded to the optional power supply — the Overall Force ceiling becomes **16 Nm** instead of the stock 12 Nm. No effect on Forte / Invicta.

### Changed
- Removed "Invicta S" from the wheelbase enumeration — it's a pedal set, not a base. Was never produced as a wheelbase, listing it would have created confusion.

### Acknowledgements
- Thanks to **@Chris** on Discord for confirming PID_F303 and suggesting the per-model torque cap.
- Thanks to **@jse67** on Discord for testing Invicta wheel detection paths.

---

## v1.0.4-beta — Overall Force fix, live torque monitor & 360 Hz toggle (April 27, 2026)

### Fixed (CRITICAL)
- **Overall Force slider had no perceptible effect** because the plugin was only writing the profile-side `main_gain` and skipping the SMP torque-limit registers (`SMP_TORQUELIMIT_CONT`/`SMP_TORQUELIMIT_PEAK` via cmd 150). The motor was clipping at the previous limit regardless of slider position. Both writes are now paired with each other in `CommitSlidersToCache` and again in `ApplyAllCoreSettings` so loading a profile also restores the SMP caps. Confirmed working in iRacing.

### Added
- **Live torque monitoring properties** (~15 Hz refresh): `Asetek.FFB.CurrentTorqueNm`, `MaxTorqueNm`, `UtilizationPct`, `IsClipping`, `PeakTorqueNm`. Reads from `GameRawData.Telemetry.SteeringWheelTorque` (iRacing) with fallbacks to LMU shared memory and ACC physics.
- **"360 Hz Compatibility Mode" toggle** (FFB Settings → Game Integration) + `Asetek.Toggle360Hz` SimHub action. Sends cmd 233 (`set_360hz_compatibility`) and is re-applied on reconnect.

### Confirmed working
- v1.0.3 slider mapping fix validated in iRacing & LMU.
- Auto-match by Game / CarClass / CarId works across sims (iRacing exposes Game, CarId and CarModel; CarClass may be empty for some series like Porsche Cup — use the "Quick save → by Car" button for those).
- Quick-Save buttons + Re-center + Standstill Damping all behaving as designed.

### Known beta
- Controls-tab button bindings (FFB Strength +/-, range / force presets, toggles, LED modes) not yet hands-on validated across configs. Please open a GitHub issue if any binding misbehaves.

---

## v1.0.3-beta — FFB slider mapping fix + Re-center wheel (April 25, 2026)

### Added
- **"360 Hz Compatibility Mode" toggle** (FFB Settings → Game Integration). Enables the wheelbase's high-rate FFB pipeline so it stays in sync with iRacing's 360 Hz native telemetry and LMU's shared-memory feed. State is persisted by the device in flash and re-applied on reconnect. Also available as the bindable `Asetek.Toggle360Hz` SimHub action (Controls → TOGGLES).
- **"RE-CENTER WHEEL" button** at the bottom of the FFB Settings tab. Sends `set_wheel_center_here` + `save_to_flash` so the new zero point survives a power cycle. Useful after swapping rims when the wheel keeps trying to rotate to the previous center.
- **SimHub action `Asetek.RecenterWheel`** — bindable to any button on a wheel/box via the Controls tab (DEVICE section).
- **"Standstill Damping" toggle** (Game Integration section). Auto-boosts `ioni_damping` to 95% at slow speed (< 13 km/h) to kill wheel oscillations in pits / on grid / pit lane, then restores the user's normal value at racing speed (> 15 km/h, 2 km/h hysteresis prevents flicker). Persisted in `ffb_settings.json`.
- **"↻ RELOAD PRESET" button** next to RE-CENTER WHEEL. Discards unsaved slider edits and restores the active profile values (shortcut for clicking the profile name in the list).
- **Auto-match profile by game / car class**. Toggle on the Overview tab (next to the profile list). Each profile gains optional `Game` and `CarClass` tags. When enabled, the plugin auto-loads the best-matching profile when the active sim or car class changes. Priority: exact `(game, class)` match → game-only match → class-only match. Use the "Tag" button on each profile to auto-fill from the currently running game.
- **Smart toggle** for Auto-match: if no profile already matches the current game+class when you enable it, the plugin auto-creates a new profile with your current slider values and tags it for you.
- **"Load" button** on each profile row (Overview tab) — explicit one-click apply of any saved profile to the wheelbase.
- **"Import RaceHub Presets" button** (Overview tab). Scans `%USERPROFILE%\Documents\RaceHub Profiles\Wheelbase\Backup\` and imports every XML preset auto-exported by RaceHub as a plugin profile. Auto-tags the `Game` field heuristically from the preset name (LMU, iRacing, ACC, RFactor2, AMS2, EAWRC, Dakar, Kart). Skips profiles whose name already exists.
- **"Edit" button** on each profile row — inline editor for the `Game` and `CarClass` tags. Empty field = matches anything. Examples: `Game="LMU" CarClass=""` matches all LMU cars; `Game="" CarClass="GT3"` matches GT3s in any sim; `Game="LMU" CarClass="GT3"` matches all GT3s in LMU.

### Fixed (CRITICAL)
- The per-profile "Save" button silently lost slider edits — it called `LoadProfile()` *before* `SaveCurrentToProfile()`, overwriting your current sliders with the profile's stored values just before saving. Now it commits sliders to cache, then writes the cache to the target profile (no pre-load).
- "APPLY & SAVE" only persisted 8 of the 12 FFB sliders. The Torque Prediction, Torque Accel Limit, Cornering Force Assist and Bumpstop Hardness sliders were silently dropped. All 12 sliders now flow through a unified `CommitSlidersToCache()` helper.

### Added
- **"Save current sliders to..." dropdown** on the FFB Settings tab (below APPLY & SAVE). Pick any profile from the list and write your current slider values to it without applying to the wheelbase. Useful when fine-tuning a session and you want to commit incrementally.
- **`CarId` field** on profiles (more specific than `CarClass`). Match priority: `CarId` > `CarClass` > game-only. Persisted in `profiles.json`. Edit dialog now has 3 fields (Game / CarClass / CarId).
- **"Quick save → by Car Class" / "by Car" buttons** on the FFB Settings tab. Detects the running sim and current car, creates a new profile from your current sliders, auto-tagged either with the broad CarClass (covers all cars of that class) or the specific CarId.
- **Live status line** "Detected: Game=… Class=… Car=…" refreshing every second so you can see what the plugin will tag before you save.
- **RaceHub-format XML mirror**: each plugin profile is also written to `%USERPROFILE%\Documents\RaceHub Profiles\Wheelbase\Backup\Plugin - <Name> - Asetek Plugin Backup.xml` on every save. Provides a redundant readable backup alongside the plugin's `profiles.json`.


### Fixed (CRITICAL)
- **Damping / Friction / Inertia / Anti-Oscillation sliders now write the correct hardware addresses**. Previous versions wired these UI sliders to firmware-constant registers (`damper_gain`, `friction_gain`, `inertia_gain`) that don't drive the FFB feel — moving the sliders had no perceptible effect. Confirmed via decompilation of RaceHub 4.4.3 `Assembly-CSharp.dll` and cross-analysis of 11 RaceHub XML preset exports.
  - `Damping` → now writes `ioni_damping` (was: `damper_gain`)
  - `Friction` → now writes `ioni_friction` (was: `friction_gain`)
  - `Inertia` → now writes `ioni_inertia` (was: `inertia_gain`)
  - `Anti-Oscillation` → now writes `latency_comp_factor` (was: `ioni_damping`)

### Migration note
Profiles saved with v1.0.2-beta or earlier have the Damping / Friction / Inertia / Anti-Oscillation values stored in the wrong addresses. After upgrading: re-set those 4 sliders manually, or re-import your RaceHub presets.

### Discoveries
- `addr_reserved_ui_simple_1` (26) is **not reserved** — it's a packed bitfield holding the 4 Simple Mode values (MainGain / SteeringRange / Smoothing / Damping, 8 bits each)
- `addr_profile_settings_bits_1` (28) is a bitfield: bit 0 = `SimpleMode` flag, bit 1 = `Dirty` flag

---

## v1.0.2-beta — Universal Device Scanner (April 8, 2026)

### Added
- **Auto-scan PID ranges F2xx–F6xx**: the plugin now detects ANY Asetek base or wheel in these ranges, not just hardcoded PIDs
- **New devices supported**: Forte base (PID_F301), Formula Forte wheel (PID_F402)
- **Dynamic UI**: device cards now show the actual detected model name and PID instead of hardcoded "Invicta" / "Forte GT"
- **Unknown PID detection**: devices with unrecognized PIDs in the Asetek range are auto-classified and flagged for reporting

### Fixed
- Users with Forte base (PID_F301) or Formula Forte wheel (PID_F402) were not detected at all

---

## v1.0.1-beta — Multi-Base Support (April 7, 2026)

### Added
- **Forte / La Prima support**: the plugin now tries PID_F200 (Forte/La Prima) automatically if PID_F300 (Invicta) is not found
- **Full Asetek device scan**: when no known base is detected, the plugin scans all VID_2433 devices and logs every PID found — making it easy to report unsupported models
- **Helpful error messages**: displays "Is RaceHub closed?" / "Is the base powered on?" when no Asetek device is detected at all

### Fixed
- Users with Forte or La Prima bases were getting "PID_F300: 0 Found / Not Found" with no further information

---

## v1.0.0-beta — Initial Release (April 6, 2026)

### Features
- **FFB Settings Control**: adjust all force feedback parameters (Overall Force, Spring, Damper, Friction, Inertia, etc.) directly from SimHub — no need for RaceHub
- **True Steering Lock**: automatic steering angle sync per car (reads game telemetry, sends matching lock to the wheelbase)
- **Per-Game Profiles**: save and load named FFB profiles, with optional default profile on startup
- **LED Control (Beta)**: set RPM LED colors and Rev Light brightness
- **Button Mapping**: view real-time button/axis inputs from the wheelbase and Forte GT wheel
- **Live Diagnostics**: connection status, HID report details, last write hex dump

### Requirements
- SimHub 9.x
- Asetek SimSports wheelbase (Invicta confirmed, Forte/La Prima support added in v1.0.1)
- **RaceHub must be closed** before launching SimHub

### Known Limitations
- Settings cannot be read back from the device — the plugin persists them locally in JSON
- LED Control is experimental and not fully tested on all configurations
- Dynamic FFB (real-time telemetry modulation) was removed — `setprofiledata` does not produce perceptible real-time effects
