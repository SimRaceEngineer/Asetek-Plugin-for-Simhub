# Asetek Control — SimHub Plugin for Invicta, Forte & La Prima

> **Beta Release — v1.3.1-beta**

A SimHub plugin that extends the Asetek SimSports ecosystem with **automatic per-game FFB profiles**, **True Steering Lock**, **in-game FFB adjustment via wheel buttons**, and **LED control** — all from within SimHub, using the exact same FFB engine and protocol as RaceHub.

---

## What this plugin does

Asetek RaceHub is the official companion software and delivers an excellent FFB experience. This plugin **does not replace RaceHub** — it builds on top of the same USB protocol to add workflow features that sim racers have been requesting:

1. **Per-game / per-car FFB profiles** — Save unlimited profiles and auto-load the right one when you switch sims or cars. No manual adjustment between sessions.
2. **True Steering Lock** — Automatically match the wheelbase steering range to the car you're driving (e.g., 380 for a Hypercar, 540 for a GT3).
3. **In-game FFB adjustment** — Change FFB strength directly from your wheel buttons while driving, without alt-tabbing.
4. **RaceHub XML import** — Import your existing RaceHub presets directly, so your tuned FFB carries over seamlessly.

The FFB values sent to the wheelbase are **strictly identical** to those sent by RaceHub — same addresses, same protocol, same firmware behavior. The plugin simply provides additional tools to manage and switch between them.

---

## Screenshots

### Overview — Detection & Profiles
![Overview](screenshots/overview.png)

Auto-detects your wheelbase model (Invicta / Forte / La Prima), reads firmware PEAK torque and High Torque status, and manages per-game profiles with one-click switching.

### FFB Settings — Full Parameter Control
![FFB Settings](screenshots/ffb%20settings.png)

All wheelbase parameters with sliders matching RaceHub values: Overall Force, Steering Range, Damping, Friction, Inertia, Anti-Oscillation, Torque Prediction, Slew Rate, HF Limit, Cornering Assist, Bumpstop. Quick-save buttons create profiles tagged by game, car, or track.

### Game-Change Banner
![Game Change Banner](screenshots/Banner%20game-change.png)

When SimHub switches to a new sim, the plugin auto-reconnects and loads the matching profile. A banner guides you if the base needs a physical button press.

### Editable Profile Combo
![Profile Combo](screenshots/Profile%20combo%20editable.png)

Type a new profile name to create it, or pick an existing one to overwrite — all from the same dropdown in FFB Settings.

### LED Control (Beta)
![LED Control](screenshots/Led%20control.png)

Center LED color and flag mode, Forte rev-light patterns driven by game telemetry.

### Controls — Button Mapping (Beta)
![Controls](screenshots/button%20Mapping.png)

Assign wheel buttons to any plugin action using SimHub native binding system.

---

## Features

### Confirmed Working

| Feature | Description |
|---------|-------------|
| **Auto base detection** | Enumerates VID_2433 on connect and auto-identifies Invicta / Forte / La Prima. Slider ceilings adapt to the detected base spec (12 / 16 / 18 / 27 Nm). |
| **Game-detect timer** | Polls DataCorePlugin.CurrentGame every 2s — profile loads as soon as SimHub detects a sim, even before telemetry flows. |
| **True Steering Lock** | Auto-syncs steering range from the game (LMU REST API + per-car CarClass detection). |
| **FFB Settings** | Full control of all wheelbase parameters — identical values to RaceHub. |
| **Per-game favourites** | Star a profile per game — the starred profile auto-loads on game launch. |
| **Auto-match profiles** | Profiles tagged with Game / CarClass / CarId auto-load when you switch sims or cars. |
| **RaceHub preset import** | One-click import of RaceHub XML presets from Documents\RaceHub Profiles\Wheelbase\Backup\. |
| **FFB Strength +/-** | Bindable SimHub actions — assign to wheel buttons for on-the-fly force adjustment. |
| **Steering Range / Force Presets** | Quick-switch between 360 / 540 / 900 / 1080 and Low/Med/High/Max force. |
| **Auto-reconnect** | Detects stale HID handles after game switches and reconnects automatically. |
| **RaceHub auto-pause** | Detects when RaceHub is running and auto-disconnects so the two apps never conflict. |
| **Firmware health monitoring** | Reads SMP_TORQUELIMIT_PEAK and High Torque status every 5s with degradation warnings. |
| **Reset Torque Limits** | Restores the base to factory torque configuration in one click. |

### Beta

| Feature | Description |
|---------|-------------|
| **Wheelbase Center LED** | Set color + flag mode (auto-coloured by race flags). |
| **Forte Rev Lights** | External control of the rev-light strip from game telemetry. |
| **Button Mapping** | Assign wheel buttons to any plugin action. |

---

## Supported Hardware

- **Asetek Invicta Wheelbase** (PID_F300) — 27 Nm peak
- **Asetek Forte Wheelbase** (PID_F301 / PID_F200) — 18 Nm peak
- **Asetek La Prima Wheelbase** (PID_F303) — 12 Nm peak (16 Nm with high-power PSU)
- **Asetek Forte GT Steering Wheel** (PID_F207)
- **Asetek Invicta Steering Wheel** (PID_F400)
- **Asetek Formula Forte Steering Wheel** (PID_F402)

The plugin auto-detects the model on connect and adapts the Overall Force ceiling. Other Asetek devices may enumerate but have not been tested — please open a GitHub issue with your PID if you have one to try.

---

## Installation

1. Download `AsetekPlugin.dll` from the [Releases](../../releases) page
2. Copy `AsetekPlugin.dll` into your SimHub installation folder (e.g., `C:\Program Files (x86)\SimHub\`)
3. Launch SimHub — the plugin appears as **"Asetek Control"** in the left menu

---

## SimHub Properties (for dashboard developers)

| Property | Type | Description |
|----------|------|-------------|
| `Asetek.WheelbaseConnected` | bool | Wheelbase detected |
| `Asetek.ForteConnected` | bool | Forte GT wheel detected |
| `Asetek.FFB.OverallForce` | double | Current overall force in Nm |
| `Asetek.FFB.CurrentStrength` | int | Current FFB strength (main_gain 0-100) |
| `Asetek.FFB.SteeringRange` | int | Current steering range in degrees |
| `Asetek.FFB.Damping` | int | Damping value (0-100) |
| `Asetek.FFB.Friction` | int | Friction value (0-100) |
| `Asetek.FFB.Inertia` | int | Inertia value (0-100) |
| `Asetek.FFB.SlewRate` | double | Torque Accel Limit in Nm/ms |
| `Asetek.FFB.HfLimit` | int | High Frequency Limit in Hz |
| `Asetek.FFB.IsClipping` | bool | FFB signal is clipping |
| `Asetek.FFB.CurrentTorqueNm` | double | Real-time torque output in Nm |
| `Asetek.FFB.TrueSteeringLock` | bool | True Steering Lock enabled |
| `Asetek.Profile.ActiveName` | string | Active profile name |
| `Asetek.Led.Mode` | string | Current LED mode |

---

## SimHub Actions (for button mapping)

| Action | Description |
|--------|-------------|
| `Asetek.FFB.Strength.Up` | Increase FFB strength |
| `Asetek.FFB.Strength.Down` | Decrease FFB strength |
| `Asetek.FFB.SteeringRange.360/540/900/1080` | Set steering range |
| `Asetek.FFB.Force.Low/Medium/High/Max` | Set force preset (% of detected base peak) |
| `Asetek.FFB.TrueSteeringLock.Toggle` | Toggle True Steering Lock |
| `Asetek.Profile.GameCycle.Next/Prev` | Cycle profiles for the current game |
| `Asetek.ApplyAndSave` | Apply current settings and save to flash |
| `Asetek.Reconnect` | Reconnect to devices |

---

## Known Limitations

- **True Steering Lock** currently only works with **Le Mans Ultimate / rFactor 2** (LMU REST API). Multi-sim support is on the roadmap.
- **LED features are in beta** — behavior may vary depending on firmware version.
- **Settings are not readable from the wheelbase** — the plugin persists your last settings locally. On first use, set all sliders to match your current RaceHub values, or import your RaceHub presets.

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "RaceHub is running — paused" banner | Expected. Close RaceHub then click Reconnect. |
| Wheelbase shows "Not detected" | Another app has the HID handle. Close RaceHub, click Reconnect. |
| RaceHub Overall Force slider stuck at low Nm | Click **Reset Torque Limits** in Overview, then power-cycle the base. |
| Settings don't apply | Click "Save to Wheelbase" — sliders only update the display until you save. |
| True Steering Lock shows "err" | Make sure LMU is running and in a session (not main menu). |

---

## Roadmap

- [x] Per-game / per-car auto-match profiles (v1.0.3)
- [x] Per-base torque and slew rate ceiling auto-detection (v1.0.5)
- [x] One-click factory recovery for corrupted SMP limits (v1.0.8)
- [x] Safe RaceHub coexistence — auto-pause + Disconnect/Reconnect (v1.0.8)
- [x] Per-game favourites with star system (v1.3.0)
- [x] Game-detect timer — profile loads before telemetry flows (v1.3.1)
- [x] SMP PEAK degradation protection (v1.3.1)
- [ ] Multi-sim True Steering Lock (ACC, iRacing, AMS2...)
- [ ] In-plugin High Torque Mode toggle
- [ ] LED patterns and animations
- [ ] Community-contributed profiles library

Feature requests and bug reports are welcome via [GitHub Issues](../../issues).

---

## License

MIT License — see [LICENSE](LICENSE) file.

---

## Support

If you like this plugin and want to support its development:

[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/simrace)

---

*Made with passion by a sim racer, for sim racers.*
