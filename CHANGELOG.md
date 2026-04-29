# Asetek Control — Changelog

> All notable changes to this plugin will be documented in this file.

---

## v1.0.8-beta — Torque-limit recovery + Disconnect button (April 29, 2026)

### Fixed (CRITICAL)
- **Wheelbase silently capped at low-torque safe limit after several Apply+Save cycles**
  (~7 Nm on Invicta, ~3 Nm on Forte, ~1 Nm on La Prima — visible even in RaceHub
  after closing SimHub). Root cause: v1.0.4 → v1.0.7 wrote `SMP_TORQUELIMIT_CONT`
  and `SMP_TORQUELIMIT_PEAK` on every `SetOverallForce` and `ApplyAllCoreSettings`,
  with values calculated against the Invicta-scale `TORQUE_CONSTANT` (1.333) and
  without the surrounding `goto_test_mode` / `SMP_MAX_OUTPUT_POWER` /
  `SMP_SYSTEM_CONTROL=1` / `restart_drive` sequence the motor controller actually
  expects. Eventually the IONI persisted those bogus limits in flash and the
  base stayed capped even when the plugin was uninstalled.
  - Both `SetOverallForce` and `ApplyAllCoreSettings` no longer touch
    `SMP_TORQUELIMIT_CONT/PEAK`. The Overall Force slider only writes
    `main_gain` (profile addr 3) now, like RaceHub does for the user-facing
    slider.
  - `goto_test_mode = 107` added to `WheelbaseUsbCommand` (needed by the new
    Reset path).
  - `WheelbaseSpec` extended with `ContTorqueNm` and `MaxOutputPower` so the
    Reset path knows the right values per model.

### Added
- **"Reset Torque Limits" button** (Overview tab → bottom row, next to
  Reconnect/Disconnect). Reproduces RaceHub's
  `CO_ChangeWheelbaseTorqueLimits` sequence (decompiled from RaceHub 4.4.4):
  `goto_test_mode` → write `SMP_TORQUELIMIT_CONT/PEAK/MAX_OUTPUT_POWER` and
  `SMP_SYSTEM_CONTROL=1` (one register per packet) → `restart_drive`. Restores
  the detected base to its factory torque limits in one click. Confirmation
  dialog before the write so it's not triggered accidentally. After the reset,
  power-cycle the wheelbase (USB unplug + replug) and verify in RaceHub that
  the Overall Force slider reaches the full peak.
  - Per-model factory values: Invicta peak 27 Nm / cont 19 Nm / power 950,
    Forte peak 18 / cont 14 / power 600, La Prima peak 12 / cont 10 / power 400
    (16 Nm peak when high-power PSU is enabled in plugin settings).
- **"Disconnect" button** (Overview tab, between Reconnect and Reset Torque
  Limits). Releases the HID handle without closing SimHub, so RaceHub or any
  other tool can take exclusive access. Mirrors the clean-shutdown sequence
  used in `Dispose` (`SMP_SYSTEM_CONTROL = 1` → `restart_drive` → 150 ms grace)
  so the firmware exits the plugin's session cleanly. Click "Reconnect"
  afterwards to reattach.

### Acknowledgements
- Thanks to **@Uzurod** on Discord for the bug report (Forte capped at 3 Nm /
  10.5 Nm) that triggered the investigation.
- Decompilation cross-checked against RaceHub 4.4.4 `Assembly-CSharp.dll`
  (`DeviceUpgradeMediator.CO_ChangeWheelbaseTorqueLimits`,
  `WheelbaseCommunicationService.ChangeRegisterValue`,
  `WheelbaseSMPRegisters` and `WheelbaseUsbCommand` enums).

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
