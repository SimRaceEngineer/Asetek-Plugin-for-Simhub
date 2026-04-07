# Asetek Control — Changelog

> All notable changes to this plugin will be documented in this file.

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
