# Asetek Control — Changelog

> All notable changes to this plugin will be documented in this file.

---

## v1.0.3-beta — FFB rewiring, profile auto-match & quality of life (April 25, 2026)

This release is a major iteration. It fixes a long-standing FFB mapping bug, rewires the slider plumbing, and adds a full profile system tied to the running game and car. All work was done after decompiling RaceHub 4.4.3's `Assembly-CSharp.dll` and cross-checking against 11 RaceHub XML preset exports.

### Fixed (CRITICAL)

- **Damping / Friction / Inertia / Anti-Oscillation sliders now write the correct hardware addresses.** Previous versions wired these UI sliders to firmware-constant registers (`damper_gain`, `friction_gain`, `inertia_gain`) that don't drive the FFB feel — moving the sliders had no perceptible effect. The mapping is now confirmed against the decompiled RaceHub source:
  - `Damping` → `ioni_damping` (was `damper_gain`)
  - `Friction` → `ioni_friction` (was `friction_gain`)
  - `Inertia` → `ioni_inertia` (was `inertia_gain`)
  - `Anti-Oscillation` → `latency_comp_factor` (was `ioni_damping`)
- **APPLY & SAVE only persisted 8 of the 12 FFB sliders.** The Torque Prediction, Torque Accel Limit, Cornering Force Assist and Bumpstop Hardness sliders were silently dropped before this release.
- **The per-profile "Save" button silently lost slider edits.** It called `LoadProfile()` *before* `SaveCurrentToProfile()`, overwriting the user's current sliders right before saving. Now it commits sliders to cache, then writes the cache to the target profile.

> **Migration note** — profiles saved with v1.0.2-beta or earlier still hold the Damping / Friction / Inertia / Anti-Oscillation values in the wrong addresses. After upgrading: re-set those four sliders manually, or re-import your RaceHub presets.

### Added — Wheel utilities

- **"RE-CENTER WHEEL"** button on the FFB Settings tab. Sends `set_wheel_center_here` + `save_to_flash` so the new zero point survives a power cycle. Useful after swapping rims when the wheel keeps trying to rotate to the previous center. Also exposed as the `Asetek.RecenterWheel` SimHub action — bindable to a button on a wheel or button box from the Controls tab.
- **"↻ RELOAD PRESET"** button. Discards unsaved slider edits and restores the active profile's saved values.
- **"Standstill Damping"** toggle (Game Integration). Auto-boosts `ioni_damping` to 95 % at slow speed (under 13 km/h) to kill wheel oscillations in pits / on grid / pit lane, then restores the user's normal value at racing speed (above 15 km/h, 2 km/h hysteresis prevents flicker).

### Added — Profile system

- **Auto-match profile by game / car class / car id.** Every profile gains optional `Game`, `CarClass` and `CarId` tags. When the toggle is enabled (Overview tab), the plugin auto-loads the best-matching profile when the active sim or car changes. Match priority: exact `(game, carId)` → `(game, carClass)` → carId-only → carClass-only → game-only.
- **Smart toggle behaviour**: turning auto-match on when no profile matches the current game/class auto-creates a profile from your current sliders and tags it for you.
- **"Quick save → by Car Class" / "by Car (specific)"** buttons (FFB Settings tab). One-click profile capture from your current sliders, auto-named and auto-tagged from the running sim:
  - by Class: e.g. `LMU GT3`, tagged `Game=LMU CarClass=GT3` (covers every GT3 in LMU)
  - by Car: e.g. `LMU GT3 - United Autosports 2025`, tagged with the specific `CarId`
- **Live "Detected:" status line** above the Quick Save buttons that previews the names that will be created before you click — refreshed every second.
- **"Load" / "Tag" / "Edit"** buttons on every profile row. Tag auto-fills from the running sim; Edit opens an inline editor for Game / CarClass / CarId (empty field = match anything).
- **"Save current sliders to…"** dropdown on the FFB Settings tab. Pick any profile and write your current slider values to it without applying to the wheelbase — useful for fine-tuning incrementally.

### Added — Import / backup

- **"Import RaceHub Presets"** button. Scans `%USERPROFILE%\Documents\RaceHub Profiles\Wheelbase\Backup\` and imports every XML preset auto-exported by RaceHub as a plugin profile. Auto-tags the `Game` field heuristically from the preset name (LMU, iRacing, ACC, RFactor2, AMS2, EAWRC, Dakar, Kart). Skips profiles whose name already exists. **Note:** RaceHub appears to only auto-export those XML files on a major version upgrade — they reflect the preset state at the time of export, not your current RaceHub configuration.
- **RaceHub-format XML mirror.** Every profile save also writes `Plugin - <Name> - Asetek Plugin Backup.xml` to `Documents\RaceHub Profiles\Wheelbase\Backup\` as a redundant readable backup alongside the plugin's `profiles.json`.

### Discoveries (RaceHub 4.4.3 reverse engineering)

- `addr_reserved_ui_simple_1` (26) is **not reserved** — it's a packed bitfield holding the four Simple Mode values (MainGain / SteeringRange / Smoothing / Damping, 8 bits each).
- `addr_profile_settings_bits_1` (28) is a bitfield: bit 0 = `SimpleMode` flag, bit 1 = `Dirty` flag.
- The "profile hash" sent via cmd `0x7F` is the profile's GUID in little-endian, not an arbitrary content hash.

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
