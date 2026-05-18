# Asetek Control — Changelog

> All notable changes to this plugin will be documented in this file.

---

## v1.5.7 — Sanitize Wheelbase (nuclear recovery) (May 18, 2026)

### Added
- **"Sanitize Wheelbase" button** in the Advanced Recovery expander
  (Debug tab), right next to *Restore Factory Default*. Same red
  confirmation checkbox gates both — tick it once and either button
  becomes available.
- Sanitize covers cases where the SMP-only reset doesn't fix the
  problem because the soft-cap lives in `addr_*` hardware bitfields :
  - `addr_simucube_options = 0` (HandsOff Off + all safety flags off)
  - `addr_max_motor_current = factory peak`
  - `addr_standbys_settings = 0` (no safe-mode auto-off)
  - SMP regs reset to factory (same as Restore Factory Default)
  - `main_gain` forced to 100 %
  - `save_to_flash` + `restart_drive`

### Why
- Confirmed on Uzorod's Forte (2026-05-18) : RaceHub showed Overall
  Force max at **10.5 Nm** instead of the 18 Nm nominal even after
  factory reset + fresh RaceHub install on a new PC. The corruption
  lives in the STM32 flash (`addr_simucube_options = 2` =
  `HandsOffDetectionLevel = Medium` capped the firmware output).
  Standard SMP reset left those addr_* untouched.

### Safety
- Same confirmation checkbox as *Restore Factory Default* — destructive,
  requires explicit user opt-in.
- Aborts if RaceHub is running (would race with HID handle).
- Uses the same `goto_test_mode → SMP writes → save_to_flash →
  restart_drive` sequence that's been field-validated as RaceHub-safe.

---

## v1.5.6 — Status read robustness (race with 60 Hz heartbeat) (May 18, 2026)

### Fixed
- **HT bit + safe-mode both showing "(status read failed)"** in v1.5.5
  dumps. Uzorod's 23:19 dump had two back-to-back `request_status`
  reads fail simultaneously because the dump section issued one HID
  request per consumer (HT detection, then safe-mode detection) and
  both raced with the 60 Hz `set_all_leds` heartbeat traffic. Auto-prime
  and SMP-register reads worked fine — only the `reply_status` frame
  consumers were affected.
- Now : the dump section reads the status frame **once** and reuses
  the same bytes for both the HT verdict and the safe-mode flag.
- `ReadStatusBitfield()` itself is also more robust : 3 full
  request/read cycles (was 1 send + 3 reads), per-read timeout backs
  off across cycles (150 / 200 / 250 ms), and the reply length
  requirement relaxed from 64 to 15 bytes (then padded to 64) so
  partial frames don't get rejected when the device splits the reply.
- `IsHighTorqueModeEnabled()` now delegates to `ReadStatusBitfield()`
  so the live banner refresh and the dump share the same robust path.

---

## v1.5.5 — Challenge probe interpretation cleanup (May 18, 2026)

### Fixed
- **Misleading "firmware is in LOW TORQUE state" verdict in the
  challenge probe section.** Uzorod's v1.5.3 dump showed challenge
  = `0x01E18ADB` (non-zero) AND HT confirmed ENABLED via byte 14 bit 7
  AND auto-prime success AND RaceHub displaying HT=ON simultaneously —
  proving a non-zero challenge does NOT mean LT mode. The firmware
  regenerates the challenge continuously ; only the all-zeros state
  is a clean post-handshake signature.
- Reworded the dump section as **informational only**, with explicit
  pointers back to the HT bit section (byte 14 bit 7) as the
  authoritative status source.

---

## v1.5.4 — Auto-prime telemetry detailed (May 18, 2026)

### Fixed
- **Auto-prime result stuck at "(not run)"** in the dump even when the
  task had been scheduled. The background runner could early-return
  silently on either of its two guards (wheelbase disconnected during
  the 12 s wait, or RaceHub launched manually in the meantime), leaving
  `LastAutoPrimeResult` at its initial value — so the dump couldn't
  tell us *why* priming hadn't happened.
- Now we set the result field at every transition :
  - `scheduled (background, 12 s)` when the task is queued
  - `skipped (wheelbase disconnected during 12 s wait)` if the device
    drops between Connect() and the runner wake-up
  - `skipped (RaceHub launched manually during 12 s wait)` if the user
    started RaceHub before the runner fired
  - `skipped (RaceHub already running at Connect)` for the immediate path
  - `skipped (La Prima — no HT mode needed)` for La Prima bases
  - `background error : <message>` if an exception is swallowed
- No functional change to the priming itself ; this is purely a
  diagnostic improvement so dumps reveal the path that was taken.

---

## v1.5.3 — Real HT bit identified (byte 14 bit 7) (May 18, 2026)

### Fixed
- **HT bit detection corrected.** The v1.5.2 release retracted the old
  rule `(byte[12] & 0x02) == 0` after Uzorod's Forte field test proved
  it stayed set in both LT and HT modes. The diff of his factory-reset
  dump (challenge probe = 0x00000000 = HT confirmed ENABLED via the
  Asetek handshake) against the prior dump (challenge non-zero = LT)
  isolated **byte 14 bit 7 (mask 0x80)** as the real indicator :
  - LT mode : byte 14 = `0xE6` (bit 7 set)
  - HT mode : byte 14 = `0x62` (bit 7 clear)
  - Cross-checked against Jerome's Invicta dumps @ 22 Nm working :
    byte 14 = `0x2A` (bit 7 clear) — consistent.
- **Health banner re-enabled** with the corrected detection. The
  v1.5.2 kill-switch is removed ; users will once again get a
  recovery-procedure banner if HT genuinely drops mid-session,
  without the false positives that plagued v1.0.15b → v1.5.1.

### Memory
- New rule documented in `asetek_reverse_engineering.md` for future
  firmware version checks.

---

## v1.5.2 — Forte bounds verified, standstill damping fix, HT detection retracted (May 18, 2026)

### Fixed
- **"High Torque OFF" banner crying wolf.** The v1.0.15b rule
  `(byte[12] & 0x02) == 0` for HT detection turned out to be wrong on
  current firmware : Uzorod's Forte with RaceHub reporting HT=ON and
  SMP_TORQUELIMIT_PEAK reading full spec still showed byte 12 bit 1
  set ; Jerome's own Invicta dumps at 22 Nm working perfectly showed
  the same bit set too. Until we identify the real HT indicator, the
  banner is suppressed and the dump section is rewritten to surface
  candidate bytes for diagnosis rather than claim a verdict.
- **Damping slider drifting to 95 % "by itself"** in pits — that was
  the Standstill Damping feature kicking in (auto-boost ioni_damping
  when `speed < 13 km/h`). The override value was a 95 % development
  sledgehammer that turned the wheel into a brick. **Lowered to 60 %**
  (still kills oscillations, keeps the wheel alive).

### Added
- **`Base.StandstillActive` SimHub property** + dump annotation when
  the override is engaged, so users can wire a dashboard indicator
  and understand why their slider value drifts at low speed.
- **Game Integration notice** updated to mention the override value
  (60 %) and clarify it's expected behaviour, not a bug.

### Verified
- **Forte slider bounds** cross-checked against Uzorod's RaceHub
  `Test-Mini.xml` / `Test-Maxi.xml` exports : steering 180–1890°,
  slew 0.1–6.7 Nm/ms, main_gain 28–100 %, bumpstop 0–2 — all already
  implemented via the per-base `WheelbaseSpec` table.

---

## v1.5.1 — Shift beep "Test now" button fix (May 18, 2026)

### Fixed
- **"Test beep now" silently did nothing** when the user hadn't ticked
  "Enable Shift Beep" first. The button called `ShiftBeepTick()` which
  early-returns on `!ShiftBeepEnabled`. Now the test bypasses the
  enable/threshold/min-interval guards and plays the configured
  wheelbase Beep (or PC sound) directly — useful for confirming the
  route is wired up before tuning the threshold.

---

## v1.5.0 — Shift beep silent (route default fix) (May 18, 2026)

### Fixed
- **Shift beep didn't trigger any sound.** Default `ShiftBeepRoute` was
  still `"pc"` from v1.3, which fell back to
  `System.Media.SystemSounds.Asterisk` — usually inaudible in a headset
  or VR setup, where Windows system sounds are bypassed.
- New default : `ShiftBeepRoute = "wheelbase"` → plays Beep 8 on the
  Invicta piezo buzzer directly through the base.
- **One-time migration** : on load, if the saved route is `"pc"` AND no
  wav path is configured, we silently upgrade to `"wheelbase"`. Users
  who explicitly set a wav file are respected and stay on PC route.

---

## v1.4.9 — Remove duplicate Smart Driving Mode block (May 18, 2026)

### Removed
- **Legacy "Smart Driving Mode (BETA)" card** removed from FFB Settings —
  it was a v1.3.16 module that wrote to the firmware's Torque Acceleration
  Limit live, which conflicts with the post-v1.4 *"no firmware writes"*
  architecture. The new **Adaptive FFB Zones (Phase 1)** card replaces it
  with a safe per-profile modulation approach.
- `SmartDrivingEnabled` / `SmartSlewEnabled` properties retained in
  AsetekManager for backwards compat with saved settings, but no longer
  exposed in the UI.

---

## v1.4.8 — Shift Beep relocation + adaptive target laps (May 18, 2026)

### Changed
- **Shift Beep card relocated** to the top of *FFB Settings*, right under
  the quick-save row. Since the RPM threshold is part of the profile,
  it now sits next to the per-car save actions instead of buried at
  the bottom of the tab.
- **Adaptive FFB Zones — "Laps to learn" slider** (2-20, default 5).
  The user picks how many laps the learner should observe before the
  model is declared "complete" for the current track + car. Extra laps
  still refine the rolling peaks ; the slider drives the *"X of Y laps"*
  progress label and (in Phase 2) gates auto-modulation until enough
  data is in.

---

## v1.4.7 — Adaptive FFB Zones (beta — Phase 1 : Learning) (May 18, 2026)

### Added — Smart Driving Mode, Phase 1
- **Per-track / per-car FFB peak learning.** While you drive, the plugin
  bins `|FFB level|` by track position (200 bins of 0.5 %) and tracks
  the rolling peak per bin across laps. After 2+ laps with samples
  ≥ sensitivity threshold, consecutive flagged bins are merged into
  contiguous **hot zones** (e.g. *"56.0 % → 58.5 %, peak 96.2 %"* =
  Karussell at Nordschleife on a GT3).
- **Persistence** : zones are stored per `(game, track, car)` in
  `%APPDATA%/AsetekPlugin/adaptive_zones.json`, restored on plugin start.
- **FFB Settings UI** :
  - Green explainer card describing the concept (beta).
  - "Capture telemetry (learning)" toggle (default ON).
  - **Sensitivity slider** 50–100 % (default 90 %) — tunes which peaks
    count as a hot zone. Slider value persists ; **its effect lands in
    Phase 2** (auto-soften) — for Phase 1 it just gates which zones
    show up in the list.
  - Live stats line (laps captured, zones detected, current track + car).
  - Top-10 zone list with start %, end %, peak |ffb|.
  - **"Forget zones for this track"** button.
  - Greyed-out **"Apply modulation (coming in v1.5)"** placeholder.
- **Zero wheelbase writes.** Pure read of SimHub's `GameFfbLevel` +
  `TrackPositionPercent`. No HID traffic, no firmware risk.

### Roadmap — Phase 2 (planned v1.5)
- Pre-bake "soft -15 %" and "soft -30 %" variants of the active profile.
- GPS-anticipated `setprofiledata` switches : push soft variant ~150 ms
  before entering a known hot zone, restore on exit.
- Per-zone intensity tuning via the existing sensitivity slider.

---

## v1.4.6 — Per-profile shift beep + UI cleanup (May 18, 2026)

### Changed
- **Shift Beep RPM threshold is now saved per profile.** Different cars
  have different ideal shift points, so the slider lives in *FFB Settings*
  and gets captured into the active profile (via `CaptureCurrentAsProfile`)
  alongside the other FFB values. Quick-save / "Save to wheelbase" commit
  it like any other slider.
- **Safety tab beep section removed.** WHEELBASE BUILT-IN BEEPS probe +
  SHIFT BEEP route/volume/wav controls are wrapped in
  `#if SHOW_SAFETY_BEEP_LEGACY` (not compiled by default). The remaining
  beep config — Asetek wheelbase buzzer, Beep 8, enabled — is now defaulted.

### Fixed
- **Safe-mode banner not appearing.** Refresh of `IsBaseSafeMode` was
  running on the gameDetectTimer threadpool, which raced with the
  60 Hz heartbeat HID writes and sometimes returned stale frames.
  Moved the refresh into the 1 s UI status timer (where it's serialized
  with the existing health snapshot read), so the banner now shows
  within ~1 s of pressing the Invicta torque-off button.

---

## v1.4.5 — Invicta safe-mode button detection (May 18, 2026)

### Added
- **Safe-mode detection.** The plugin now detects when the Invicta
  TORQUE-OFF button is pressed (the yellow safety button on the base).
  Confirmed mapping via 2-dump diff: firmware status reply
  **byte 45 bit 6 (mask 0x40)** flips `0 → 1` exactly when the button
  is pressed (FFB cut). Bytes 48–50 also carry a non-zero event payload
  when safe mode engages.

- **`Base.SafeMode` SimHub property** (boolean). Surfaces the flag to
  dashboards / NCalc expressions.

- **Red banner in Overview** appears within ~1 s of pressing the button :
  *"⚠ Base in SAFE MODE — FFB is cut. Press the yellow TORQUE-OFF button
  on the Invicta to re-arm."*

- **Diag dump** now shows a clean `Safe-mode detection` section with
  the decoded flag + fault payload, plus the full 64-byte status reply
  hex dump (kept for future reverse-engineering).

### Internals
- `AsetekManager.IsBaseSafeMode` cached property, refreshed every 2 s
  by the existing game-detection timer (no extra HID polling thread).
- `RefreshBaseSafeMode()` public method for on-demand UI refresh.

---

## v1.4.1 — Auto-enable High Torque mode (May 18, 2026)

### Added
- **Auto-HT at startup.** After `Connect()` succeeds, the plugin now
  automatically runs `RestoreHighTorqueMode()` — mirroring RaceHub's
  `WheelbaseDataMediator.InitializeMediator()` which calls
  `ActivateHighTorqueWithAction()` when `WheelbaseAutoEnableHighTorque=true`.
  Previously the plugin just opened HID handles and stayed in whatever
  torque state the firmware was in. If HT was disabled for any reason
  (RaceHub interaction, firmware glitch, USB reconnect), the plugin stayed
  at 8 Nm LT cap with no automatic recovery.

- **Challenge probe in health monitoring.** `RefreshHealthSnapshot()` now
  verifies HT status via the register 6071 challenge probe (every 10s)
  when byte 12 reports HT=ON. On Forte (and possibly other models),
  byte 12 bit 1 can read "HT enabled" while the firmware is actually
  in Low Torque mode. Without this double-check, `HealthHighTorqueOn`
  was `true`, the warning banner never appeared, and force was silently
  capped at 8 Nm.

- **Auto-recovery when HT OFF detected.** When 3 consecutive health
  readings confirm HT is OFF, the plugin automatically attempts a
  `SoftRestartDriveForHT()` (IONI cold boot → HT auto-on). Capped at
  3 attempts per session to avoid infinite loops on genuinely faulted
  hardware. Previously the user had to manually click the recovery button.

### Root cause analysis
RaceHub's codebase (decompiled) revealed:
1. `WheelbaseDataMediator.InitializeMediator()` auto-enables HT at every
   startup via challenge/answer on reg 6071 — our plugin never did this.
2. `SetOverallForceSliderRange()` caps main_gain to `8Nm / torqueConst`
   when `HIGH_TORQUE_MODE_BIT` is OFF — this is the 8 Nm cap mechanism.
3. `GameSettingMediator` does NOT toggle HT per-game — HT is firmware
   persistent state, not per-session.
4. The status byte 12 bit 1 can be a false positive (says HT=ON when
   actually LT) — the challenge probe (reg 6071 value=0 means truly HT)
   is the only authoritative indicator.

---

## v1.4.0z10 — Plugin/RaceHub coexistence fixed (May 16, 2026)

### Fixed
- **STOP PLUGIN now actually stops everything.** Previously the 360 pkt/s
  heartbeat thread was started on Connect but never killed — only gated by
  `_wheelbaseConnected`. If anything briefly re-flipped that flag (status
  reads, UI refresh, Forte detection) the heartbeat resumed firing while
  RaceHub thought it owned the device, triggering Windows USB add/remove
  "bibip" sounds and degraded RaceHub FFB. `StopPlugin()` now calls
  `StopWheelbaseHeartbeat()` before `Disconnect()`.

### Changed
- **`WheelbaseHeartbeatEnabled` default → false.** Until we have proof the
  360 pkt/s stream actually helps standalone FFB, it stays off by default
  so the plugin coexists cleanly with RaceHub. Toggle in the bottom row
  re-enables it for plugin-only testing.
- **`AutoReleaseWheelOnGame` default → false.** The auto-release was meant
  to hand the wheel HID to DirectInput at game start, but the HID
  transitions confused RaceHub. Opt-in via the toggle if needed.

---

## v1.4.0z9 — REVERT z6/z7/z8 — back to z5's known-working form (May 16, 2026)

### Reverted
Jerome confirmed in field test that **v1.4.0z5 worked perfectly** (full 27 Nm,
no LT cap in corners), and every "more correct" attempt to mirror RaceHub
byte-for-byte (z6/z7/z8) regressed back to ~8 Nm capping. Reverting the
read-side and answer-side packet construction to exactly z5:

- **TryReadDriveParam**: `pkt151[2] = 107, pkt151[3] = 0` (z5 form,
  applied to ALL register reads — the firmware apparently ignores
  value1/value2 on cmd 151 reads except for some unknown state machine
  on reg 6071 that gets confused if we send value2=107 there).
- **BuildHighTorqueAnswerPacket**: `p[2] = 0, p[3] = 107` (z5 form,
  value1=0 instead of echoing replyValue1).

### Lesson
The decompiled RaceHub source says one thing about packet layout
(value1=byte2, value2=byte3, value2 set to 107 on read AND write), but the
empirical wire protocol the firmware accepts is something else. **The
empirical test (does HT stay during a 2-3 lap drive?) is the only
authoritative validation.** From now on we keep z5's form unless a real
USB sniff comparison vs RaceHub proves otherwise.

---

## v1.4.0z8 — value2=107 token now scoped to reg 6071 only (May 16, 2026)

### Fixed
- **CRITICAL — HT no longer drops during drive.** v1.4.0z6 unconditionally
  set `value2 = 107` on every `start_read_drive_params` (cmd 151) read,
  including generic SMP/status reads done continuously while driving.
  RaceHub actually has TWO separate code paths
  (`_racehub_WheelbaseCommService.cs`):
  - `ActivateHighTorque` line 970: `value2 = 107` (HT session token) —
    only when reading reg 6071 (VAL_ACTIVATE_HIGH_TORQUE_CHALLENGE).
  - `ReadWheelbaseSetSettingsDataPacket` line 1545 (used by every other
    register read in RaceHub): `value2 = 0` (default).

  Sending the HT session token on non-HT reads while driving made the
  firmware drop HT mid-session — exactly the regression Jerome reported
  after a fresh cold boot (HT ENABLED at startup, then disappeared after
  a few laps). z8 conditions `value2` on `regAddr == 6071` so generic
  reads stay neutral.

---

## v1.4.0z7 — Echo firmware session token in HT answer (May 16, 2026)

### Fixed
- **CRITICAL — value1 of the answer packet now echoes the firmware's reply.**
  RaceHub's `ActivateHighTorque` deserializes the cmd 153 challenge reply
  into a `WheelbaseSetSettingsDataPacket`, then explicitly mutates only
  `command`/`value2`/`addrs[0]`/`values[0]` before sending the answer —
  leaving `value1` (byte 2) UNCHANGED from whatever the firmware put in the
  reply. Likely a session/sequence token the firmware checks before
  accepting the answer. Our plugin always sent `value1 = 0`, so the firmware
  silently rejected every challenge answer with a fresh value1 token. Now
  `TryReadDriveParam` captures `resp[2]` (replyValue1) and
  `RestoreHighTorqueMode` passes it through `BuildHighTorqueAnswerPacket`
  → echoed into byte 2 of the answer, matching RaceHub byte-for-byte.

---

## v1.4.0z6 — HT byte-offset fix completed on READ side too (May 16, 2026)

### Fixed
- **CRITICAL — symmetric value2=107 on both halves of the handshake.**
  v1.4.0z5 fixed the offset only on the ANSWER packet
  (`BuildHighTorqueAnswerPacket`, cmd 150) but left the READ packet
  (`TryReadDriveParam`, cmd 151) writing `107` to byte 2 (value1). RaceHub
  (`_racehub_WheelbaseCommService.cs` line 970) sets `value2 = 107` on
  BOTH the cmd 151 read AND the cmd 150 write — they're paired session
  tokens. After z5 our handshake was asymmetric: read with value1=107,
  write with value2=107 — firmware probably treated them as belonging to
  different sessions and dropped HT mid-drive, explaining the FFB loss
  reported on z5. z6 makes both packets identical to RaceHub:
  `value1 = 0, value2 = 107`.

---

## v1.4.0z5 — HT challenge byte-offset fix (May 16, 2026)

### Removed (Overview bottom row cleanup)
- `Force Release HID` button — debug-only brute-close, never needed by users.
- `🪄 Replay RaceHub Init` button — RE probe that's now obsolete since the
  real fix (value2 byte offset) was identified.
- `Wheelbase heartbeat (360 pkt/s)` toggle — kept enabled silently.
- `Auto-release wheel HID on game start` toggle — kept enabled silently.
- `Live FFB : … Peak : …` label — debug telemetry.

The bottom row now fits on one line again: Reconnect • Disconnect • STOP/START •
Re-center wheel • Dump Diagnostic. Underlying API methods stay on
AsetekManager so they can be wired to SimHub action bindings or re-exposed
in the Debug tab later.

### Fixed
- **CRITICAL: High Torque challenge answer was being rejected silently** by
  the firmware due to a byte-offset bug in `BuildHighTorqueAnswerPacket`.
  RaceHub's `WheelbaseSetSettingsDataPacket` struct (Pack=1) has layout
  `byte 0 reportID | byte 1 command | byte 2 value1 | byte 3 value2`, and
  RaceHub's `ActivateHighTorque` sets `value2 = 107` (token), leaving
  `value1 = 0`. Our plugin was writing `107` to `p[2]` (value1) and `0` to
  `p[3]` (value2) — the firmware checks `value2` for the token and threw
  every challenge answer on the floor without flipping the HT bit. Net
  effect: HT bit appeared "already enabled" in status reads (because the
  base never lost HT on cold boot) but any time the user reset / re-armed,
  the handshake would fail and the base stayed in the ~8 Nm Low Torque cap
  we kept seeing in-game despite RaceHub achieving full 27 Nm. Swapped
  `p[2]` and `p[3]` assignments in all three challenge-answer variants so
  `value2 = 107, value1 = 0` matches RaceHub byte-for-byte.

  Discovered by disassembling RaceHub's `Assembly-CSharp.dll` with
  dnSpy.Console and comparing the packet construction path against ours.

---

## v1.4.0 — RaceHub 360 Hz heartbeat parity + LED protocol fixes (May 16, 2026)

### Why
USB-sniff comparison of RaceHub vs our plugin during 3-lap LMU drives revealed
RaceHub continuously pushes ~366 wheelbase commands per second (cmd 0xD2
set_all_leds, 6-chunk pattern at addrs 0/27/54/81/108/135) while our plugin
pushed only on demand. Without this heartbeat the firmware drops out of its
360 Hz interpolation mode and FFB feels "smoothed/clipped" above 25-30 %
torque in fast corners.

### Added
- **Wheelbase 60 Hz heartbeat thread** : on wheelbase-connect, starts a
  background thread that mirrors RaceHub's exact wire pattern (6 packets per
  frame, value1=3, chunks at 0/27/54/81/108/135, refresh=1 only on packet 6)
  at ~60 frames/sec = 360 packets/sec. Keeps the firmware's 360 Hz mode alive
  end-to-end during driving.
- `WheelbaseHeartbeatEnabled` toggle (defaults true).
- Diagnostic build-version string now reads dynamically from
  `Assembly.GetExecutingAssembly().GetName().Version` (no more drift between
  hardcoded label and csproj).

### Investigated / partial
- MMF host mode color order : after multiple swap attempts (RGBA/BGRA/GBRA),
  cyclic R→B→G→R shift still observed on the wheel rim. The wire-level test
  buttons (All RED / All GREEN / All BLUE direct-push) confirm the wheel
  firmware does NOT use straight RGB byte order in our writes. Investigation
  ongoing — possibly a per-LED color-format register we haven't reverse-
  engineered yet.

---

## v1.3.9 — MMF host mode + RaceHub protocol reverse-engineering (May 15, 2026)

### Major changes
- **MMF host mode (BETA)** : the plugin can now CREATE the `Local\RaceHubXSimHub`
  MMF itself, replacing RaceHub for LED control. SimHub-native "Asetek RaceHub
  LEDs and display" device connects to our MMF and writes RPM + Flag colors,
  which we relay to the wheel via HID. RaceHub no longer required for LEDs.
- **Reverse-engineered Forte GT LED HID protocol** via USB sniff (USBPcap +
  tshark) : confirmed `02 52 12 + 15 indices + 15 RGB + refresh=1` per packet,
  with byte-VALUE addressing (not slot-position).
- **Fixed RPM_LED_ORDER** from `{41..45, 0..9}` (0-based, wrong) to
  `{41..45, 1..10}` (1-based, matches RaceHub sniff exactly).

### Added
- `🏠 Become MMF host` button : creates the MMF as host, arms wheel external
  control. Lets the plugin drive LEDs without RaceHub running.
- `🔬 Dump MMF buffers (hex)` : reads current MMF state in reader or host mode.
- `⚪ All LEDs WHITE (60)` / `⚫ All LEDs OFF` : full-frame test buttons.
- `R→42 / G→42 / B→42` : direct color test buttons that bypass MMF.
- Index Probe grid 0-63 with full 4-packet protocol (`ProbeSingleLedFullFrame`).
- Auto-sweep tool (`StartLedSweep`) to walk firmware indices empirically.
- USB sniffing helper script `sniff_forte_v2.py` (USBPcap + tshark wrapper).

### Known issues (deferred to next session)
- Color byte order in MMF still wrong : intent green shows as red on wheel,
  cyclic R→B→G→R shift remains. Multiple swap attempts (RGBA, BGRA, GBRA) did
  not fully fix. Need direct color test via new R/G/B test buttons to isolate.
- Custom RPM curve UI colors are NOT applied in MMF host mode (only direct
  push). User confusion : "redzone green" UI setting ignored when MMF is host.

### Added
- **🔬 Dump MMF buffers (hex) button** in LED Control tab → reads the current
  rev + flag buffers from our hosted MMF and prints them in a scrollable hex
  panel. Lets us see exactly what SimHub writes when different LED Profile
  configurations are applied.

---

## v1.3.24 — Properties-based LED pipeline (ATSR_Hub-style) (May 15, 2026)

### Why this version
After reverse-engineering ATSR_Hub, DanielNewmanRacing, SOELPEC, and Leoxz plugins
for their LED-Manager integration pattern, we confirmed : there is **no public
SimHub API to register a custom RGB LED device**. The community pattern is
universal — plugins expose SimHub **properties** that hold the desired LED
colors, and the user binds those properties to the SimHub LED Profile that
targets a built-in device (in our case the native "Asetek RaceHub LEDs and
display" device, which writes to the wheel via MMF).

This version moves us to that architecture and ships a ready-made LED profile.

### New SimHub properties published every tick (60 Hz)

| Property | Type | Meaning |
|---|---|---|
| `Asetek.Led.Rpm.L1`..`L15` | int (ARGB) | Final color of each of the 15 RPM bar LEDs after threshold, gradient, brightness, and redline flash logic |
| `Asetek.Led.Rpm.L1.Hex`..`L15.Hex` | string | Same as above as 6-char hex (e.g. `"00FF00"`) — easier for JS string templates |
| `Asetek.Led.Flag.F1`..`F6` | int (ARGB) | Final color of each of the 6 Flag LEDs (lit when its bound property is true, off otherwise) |
| `Asetek.Led.Flag.F1.Hex`..`F6.Hex` | string | Same as hex |
| `Asetek.Led.Rpm.Count` | int | 15 (constant) |
| `Asetek.Led.Flag.Count` | int | 6 (constant) |
| `Asetek.Led.BrightnessPct` | int | Current global brightness slider value (0-100) |
| `Asetek.Led.RedlineActive` | bool | True when current RPM > redline threshold (97 % default) |

### Ready-made `.ledsprofile`
`AsetekPlugin Default LED Profile.ledsprofile` shipped with the plugin :
- Container 1 : "Asetek RPM Bar (15 LEDs)" — `ScriptedContent` reading `Asetek.Led.Rpm.L1..L15`
- Container 2 : "Asetek Flag LEDs (6)" — reads `Asetek.Led.Flag.F1..F6`

**To use** :
1. Re-enable "Asetek RaceHub LEDs and display" in SimHub Devices (if disabled).
2. SimHub → LED Manager → Import `AsetekPlugin Default LED Profile.ledsprofile`.
3. Target device : your Forte GT / Invicta wheel.
4. The profile is now driven by the plugin's per-LED properties — every change in the plugin (RPM thresholds, per-LED colors, brightness, Flag bindings) flows to the wheel via SimHub LED Manager → MMF → RaceHub → wheel firmware.

### Internal architecture changes
- `AsetekManager.UpdateForteRpmLeds(rpmPct)` no longer early-returns when Forte isn't connected ; it still computes the per-LED frame so the SimHub properties have live data even without HID. Direct HID is now conditional on `_forteConnected`.
- New public state : `CurrentForteRpmFrame` (Color[15]), `CurrentForteFlagFrame` (Color[6]).
- `AsetekSimHubPlugin.DataUpdate` now ALWAYS calls `UpdateForteRpmLeds(rpmPct)` and mirrors the resulting frame to the 36 LED properties + brightness + redline flag.
- Version label in the UI title bar now reads dynamically from `Assembly.GetExecutingAssembly().GetName().Version` — no more hardcoded "v1.3.8" drifting from csproj.

### Notes
- The direct-HID rendering path (`ForteSetLeds()`) is still used when the SimHub-native Asetek device is disabled. Both paths coexist.
- The MMF push (`PushTelemetryFrameToMmf`) is kept for users who prefer not to touch the LED Manager UI — toggle in the LED tab.

---

## v1.3.22 — Real Flag LED HID push + RPM demo sweep + Index Probe (May 15, 2026)

### Fixed — Flag LED Test button now drives the physical wheel
v1.3.21's Test button only flipped the in-UI live indicator dot. Now it
sends a real `ForteSetLeds()` HID command to the wheel for 800 ms, using
the slot's configured color AND the configured HID index. You actually
see the LED light up on the wheel.

### Added — Flag LED HID index field
Each of the 6 Flag LED slots now has an editable **HID index** input
(default 10/11/12/13/14/15 for FL1/FL2/FL3/FR1/FR2/FR3). The plugin
sends `ForteSetLeds([(index, R, G, B)])` to that index when the bound
SimHub property is true.

### Added — Index Probe sweep (find physical indices empirically)
At the bottom of the Flag LED card, a grid of buttons 10..39. Click any
number → that single LED index lights up red for 1.5 s. Watch your
wheel, identify which physical LED illuminates, then enter that index
in the appropriate FL/FR slot. Three iterations and you've mapped every
flag LED on your Forte GT.

### Added — RPM bar Demo Sweep
Big primary "▶ Run RPM demo sweep (3 s)" button in the RPM customization
section. Click → animates rpmPct 0 → 1 → 0 over 3 seconds at ~30 Hz so
the user can preview their per-LED thresholds + colors + redline flash
WITHOUT firing up a sim. Restores the bar to dark when done.

### Added — Permanent Flag LED rendering loop
SimHub plugin tick now calls `DriveFlagLedsFromLiveState()` after reading
the bound properties — that pushes HID writes edge-triggered (only on
state changes) so the wheel LEDs follow the in-game state continuously.
60 Hz spam is avoided by a per-slot `_flagLedPushed[]` cache.

### Internal
- `SetFlagLedPhysical(slot, on)` — single-LED HID write helper.
- `DriveFlagLedsFromLiveState()` — edge-triggered push driven by plugin tick.
- `TestFlagLedPulse(slot)` — 800 ms pulse with auto-revert (used by Test button).
- `RunRpmBarDemo()` — 30 Hz triangle-wave sweep on a background thread.
- `FlagLedHidIndex[6]` array — persisted under JSON key `FlagLedHidIndex`.

---

## v1.3.21 — Hex-visible color picker + Flag LEDs 3×3 layout (May 15, 2026)

### Changed — color picker UX (back to WPF popup, with everything)
The Windows-only ColorDialog from v1.3.20 hid the hex code behind multiple
sliders. v1.3.21 brings back a WPF popup that shows :
- The **hex code in an editable Consolas-font box** (always visible, type
  to apply, copy-paste between LEDs in seconds).
- A 10-color **quick palette** with per-dot hex tooltip.
- A **🎨 Open color wheel...** button that still launches the full Windows
  ColorDialog when needed.
- Explicit **OK / Cancel** so you can preview-then-confirm.

### Changed — Flag LEDs 3-left + 3-right layout
Cluttered single-row layout of v1.3.20 replaced with a 2-column grid :
- **◄ LEFT SIDE** : FL1 / FL2 / FL3
- **RIGHT SIDE ►** : FR1 / FR2 / FR3

Each slot lives in its own bordered card with checkbox / label / color
swatch / Test button / live dot / preset combo / property textbox. Much
easier to scan.

### Added — Bulk-apply helpers
- **Copy LEFT 3 → RIGHT 3** — mirrors left-side config to right side.
- **Spread FL1 → FL1/FL2/FL3** — replicates FL1 across the 3 left LEDs
  (e.g. ABS in pink on all 3 left LEDs in one click).
- **Spread FR1 → FR1/FR2/FR3** — same for the right.

### Added — In-UI explanation
Inline blue tip explaining how to map multi-LED events :
> *"Pour allumer 3 LEDs sur le MÊME event (ex : ABS rose sur FL1/FL2/FL3) :
> mets la même property + même couleur sur les trois slots. Pour 2 events
> séparés : ABS-rose sur les 3 gauche, TC-jaune sur les 3 droite. Pour un
> 3e event (Lift & Coast orange) : override 1 ou 2 slots."*

---

## v1.3.20 — Color wheel + Flag LEDs + redline flash color + race defaults (May 15, 2026)

### Added — Windows native color wheel
Every color picker in the plugin now opens the **Windows `ColorDialog`** :
- Full color wheel
- RGB sliders
- Hex input
- Custom colors palette (saved during the session)

Replaces the v1.3.19 popup-with-10-palette-dots which made it impossible to
find a specific hex. Applies to :
- All 15 RPM LED swatches
- The 6 Flag LED swatches (new)
- The redline flash swatch (new)

### Added — Redline flash color
The blue redline blink is now user-pick. New `RpmRedlineFlash` setting +
swatch under "Redline blink starts at" slider. Click → Windows color wheel.

### Added — 6 Flag LEDs bindable to any SimHub property
New "FLAG LEDS" section under the RPM bar customization. Each of the 6 slots
exposes :
- **Enable checkbox** — off by default, on to activate the LED
- **F1..F6 label**
- **Color swatch** — click → color wheel
- **Preset combo** — quick-pick : ABS Active / TC Active / DRS Enabled /
  DRS Available / Pit Limiter / Fuel Low Alert / Lift & Coast (LMU) /
  Engine Started / Speed Warning / Yellow Flag / Blue Flag / Black Flag /
  In Pit Lane
- **Property textbox** — free-text SimHub property path, can be ANY
  property (e.g. `GameRawData.LMUNativeTelemetry.generic.GPower`,
  `Maths.IsAbsActive`, a custom Calc, etc.)
- **Live indicator dot** — pill that fills with the chosen color while the
  property reads as truthy

The plugin reads each enabled property every telemetry tick. The LED is
considered "on" when the property is a true bool, non-zero number, or a
non-empty / non-"None" / non-"Off" string.

**Default bindings** :
```
F1 → ABS Active            → red
F2 → TC Active             → yellow
F3 → Lift & Coast (LMU)    → cyan
F4 → DRS Enabled           → green
F5 → Pit Limiter           → orange
F6 → Fuel Low Alert        → magenta
```

All slots start DISABLED so existing users don't see flickering LEDs they
didn't ask for — toggle each one ON to use it.

⚠ Physical LED indices on the Forte GT wheel are not yet wired — the
UI captures the state + lives in the SimHub properties, but the actual
HID command to light the 6 flag LEDs still needs reverse-engineering on
the wheel firmware. Coming in v1.3.21 once we've probed the indices.

### Changed — RPM default thresholds (race-friendly 3×3 grouping)
Jerome's race-tested preset, replacing v1.3.19's `70-98 %` linear spread
that left LEDs lit during race-pace cruise (70-80 % RPM).

```
LEDs L1-L3    : 78 %  (first warning)
LEDs L4-L6    : 81 %
LEDs L7-L9    : 84 %  (shift suggested)
LEDs L10-L12  : 87 %
LEDs L13-L15  : 90 %  (SHIFT NOW)
```

Bar stays DARK at 75-78 % cruise RPM ; lights up only in the shift window.
Reset button renamed **"Reset to race default (3×3)"**.

### Fixed — linear curve fallback respects RpmStartThreshold
When "Enable custom curve" is OFF, the wheel RPM bar used a pure linear
distribution (LED 1 at 6.7 % RPM = always on). Now applies the same
`RpmStartThreshold` floor as the wheelbase strips (default 75 %), so cruise
keeps the wheel bar dark regardless of curve mode.

### Internal
- Added `System.Windows.Forms` + `System.Drawing` references to `AsetekPlugin.csproj`
  so we can use `System.Windows.Forms.ColorDialog`.
- New AsetekManager fields : `RpmRedlineFlashR/G/B`, `FlagLedProperties[6]`,
  `FlagLedColorsR/G/B[6]`, `FlagLedEnabled[6]`, `FlagLedLive[6]`.
- SimHub plugin tick reads each enabled property and populates `FlagLedLive[]`
  for downstream consumers (UI live indicator dot, future HID push to wheel).
- JSON persistence : `RpmRedlineFlash`, `FlagLedProperties`, `FlagLedColors`,
  `FlagLedEnabled` arrays added to `ffb_settings.json`.

---

## v1.3.19 — RPM LED UX polish + Safety tab moved (May 15, 2026)

### Changed
- **Safety tab** moved to the right end of the left tab row (between
  "Controls (Beta)" and the right-aligned Debug tab). Was previously
  sandwiched between FFB Settings and Wheel, where it was easy to mis-click
  while moving between FFB-related panels.
- **Wheelbase Sound Effect Probe** trimmed from 8 buttons to the 4 audible
  IDs Jerome confirmed on his Invicta : **Beep 1, Beep 5, Beep 6, Beep 8**.
  IDs 2/3/4/7 are silent or reserved on the tested firmware — no point
  exposing them.
- **Notifications section** simplified to a single clearly-labeled toggle
  "Play sound on wheelbase state changes" with a precise description of
  what triggers it (HT enter/leave, Safe Mode entry, motor saturation).
  Resonance Reduction + Tracking Center Damping hidden until we have a
  documented user-observable effect — they're still in the underlying
  bitfield but no longer cluttering the UI.
- **Shift Beep wheelbase ID slider** snaps to the 4 audible IDs only.

### Fixed
- **Forte RPM LED default thresholds** raised so cruise (40-60 % RPM) no
  longer keeps the bar fully lit. New defaults : `70, 73, 76, 79, 82, 85,
  87, 89, 91, 93, 94, 95, 96, 97, 98` (all values are % of redline at which
  the LED activates). User can still customize each LED via the per-LED
  sliders or hit "Reset to linear" for the old behaviour.

### Added — per-LED RGB color picker (15 LEDs)
Replaces the 3-zone color UI of v1.3.18 with full per-LED control :

- **One swatch per LED** above each threshold slider (15 swatches total).
- **Left-click** on a swatch → popup with :
  - Palette of 10 colors : Off / Red / Orange / Yellow / Green / Cyan / Blue / Purple / Pink / White.
  - Hex input (ex : `FF8800`) with Apply button — full RGB control.
- **Right-click** on a swatch → copies the color to the system clipboard
  as `#RRGGBB`. Easy to paste elsewhere.
- **Middle-click** on a swatch → pastes from clipboard if a valid hex is
  present, else uses the last copied color.
- **"Apply L1 color to all"** button → propagates LED 1's color across all 15.
- **"Restore green→yellow→red"** button → resets to the classic shift-light
  gradient.

The per-LED colors are stored in `RpmLedColors[15]` (hex array in
`ffb_settings.json`). Legacy 3-zone keys (`RpmLedColor1/2/3`) are still
written for backward compat — a downgrade to v1.3.18 preserves the zone
colors that match LEDs 2/7/12.

### Architecture
- `RpmLedColorsR[15]` / `RpmLedColorsG[15]` / `RpmLedColorsB[15]` arrays in
  `AsetekManager`. The legacy `RpmLedColor{1,2,3}{R,G,B}` properties remain
  as compatibility shims (getters return the corresponding zone's LED 2/7/12,
  setters propagate to all 5 LEDs of that zone).
- `UpdateForteRpmLeds` now indexes the color array per-LED instead of
  bucketing into 3 zones.
- Forward-compatible JSON : new `RpmLedColors` array is preferred ; if
  absent, fall back to the three legacy `RpmLedColorN` keys.

### Coming next (v1.3.20)
- **6 Flag-LED bindings** : map each of the wheel's 6 flag LEDs to a SimHub
  property name (ABS, TC, lift_and_coast, fuel_low, drs_available, custom)
  with its own user-chosen color. Pending : confirm the physical LED
  indices on the Forte GT wheel.

---

## v1.3.18 — Safety tab + Universal Shift Beep + Custom RPM LED curve (May 15, 2026)

### New "Safety" tab — RaceHub parity + bonus
A dedicated tab between FFB Settings and Wheel. Hosts every feature RaceHub
exposes under its Safety + Notifications panels, plus a sound-effect probe to
discover the wheelbase buzzer IDs.

| Feature | What it does | Underlying register |
|---|---|---|
| Automatic Centering Strength | Spring to center when no game is grabbing FFB | `addr_desktop_spring_gain` (3) |
| Safe Mode | Auto-drop HT after N minutes of inactivity | `addr_standbys_settings` (22) |
| Hands-off Detection | Cut FFB momentarily when no driver resistance | `addr_simucube_options` (20) bits 0-1 |
| Sound Notifications | Wheelbase buzzer on HT change / saturation | `addr_simucube_options` bit 2 |
| Resonance Reduction | Kerb-vibration filter | `addr_simucube_options` bit 3 |
| Tracking Center Damping | Damping when off-center | `addr_simucube_options` bit 4 |

`addr_simucube_options` is a packed bitfield. We mirror RaceHub's
`PrepareSimucubeOptions` layout discovered in
`_racehub_SimSportsWheelbase.cs:484-491`. Bit positions for the three booleans
are an educated guess (bits 2/3/4 in declaration order) — the "Wheelbase Sound
Effect Probe" section below provides 8 test buttons to confirm empirically.

### Wheelbase Sound Effect Probe (BETA)
Discovered in `_racehub_WheelbaseCommService.cs:1025` : the Invicta has a
built-in piezo buzzer driven by SMP register `VAL_PLAY_SOUND_EFFECT = 6070`
(cmd 150 / `set_drive_params`). RaceHub uses it for HT-on/off and Safe Mode
chimes. We expose 8 trigger buttons so the user can probe IDs 1..8 and discover
the available effects on their base.

### Universal Shift Beep (works on ANY wheel)
A short audio cue triggered when engine RPM crosses a configurable threshold,
edge-triggered so it plays ONCE per shift approach (not continuously while
above redline).

Three routing options :
- **PC speakers** — default. Uses `MediaPlayer` so the volume slider works.
  Loads a user-chosen `.wav` (Browse... dialog), falls back to Windows
  Asterisk system sound if no file is configured.
- **Asetek wheelbase buzzer** — routes to `PlayWheelbaseSound(id)` with a
  user-selectable sound ID (1..8 probed in the section above).
- **Future** — wheel rim LEDs flash (already covered by the existing
  "Flash at Optimal Shift Point" in RaceHub's Shift Lights tab).

Persisted : enabled flag, RPM threshold, volume, route, wav path, wheelbase
sound ID.

### Forte GT RPM Bar — Custom Curve & Colors (BETA)
The wheel's 15-LED shift bar gets a real customization layer :
- **Per-LED RPM threshold** : 15 vertical sliders (1..100 %) — each LED lights
  up when its individual threshold is reached. Goes beyond RaceHub which forces
  a linear curve across all LEDs.
- **Per-zone color** : 3 click-to-cycle swatches (zone 1 = LEDs 1-5, zone 2 =
  6-10, zone 3 = 11-15). Palette : Green / Yellow / Red / Blue / White /
  Purple / Orange / Cyan / Pink. Full RGB internally — defaults to classic
  green/yellow/red.
- **Redline blink threshold** : slider 90..100 % — where the bar starts the
  blue redline flash. Default 97 %.
- **Reset to linear** button — restores the default 15-step linear curve.

The legacy linear behaviour is preserved by default — custom curve only kicks
in when the toggle is on.

### Architecture
- `AsetekManager` properties : `HandsOffDetectionLevel`, `TorqueSaturationSoundEnabled`,
  `ResonanceReductionEnabled`, `TrackingCenterDampingEnabled`, `AutoCenteringStrength`,
  `SafeModeTimeoutMin`, `ShiftBeepEnabled` and friends, `RpmLedCustomCurveEnabled`,
  `RpmLedThresholds[15]`, `RpmLedColor{1,2,3}{R,G,B}`, `RpmLedBlinkThreshold`.
- `PushSimucubeOptions()` recomposes the bitfield and writes via existing
  `WriteHardwareSettings` (cmd 122).
- `PlayWheelbaseSound(int id)` uses existing `SetSmpRegisters` to write reg 6070.
- `ShiftBeepTick(double rpm)` called from the 60 Hz telemetry loop. Edge-triggered,
  throttled by `ShiftBeepMinIntervalMs` (default 250 ms).
- `UpdateForteRpmLeds(rpmPct)` now consults `RpmLedThresholds[]` per-LED when
  custom curve is enabled, falls back to linear when off.

### Settings JSON additions
```
HandsOffDetectionLevel, TorqueSaturationSoundEnabled, ResonanceReductionEnabled,
TrackingCenterDampingEnabled, AutoCenteringStrength, SafeModeTimeoutMin,
ShiftBeepEnabled, ShiftBeepRpmThreshold, ShiftBeepVolume, ShiftBeepRoute,
ShiftBeepWheelbaseSoundId, ShiftBeepWavPath,
RpmLedCustomCurveEnabled, RpmLedBlinkThreshold,
RpmLedColor1, RpmLedColor2, RpmLedColor3,  (hex 6-digit strings)
RpmLedThresholds  (array of 15 floats)
```

---

## v1.3.17 — Low Torque Mode (safety / accessibility) (May 15, 2026)

### What this adds
A voluntary safety clamp on the wheelbase output. New section at the bottom
of the **Overview** tab, with an orange-bordered card titled "🛡 LOW TORQUE MODE"
that's impossible to miss.

When ACTIVE, the firmware's `main_gain` register is clamped so the wheelbase
never exceeds the user-configured Nm cap (default 6 Nm), regardless of slider
position. The slider stays where the user left it visually — Smart re-clamps
at every `SetOverallForce` call.

### Use cases
- Letting kids learn on a direct-drive base (27 Nm Invicta can sprain a wrist on a spin).
- Letting first-time guests drive your rig safely.
- Demo / showcase setups where many people will drive briefly.

### Disclaimer modals
Hardware safety is real on direct drive, so we force the user through a modal :
- **On first activation** — full disclaimer ("voluntary safety feature, kids/first-time guests, does NOT replace good driving habits"). Acceptance remembered after that.
- **Every deactivation** — short reminder ("output will jump back to ~X Nm, keep both hands on wheel"). NEVER suppressed — even if you've seen it 100 times, deactivating a safety feature deserves a beat of thought.

### Behaviour
- `ActivateLowTorqueMode(maxNm)` :
  - Snapshots the current Overall Force value (the user's "real" setting).
  - Sets `main_gain` so effective output ≤ `maxNm`.
  - Pushes single-addr `setprofiledata` immediately.
  - Persists in `ffb_settings.json` → survives restart.
- `DeactivateLowTorqueMode()` :
  - Restores the snapshotted Overall Force.
  - Pushes the restore via HID.
- `SetOverallForce(nm)` (any caller, any source) :
  - Silently downscales `nm` to `LowTorqueMaxNm` if Low Torque is active.

### UI affordances
- Orange chip in the section header : `ACTIVE — 6.0 Nm cap` or `OFF`
- Button colour switches : red-orange when active, green when inactive
- Slider 2 Nm … base max — to tune the cap (default 6 Nm)

### New SimHub properties
- `Asetek.FFB.LowTorqueMode` — bool, true if active
- `Asetek.FFB.LowTorqueMaxNm` — current cap value in Nm

Bind these to a dashboard chip so the active state is visible on the
overlay while driving — important if multiple users share the rig.

### Persistence
- `LowTorqueModeEnabled` survives restart (so a parent leaves Low Torque ON
  before handing the rig to a kid the next day).
- `LowTorqueMaxNm` persisted.
- `LowTorqueDisclaimerAccepted` persisted (first-activation modal only fires once per user setup).

---

## v1.3.16 — Smart Driving Mode (master toggle + N-lap learn gate) (May 15, 2026)

### What this adds
A single prominent **"Smart Driving Mode"** toggle in FFB Settings, above the
Advanced Diagnostic expander. It's the master gate for all per-segment
adaptive auto-tune features (currently Smart Slew v2, future Smart HF / Smart AO).

### The N-lap learn gate
When enabled, the algorithm spends the first **N laps** (default 5,
configurable 1–15) **recording per-segment clipping data without pushing
any HID changes**. After lap N completes, the map is committed and the
algorithm starts adjusting `slew_rate_limit` predictively as before.

Status text live in the UI :
- Off → `Off`
- Enabled, lap 0..N-1 → `Learning lap 3 / 5 on monza (no FFB change yet)`
- Enabled, lap ≥ N → `Active — learned 12 segments on monza`

### Closed-circuit ONLY (auto-gated)
The mode relies on SimHub publishing :
- `TrackId` (stable across the session)
- `CompletedLaps` (incrementing every crossed start/finish)
- `LapDist` or `TrackPositionPercent × TrackLength` (lap distance in m)

None of those are reliable on :
- Rally stages (point-to-point, lap stays at 1)
- Open-world maps (Dakar, free exploration — no lap concept)
- Free-roam practice (lap counter may not advance)

The plugin auto-detects "no lap progression" by watching `CompletedLaps`
and **parks Smart Driving in the learn state forever** in those contexts.
Enabling the toggle outside a track is harmless — it just never commits.

UI carries a yellow warning chip explaining the limitation.

### Implementation
- Master toggle `SmartDrivingEnabled` persisted in `ffb_settings.json`.
- `SmartDrivingMinLaps` slider (1–15 laps).
- `SmartSlewTickV2` now takes `currentLap` and gates HID writes behind a
  `commitAllowed = SmartDrivingEnabled && completedLaps >= minLaps` flag.
- Per-track lap counter resets on TrackId change.
- Status string `SmartDrivingStatus` reflects state for SimHub property
  binding (`Asetek.FFB.SmartDrivingStatus`).

### New SimHub properties
- `Asetek.FFB.SmartDrivingEnabled` — bool
- `Asetek.FFB.SmartDrivingActive` — bool (= committed phase, post-gate)
- `Asetek.FFB.SmartDrivingCompletedLaps` — int
- `Asetek.FFB.SmartDrivingStatus` — string for dashboard overlays

### Philosophy
The user puts their sliders where they LIKE the FFB. Smart Driving never
raises above those values — it only lowers locally on segments where the
firmware would slew-clip. So the "max FFB feel" the user dialed in is
preserved on every smooth section ; the algorithm only intervenes where
the firmware physically cannot deliver the requested ramp.

---

## v1.3.15 — Smart Slew v2 : predictive per-section, self-learning (May 15, 2026)

### Why v1.3.14 wasn't enough
v1.3.14 was reactive : "if slew clipping ≥ 12 % sustained 3 s, lower slew". The
problem in practice : you take the carrousel, it oscillates for 3 s, *then* the
plugin lowers slew, *then* you exit. Next lap we raise it back, same kerb, same
3 s of oscillation. Not a learning curve, just a loop of suffering.

### How v1.3.15 fixes it
Per-track segmentation + look-ahead :

1. **50 m buckets** indexed off SimHub's `LapDist` (or `TrackPositionPercent × TrackLength`).
2. **Per-segment learned target** : each time slew clipping is detected while
   in segment N, that segment's `TargetNmPerMs` drops 0.3 Nm/ms (clamped to
   Smart Slew Floor). Clean passes through a learned segment drift it back
   up 0.05 Nm/ms every 3 visits — so a line change auto-uncools old hot
   spots and lets new ones cool down.
3. **Predictive push** : at each tick we look 1 segment ahead. If segment N+1
   has a learned target lower than the current hardware slew, we push that
   target NOW via single-addr `setprofiledata` — so we enter the problem
   zone already filtered, not 3 s into the oscillation.
4. **Per-track persistence** : map auto-saves every 30 s while driving to
   `%APPDATA%\AsetekPlugin\trackmaps\<trackId>.json`. Next session at the
   same track loads it instantly — no re-learning.

### Baseline anchor
The user's manual slew slider is the **ceiling** of the auto-tune envelope.
Smart Slew **only lowers, never raises above it**. The "Smart Slew Floor"
slider sets the lowest value the algorithm is allowed to push (default
0.9 Nm/ms — Chris's bumpy preset). This guarantees the FFB stays inside
the envelope the user explicitly chose.

### UI
- "Smart Slew v2 — Predictive per-section (BETA)" section in the Advanced
  Diagnostic expander.
- **Reset Track Map** button — clears learned segments for the current track
  (use when changing car or after a major game patch).

### New SimHub properties
- `Asetek.FFB.SmartSlewTrackId` — currently loaded map id
- `Asetek.FFB.SmartSlewCurrentSegment` — int index, current 50 m bucket
- `Asetek.FFB.SmartSlewLearnedSegments` — int count of segments with HasLearned == true
- (existing `SmartSlewLastReason` / `SmartSlewLastTargetNmPerMs` reused)

### Removed
- Reactive 5-second cooldown auto-tune from v1.3.14 (replaced by predictive).

---

## v1.3.14 — Smart Slew Auto-tune (BETA, superseded by v1.3.15) (May 15, 2026)

### Why this exists
Chris (community) hit slew-rate-induced oscillation on Nordschleife Döttinger
Höhe in iRacing 360 Hz mode. Asetek's own advice : lower the slew rate. But a
lower slew kills cornering signal detail. RaceHub's only answer is "tune it
manually per track" — there's no feedback loop. Now there is.

### Added — Smart Slew Auto-tune
The plugin watches the live `Asetek.FFB.SlewClippingPct` and
`SmoothedRoughnessNm` metrics (both already published since v1.3.13) and
**adjusts the firmware's `slew_rate_limit` register in real time** :

| Trigger | Action |
|---|---|
| Slew clipping ≥ 12 % sustained 3 s | Lower slew by 0.5 Nm/ms (immediate fix) |
| Slew clipping ≤ 2 % AND roughness < 2 Nm sustained 10 s | Raise slew by 0.3 Nm/ms (reclaim detail) |
| Otherwise | Hold |

Global 5-second cooldown between any two adjustments to prevent flapping.
Clamped between user-configurable floor (default 0.9 Nm/ms — Chris's bumpy
preset) and ceiling (default = detected base's max slew rate).

The change is pushed via a single-addr `setprofiledata` to `slew_rate_limit` —
immediate firmware effect, no flash write, no PEAK degradation risk.

### UI
New section in **FFB Settings → Advanced Diagnostic** expander, just below
the existing Software Slew Limit slider :
- Checkbox **"Enable Smart Slew Auto-tune"** (off by default — BETA flag)
- **Smart Slew Floor** slider (0.1 .. detected base max)
- **Smart Slew Ceiling** slider (0.5 .. detected base max)

Persisted in `ffb_settings.json` as `SmartSlewEnabled` / `SmartSlewMinNmPerMs`
/ `SmartSlewMaxNmPerMs`.

### New SimHub properties
- `Asetek.FFB.SmartSlewEnabled` — bool
- `Asetek.FFB.SmartSlewLastReason` — string ("Slew clip 18% sustained → lowering 5.0→4.5 Nm/ms")
- `Asetek.FFB.SmartSlewLastTargetNmPerMs` — last value the tuner pushed

Bind these to a dashboard widget for a live "FFB engineer" overlay that
narrates the auto-tune decisions.

### Why this is "beyond RaceHub"
RaceHub gives you sliders. We close the loop : measure → decide → write. The
user doesn't have to know what slew rate means, doesn't have to remember
which track was bumpy. The plugin adapts continuously, section-by-section.

---

## v1.3.13 — Beyond RaceHub : TRUE clipping detection (slew + sustained) (May 15, 2026)

### Why this exists
RaceHub shows you sliders. v1.3.13 tells you **which slider is wrong and why**.
The whole point of having reverse-engineered the firmware down to the slew rate
register is that we can now do something RaceHub can't : detect, in real time,
both kinds of clipping the firmware can apply, and translate the diagnostic
into a single actionable line of text.

### Added — true-clipping detection suite

The plugin now distinguishes the two firmware-level clipping modes :

- **Magnitude clipping** — `|torque| ≥ 95 %` of `mainGain% × baseMaxNm`. Already
  tracked, now upgraded with a duration filter : a single-tick spike (kerb hit)
  no longer counts ; the clip must last ≥ 30 ms to flag as `SustainedMagClipping`.
- **Slew clipping** — sample-to-sample `|delta|` exceeds what the hardware
  `slew_rate_limit` register can pass through. The firmware caps the ramp so
  the wheel's actual torque follows a linear ramp instead of the requested
  step. **This is the clipping the user feels but can't see** : muted bumps,
  vague kerb response, even when the magnitude bar isn't pegged. We compute
  the threshold deterministically from the slew register we ourselves wrote.

### New properties (all under `Asetek.FFB.*`)

| Property | Meaning |
|---|---|
| `SlewClipping` | bool — slew-saturating *right now* |
| `SlewClippingPct` | int — % of last 60 s in slew clipping |
| `SlewClippingEvents` | int — distinct slew-clip events in last 60 s |
| `IsTrueClipping` | bool — composite live indicator (sustained mag OR slew ≥ 12 %) |
| `SustainedMagClipping` | bool — magnitude clip lasting ≥ 30 ms |
| `HeadroomNm` | double — Nm before wheel pegs (negative = over) |
| `HeadroomPct` | double — headroom as % of `maxNm` |
| `Suggestion` | string — one-line actionable advice, updated every 5 s |

### Suggestion engine

A 5-second-debounced helper translates the rolling stats into one of :

- `⚠ Slew clipping X% — raise Torque Acceleration Limit (bumps/kerbs being smoothed)`
- `⚠ Magnitude clipping X% — lower Overall Force by ~10% or reduce game's FFB strength`
- `⚠ Mag X% + Slew Y% — game FFB strength too high, reduce it first`
- `💡 Peak only X% of base — you can safely raise Overall Force for more feel`
- (empty when nothing to act on)

Bind `Asetek.FFB.Suggestion` to any Dash Studio text element and you get a live
FFB doctor in your dashboard.

### Why this matters
Jerome reported clipping in cornering that v3.3.37's clipping detector (in SRE)
didn't catch — because that detector only looked at SteeringTorque magnitude
drops. The real clipping was slew-clipping : the game's high-frequency content
exceeded the configured `slew_rate_limit` and got rate-limited. With v1.3.13
we now flag that explicitly.

---

## v1.3.12 — TRUE RaceHub-equivalent FFB (slider scaling fixes) (May 14, 2026)

### Why this version matters
Calibrated against Jerome's `LMU 900 mini` (all sliders at 0 %) and `LMU 900 maxi`
(all sliders at 100 %) RaceHub XML reference presets. Before this fix, **5 sliders
were silently mis-scaled** — users were getting a tiny fraction (or in one case, 5×
too much) of the FFB effect RaceHub would deliver for the same nominal slider
position. This is the version that makes our plugin's FFB feel bit-for-bit identical
to RaceHub's.

### Fixed — silent slider scaling bugs

| Slider | Old behaviour | Real firmware range | Fix |
|---|---|---|---|
| **Damping** | 100 % UI → fw 100 | 0-300 | × 3 — users were getting ⅓ of real Damping |
| **Friction** | 100 % UI → fw 100 | 0-250 | × 2.5 — users were getting 40 % of real Friction |
| **Inertia** | 100 % UI → fw 100 | 0-300 | × 3 — users were getting ⅓ of real Inertia |
| **Cornering Force Assist** | 100 % UI → fw 100 | 0-4000 | × 40 — **users were getting 2.5 % of the effect** |
| **Anti-Oscillation** | 100 % UI → fw 100 | 0-20 | × 0.2 — **users were getting 5× too much**, likely cause of "weird" cornering feel |
| **HF Limit** | UI Hz sent raw | fw 0-2500 | non-linear remap (UI 100 Hz → fw 0, UI 4700 Hz "No Limit" → fw 2500) |

### Architecture
- New `UiToFw(addr, ui)` / `FwToUi(addr, fw)` helpers in `AsetekManager`.
- `_paramCache` and `profile.Settings` JSON now consistently store **UI units**
  (0-100 %, UI Hz, etc.). Scaling is applied once, at HID-write time inside
  `ApplyAllCoreSettings.V()`.
- Auto-migration on load : profiles imported by previous plugin versions held
  firmware-raw values (Damping=300, Cornering=4000…). `MigrateLegacyFwValueIfNeeded`
  detects any scaled-addr value > 100 and down-scales it back to UI units. One-shot,
  runs in both `LoadProfiles` and `LoadSettings`.
- `BuildRaceHubXml` (our mirror export) up-scales UI → fw so the file stays
  drop-in compatible with RaceHub's own exports.
- "Compare RaceHub Presets" dump now shows XML values in UI units (auto-converted
  from fw) so the comparison is apples-to-apples against the plugin cache.

### Changed
- `SetHighFrequencyLimit(hz)` cache convention : 100 Hz (min) to 4700 Hz (= "No Limit"),
  no more "0 = No Limit" sentinel.
- **`damper_gain` / `friction_gain` / `inertia_gain` now forced to RaceHub canonical
  defaults** (15 / 15 / 0) at HID-write time, regardless of any stale value in
  `ffb_settings.json`. These 3 addrs are firmware constants RaceHub always pins —
  confirmed across 45 XML preset exports. Our previous defaults (0 / 20 / 10) were
  the residual reason the FFB could feel slightly different from RaceHub even with
  the same slider %.
- `_paramCache` default for `ioni_lpf` : was fw 0 (legacy "No Limit" sentinel), now
  UI 4700 (matches the v1.3.12 cache convention).
- Dump header version string now reads `v1.3.12` (was hardcoded to `v1.3.11`).
- HF slider UI : max value 4800 → 4700, label switches to "No Limit" at the max
  position. `SavedHfLimit` defaults to 4700 instead of 4800.
- Auto-tune engine : `IoniLpf = 0` (= No Limit) replaced by `IoniLpf = 4700` for
  consistency with the new UI-unit cache convention.

### Calibration data (firmware values from XML, all `Invicta`)
```
LMU 900 mini   : Damp=0    Fric=0    Iner=0    AO=0    Corn=0    HF=0    Slew=100
LMU 900 maxi   : Damp=300  Fric=250  Iner=300  AO=20   Corn=4000 HF=2500 Slew=9400
```

---

## v1.3.11 — Compare RaceHub Presets diagnostic + fixed Import (May 14, 2026)

### Fixed
- **"Import RaceHub Presets" button** now scans `Documents\RaceHub Profiles\Wheelbase\`
  **recursively** instead of only the `Backup\` subdir. RaceHub puts freshly
  saved presets at the root of `Wheelbase\` (live profiles) and only rotates
  older ones into `Backup\` — so the previous import path missed any preset
  the user had just exported. Jerome's `LMU 900test` was invisible because
  of this.
- Skips our own mirror exports (filename contains `"Asetek Plugin Backup"`)
  so the import doesn't duplicate plugin-written files.

### Added
- **"Compare RaceHub Presets" button** (Debug tab) — reads every XML preset
  RaceHub has auto-exported to
  `%USERPROFILE%\Documents\RaceHub Profiles\Wheelbase\` (recursive) and dumps a
  side-by-side table vs the plugin's live parameter cache.
  - One column per RaceHub preset, one row per slider (HF Limit, Damping,
    Friction, Inertia, Anti-Osc, Cornering, Bumpstop, Slew Rate, plus all
    secondary `*_gain` channels).
  - Cells marked `*` mean the preset's firmware value differs from the
    plugin's live cache → that slider's direction / scale is wrong.
  - Output copied to clipboard + saved under `%APPDATA%\AsetekPlugin\diag\`.

### Why
- User reported HF Limit slider felt inverted (UI "No Limit" gave RaceHub
  display "100 Hz"). Rather than guess slider-by-slider, this tool reads the
  canonical firmware values RaceHub itself writes for each saved preset.
  Workflow : load preset A in RaceHub → Save (forces XML export) → close
  RaceHub → push the same UI values in our plugin → run Compare. Any row
  still marked `*` is a mapping bug to fix.
- Goal : guarantee the FFB produced by our plugin is bit-for-bit identical
  to the FFB RaceHub would produce for the same named preset.

### Changed
- Reverted the experimental `ioni_lpf` inversion attempted in v1.3.10 (`hz <= 0
  ? 4700 : ...`) — the original mapping (`hz < 100 ? 0`) stays in place until
  the comparison tool confirms the correct direction empirically.

### Internal
- New `AsetekManager.DumpRaceHubPresetComparison(out filePath, out dumpText)`.
- Parses XML with `System.Xml.XmlDocument` (already referenced — no new deps).
- Strips `addr_` prefix on each `<Key>` to match `WheelbaseProfileAddr` enum
  names.

---

## v1.3.10 — Stop / Start Plugin button + Force Release HID (May 15, 2026)

### Added
- **⏸ STOP PLUGIN / ▶ START PLUGIN toggle button** in Overview tab (bottom row).
  - **Stop** : disconnects HID **AND** disables the 2s auto-reconnect loop. The
    plugin becomes fully passive — base stays free (RaceHub / other tools can
    grab it indefinitely).
  - **Start** : re-enables auto-reconnect, base reconnects within ~2s.
  - State **persisted across sessions** — if you stop the plugin, it stays
    stopped after a SimHub restart until you click Start.
- **Force Release HID button** — brutal HID handle close (no packets sent). Use
  only when normal Disconnect hangs because the firmware is unresponsive.

### Why
- Previous "Disconnect" did a clean teardown but the plugin's auto-reconnect
  loop would grab the wheelbase back within 2 seconds. Stop Plugin makes the
  pause persistent.

### Internal
- New `IsPluginStopped` flag + `StopPlugin()` / `StartPlugin()` methods.
- Auto-reconnect logic in `AsetekSimHubPlugin` now respects `IsPluginStopped`.
- Persisted under `"PluginStopped"` in settings JSON.

---

## v1.3.9 — La Prima PSU variant selector (May 14, 2026)

### Added
- **La Prima PSU variant dropdown** in Debug → Restore Factory Default panel.
  La Prima (12 Nm, 180W PSU) and La Prima+ (20 Nm, 350W PSU) share USB PID
  0xF303 — auto-detect cannot tell them apart. User picks the PSU variant :
  - La Prima — stock 180W PSU (12 Nm)
  - La Prima+ — high-power 350W PSU (20 Nm)
- Dropdown is **only visible** when La Prima is detected. Invicta and Forte
  have distinct PIDs so auto-detect remains reliable for them.
- Selection persisted across sessions (existing `LaPrimaHighPowerPsu` flag).

### Fixed
- Restore Factory Default on La Prima+ no longer writes 12 Nm values by mistake.
  Selecting "La Prima+" applies the correct 20 Nm / 400W factory targets.

### Internal
- New `IsLaPrimaDetected` property in `AsetekManager` (UI visibility helper).
- Re-uses existing `LaPrimaHighPowerPsu` flag — no new state introduced.

---

## v1.3.8 — Factory torque recovery & simplified Debug UX (May 13, 2026)

### Fixed
- **Reset Torque Limits now actually works.** The previous implementation wrote
  the SMP registers in test mode and called `restart_drive` — but the IONI motor
  controller reloaded from flash on restart, dropping our RAM-only writes back
  to the corrupted value. Now the sequence is :
  1. Enter test mode and **poll the SimuCubeStatus** until `test_mode == 22` is
     confirmed (RaceHub-style, was a blind 300 ms wait before).
  2. Write SMP_TORQUELIMIT_CONT / PEAK / MAX_OUTPUT_POWER / SYSTEM_CONTROL=1.
  3. **`save_to_flash` (cmd 4)** — the missing piece — persists the writes to
     IONI flash before the restart.
  4. `restart_drive` reloads the now-correct values.
  5. Read-back verifies the new peak matches the factory target.
  Validated end-to-end on an Invicta : a slider lowered to 15 Nm in RaceHub
  (SMP_PEAK = 11545) is fully recovered to 27 Nm (SMP_PEAK = 20255), and the
  next RaceHub open shows the slider max at 27 Nm — no power-cycle, no manual
  steps.

### Changed
- **Renamed "Reset SMP Registers" to "Restore Factory Default"** in the Debug
  tab Advanced Recovery section. Same destructive action, friendlier name.
- **Removed the redundant "Restore High Torque" button** from the Debug tab
  recovery section. The Disconnect button on the Overview tab already triggers
  the same firmware cold-boot (which auto-re-enables High Torque) — no need
  for a duplicate explicit button in Debug. Replaced with a clear info banner :
  "After using RaceHub : close RaceHub completely, then click Disconnect on
  the Overview tab."

### Added
- **Dump Diagnostic — "Last Reset SMP trace" section.** Captures the full
  step-by-step log of the last Restore Factory Default operation (test_mode
  entry, write outcomes, pre-restart verify, save_to_flash, post-restart
  verify). Survives subsequent dumps for after-the-fact debugging.
- **STM32 hardware settings read.** Dump now includes a "Wheelbase hardware
  settings (STM32 flash)" section listing the values stored in the wheelbase
  STM32 firmware flash — including `addr_max_motor_current`, the motor-current
  cap that drives the slider max in RaceHub. Reverse-engineered from RaceHub
  Assembly-CSharp.dll (cmd 110 `requesthwdata` / reply cmd 120).

### Notes
- A `RestoreFactoryMaxMotorCurrent()` API method and the
  `Asetek.Wheelbase.RestoreMaxMotorCurrent` SimHub action remain in the
  codebase for power-user scripting, but the dedicated UI button was removed —
  *Restore Factory Default* already synchronises `max_motor_current` to the
  factory value via the `save_to_flash` step.

---

## v1.3.7 — STM32 hardware settings read & restore (May 13, 2026)

### Added
- **Wheelbase hardware settings read.** The Dump Diagnostic now includes a
  "Wheelbase hardware settings (STM32 flash)" section listing the values
  stored in the STM32 firmware flash (distinct from the IONI SMP registers).
  Notable entry : `addr_max_motor_current` — the actual motor-current cap
  that drives the slider max in RaceHub. Reverse-engineered from RaceHub
  Assembly-CSharp.dll (cmd 110 / reply cmd 120).
- **Restore Factory Max Motor Current button** in Advanced Recovery
  (Debug tab). Writes the model-specific factory `max_motor_current` to
  STM32 flash via `sethwdata` (cmd 122). Use this if RaceHub shows the
  slider maxed-out at a Nm value below the model's factory peak — typical
  signature when a previous RaceHub Save persisted a sub-factory motor
  current. No power-cycle needed.
- New SimHub action : `Asetek.Wheelbase.RestoreMaxMotorCurrent` (bindable
  for power users or recovery scripts).

### Why this matters
The Asetek firmware caps deliverable torque at two independent layers :
1. **IONI motor controller** : `SMP_TORQUELIMIT_PEAK` (factory value per model).
2. **STM32 wheelbase firmware** : `addr_max_motor_current` (user-adjustable
   via the RaceHub Overall Force slider Save flow).

The plugin already handled layer 1 (Reset SMP Registers). Layer 2 was
invisible until this release — so a base could show factory SMP regs but
still deliver less torque physically because `max_motor_current` was below
the IONI's allowed peak. v1.3.7 closes that gap.

---

## v1.3.6 — Forte central encoders configuration (May 12, 2026)

### Added
- **New "Wheel (Beta)" tab** dedicated to the 3 central gold encoders on
  the Forte GT wheel. For each encoder (LEFT / CENTER / RIGHT) :
  - Choose a mode in the dropdown : **Incremental (+/-)**, **Switch — Latching
    (hold)** or **Switch — Pulse**. Modes are written to the wheel firmware
    over HID (reverse-engineered from RaceHub) and persisted to
    `%APPDATA%\AsetekPlugin\encoders.json`. Modes are re-applied automatically
    on every plugin startup.
  - Name the 12 switch positions (e.g. TC, ABS, BB, Diff, …) for use on
    dashboards.

  ![Wheel (Beta) tab — Forte central encoders](screenshots/wheel%20beta.png)

- **Live position tracking** per encoder, decoded from the Forte HID input
  report (memory : `forte_gt_hid_mapping.md`). Position name + number are
  exposed as SimHub properties for dashboards :
  - `Asetek.Encoder.{Left|Center|Right}.Mode` (string)
  - `Asetek.Encoder.{Left|Center|Right}.Position` (int : 1-12 in switch
    modes, 13 = CW pulse / 14 = CCW pulse in Incremental mode, 0 = idle)
  - `Asetek.Encoder.{Left|Center|Right}.PositionName` (user-defined name or
    fallback "Pos N", "+", "−")
- **Live HID debug** panel at the bottom of the Wheel tab : raw bytes from
  the Forte input report + decoded positions, useful to verify the byte
  mapping and confirm position reads.

### Workflow with SimHub Control Mapper
This release **does not create virtual buttons by itself** — the standard
way to use central-encoder positions in your game today is via SimHub's
built-in **Control Mapper** :

1. Set the encoder to **Switch — Latching (hold)** in the Wheel (Beta) tab.
   In this mode the wheel firmware holds a unique button (B32-B43 for LEFT,
   B46-B57 for RIGHT, B64-B75 for CENTER) for each of the 12 positions.
2. In SimHub Control Mapper, create chord bindings :
   `held button (= position) + your physical "+" button → keyboard key TC+`
   `held button (= position) + your physical "−" button → keyboard key TC−`
3. Use HID Hide to expose only the virtual buttons to the game.

A future v1.4 will add an integrated **vJoy bridge** so the same workflow
works plug-and-play without Control Mapper chords.

### Notes
- Confirmed central-encoder button ranges on the Forte GT firmware :
  LEFT incremental B44/B45, position B32-B43 ; RIGHT incremental B58/B59,
  position B46-B57 ; CENTER incremental B76/B77, position B64-B75.
- Mode setting via HID : `cmd 0x02 / group 0x50 / cmd 0x00 / rotaryIndex / mode`,
  reverse-engineered from `USB_SET_ROTARY_STATE_TYPE` in RaceHub's decompiled
  Assembly-CSharp.dll.

---

## v1.3.5 — Slider live sync + enriched diagnostics (May 12, 2026)

### Fixed
- **Slider/firmware desync.** Sliders are now the source of truth : every
  movement commits the new value to the plugin cache AND pushes it to the
  wheelbase RAM immediately, instead of waiting for a Save to Wheelbase
  click. Previously, importing a RaceHub preset (or any path that wrote to
  the cache) could leave the slider visual showing one value while the
  firmware ran with another — typical signature : slider at 18 Nm, dump
  reports `main_gain=75%`, wheelbase actually delivers 13.5 Nm. Live RAM
  push only — no flash write, so SMP_PEAK stays protected.

### Added
- **Plugin profile cache section in Dump Diagnostic.** The dump now includes
  a "Plugin profile cache (live in-memory values)" block with the current
  values for Overall Force, Steering Range, HF Limit, Torque Accel Limit,
  Mechanical Feel sliders, Torque Shaping, Bumpstop & Cornering, plus the
  active profile name and auto-match flag. Useful to spot at a glance any
  mismatch between what the sliders show and what the wheelbase actually
  runs with.
- **More live in-game tuning bindings.** New *MECHANICAL FEEL* section in
  the Controls (Beta) tab with +/- 5 % bindings for Damping, Friction,
  Inertia and Anti-Oscillation. Bind them to wheel keys to adjust those
  parameters on the fly while driving — same workflow as the *Torque
  Shaping* bindings from v1.3.4. Sliders reflect the live value, one
  Save to Wheelbase persists the setup.

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
