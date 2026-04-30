# Asetek Control — Changelog

> All notable changes to this plugin will be documented in this file.

---

## v1.0.17-beta — Forte / La Prima Overall Force scale fix (April 30, 2026)

### Fixed

- **Forte and La Prima users : Overall Force slider now hits the full
  base peak.** The previous code computed `main_gain = nm / 27 × 100`,
  using the Invicta scale (27 Nm) for every base. On a Forte (18 Nm
  factory) that capped the slider's effective output at `18 / 27 = 67 %`
  — the firmware then re-aligned `SMP_TORQUELIMIT_PEAK` to 67 % of factory
  (≈ 12 Nm flashed instead of 18 Nm) any time `SetOverallForce` was called
  with the slider at full. Same effect on La Prima (12 Nm or 16 Nm with
  high-power PSU). The fix uses the detected base's own factory peak so
  100 % on the slider always means 100 % on the firmware.
- Same correction applied to the live `Asetek.FFB.MaxTorqueNm` and
  utilisation / clipping metrics so they report against the correct
  ceiling on Forte / La Prima.

### How to recover (Forte / La Prima users still capped after v1.0.16-beta)

The fix removes the source of the capping, but a base that was already
flashed at 67 % needs a Reset Torque Limits to come back to factory peak :

1. Update to v1.0.17-beta (overwrite `AsetekPlugin.dll` in your SimHub
   folder).
2. Asetek Control → Overview → ▶ Advanced.
3. Click **Reset Torque Limits** → confirm.
4. Click **Restore High Torque** if HT bit is OFF.
5. Power-cycle the wheelbase (off / on).
6. **Cold-Start Diag** — should now read SMP_TORQUELIMIT_PEAK = 13503
   (~18 Nm Forte), 9002 (~12 Nm La Prima stock) or 12003 (~16 Nm La Prima
   with high-power PSU). On Invicta : 20255 (~27 Nm).
7. Adjust Overall Force from the FFB tab to taste — at 100 % you now get
   the real factory peak of your model.

---

## v1.0.16-beta — PEAK torque drift eliminated + Cold-Start Diagnostic (April 30, 2026)

This is a major reliability release. Several PEAK-torque drift issues that
could leave a wheelbase delivering less force than configured (sometimes
session after session) are now fixed at the root. The plugin no longer pushes
`main_gain` (the Overall Force slider value) to the firmware in routine apply
paths — only deliberate user actions can change the flash baseline.

### Critical fixes — PEAK torque stability

- **No more drift between SimHub sessions.** Loading a profile, auto-matching
  to a game, recentering the wheel, or simply restarting SimHub no longer
  causes `SMP_TORQUELIMIT_PEAK` to drift down. Earlier versions pushed
  `main_gain` on every apply, and the firmware applied a `PEAK *= main_gain/100`
  rescale on each push — over a few sessions this eroded the maximum torque
  visibly (Invicta dropped from 27 Nm to ~20 Nm in some test cycles). The
  routine apply path now omits `main_gain` entirely; the firmware keeps its
  current value untouched, so the slider's effect on PEAK is bounded and
  intentional.
- **Apply &amp; Save no longer double-scales PEAK.** The save-to-flash sequence
  used to send the settings batch twice before flushing (mimicking RaceHub).
  Because each batch triggered the firmware's PEAK rescale, two sends with
  `main_gain = 81 %` ended up persisting `PEAK × 0.81² = 0.66`. The save now
  uses a single batch pass — one rescale, the result the user actually
  intended.
- **Recenter Wheel and Load Factory Center no longer write to flash.** Both
  are now runtime-only (the wheel center is re-applied at the next session by
  the user). Eliminates two paths that previously persisted whatever
  `main_gain` happened to be in RAM, sometimes shrinking PEAK on every click.
- **Reset Torque Limits restores factory peak reliably.** The button now
  pushes `main_gain = 100 %` to the firmware before writing the factory SMP
  registers, so the firmware's auto-rescale doesn't immediately undo the
  reset. After clicking, the Overall Force slider reads 100 % — adjust it to
  taste from the FFB tab.

### Added

- **Cold-Start Diagnostic button** (Overview → Advanced). Refreshes the HID
  handle and dumps the firmware's current state — SMP torque limits in
  Nm, High Torque bit (read from `request_status` byte 12), challenge probe.
  The dump is written to a timestamped file under
  `%APPDATA%\AsetekPlugin\diag\` and copied to the clipboard so it can be
  pasted directly into Discord support threads. Equivalent of the standalone
  Python diagnostic, integrated in the plugin.
- **Auto-Cold-Start-Diag at startup and on Reconnect.** The Overview tab
  populates with the current wheelbase state automatically — no need to
  click any button to see if PEAK / HT / SMP regs are healthy.
- **Advanced section** (collapsible) on the Overview tab. Hides the recovery
  &amp; diagnostic buttons (Reconnect / Disconnect / Reset Torque Limits /
  Restore High Torque / Dump Diagnostic / Cold-Start Diag) by default — the
  default UI stays clean for normal use, the advanced controls are one click
  away when needed.
- **Live FFB slider values exposed as SimHub properties.** Damping, Friction,
  Inertia, Anti-Oscillation, Torque Prediction, Slew Rate, HF Limit,
  Cornering Force Assist, Bumpstop Hardness / Range — all now publish their
  current value as `Asetek.FFB.*` properties for dashboards. `OverallForce`
  is in Nm (= `main_gain × MaxTorque` of the detected base).
- **`Asetek.FFB.TorqueSourcePath` debug property.** Tells you which SimHub
  property the live torque metrics are reading from (iRacing 360 Hz array,
  iRacing scalar, LMU shared memory, NeoRed LMU plugin, ACC physics).

### Changed

- **High Torque bit detection** uses the firmware status report (byte 12, bit 1)
  instead of the legacy challenge probe. The status byte is invariant across
  reads; the challenge gets regenerated by the firmware after every
  interaction and is therefore noisy. Both indicators are still shown in the
  diagnostic dump for cross-reference.
- **Restore High Torque** loop is now bounded (max 9 iterations) and verifies
  success via the status byte rather than the challenge value. Spinning
  forever is no longer possible if the base is in a hard fault state — the
  plugin returns a clear error message asking for a USB power-cycle in that
  case.
- **HID I/O hardening.** The wheelbase read path now pins its buffer and
  overlapped structures during pending I/O. Eliminates a 0xc0000005 access
  violation that could crash SimHub during heavy diagnostic / recovery
  operations on long-running sessions.

### How to recover a wheelbase that's stuck at low torque

1. Open SimHub → Asetek Control → Overview → click **▶ Advanced** to expand.
2. Click **Reset Torque Limits** (confirms with a dialog).
3. Click **Restore High Torque** if the base is in safe mode (HT bit off).
4. **Power-cycle the wheelbase** via the USB cable or main power switch.
5. Click **Cold-Start Diag** — `SMP_TORQUELIMIT_PEAK` should now read
   `20255 (~27 Nm)` on Invicta, `14254 (~19 Nm)` on Forte, `9002 (~12 Nm)` on
   La Prima (or `12003 / 16 Nm` if the optional high-power PSU is enabled in
   FFB Settings).
6. Adjust Overall Force from the FFB Settings tab to taste.

### Acknowledgements

- Thanks to **@Uzurod** on Discord for the persistent Forte-cap reports that
  drove most of the v1.0.10 → v1.0.16 work, and to everyone who reported
  diagnostic dumps that helped triangulate the firmware's PEAK-rescale
  behaviour.

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
