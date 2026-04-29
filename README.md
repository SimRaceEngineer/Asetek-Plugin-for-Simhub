# Asetek Control — SimHub Plugin for Invicta, Forte & La Prima

> **Beta Release — v1.0.8-beta**

A SimHub plugin that brings **direct FFB settings control**, **True Steering Lock**, **per-game / per-car profiles**, **LED control**, and a **safe RaceHub coexistence layer** to Asetek SimSports wheelbases and Forte GT steering wheels — all from within SimHub.

---

## ⚠️ IMPORTANT DISCLAIMER

**This plugin is an independent, community-driven project.**

- This plugin is **NOT affiliated with, endorsed by, or supported by Asetek SimSports** or any of its subsidiaries.
- This is a **beta release** — features may not work as expected on all configurations. **Use at your own risk.**
- This plugin communicates with Asetek hardware via the standard HID (Human Interface Device) protocol, the same USB interface used by any compatible software.
- **No warranty** is provided, express or implied. The authors are not responsible for any damage, misconfiguration, or unexpected behavior that may result from using this plugin.
- This plugin **may stop working** after a firmware update from Asetek.
- **RaceHub coexistence is now handled automatically** — the plugin detects when RaceHub is running and auto-pauses (releases the HID handle, greys out controls). You no longer need to close RaceHub manually before launching SimHub. A "Disconnect" button is also available to hand the wheelbase over on demand. See *Coexistence with RaceHub* below.
- By using this plugin, you acknowledge that you understand these limitations and accept full responsibility.

### Why this plugin exists

The goal of this plugin is to fill gaps that the official Asetek software (RaceHub) does not currently address yet:

1. **True Steering Lock** — Automatically match the wheelbase steering range to the car you're driving (e.g., 380° for a Hypercar, 540° for a GT3). No more manual adjustment between sessions. Works on LMU now.
2. **In-game FFB adjustment** — Change FFB strength directly from your wheel buttons while driving, without alt-tabbing to RaceHub.
3. **Per-game / per-car profiles** — Create unlimited FFB profiles and switch between them instantly. Save your perfect setup for each sim and each car.

These are features the Asetek community has been requesting for a long time, and this plugin aims to deliver them through SimHub's ecosystem.

---

## Features

### ✅ Confirmed Working

| Feature | Description |
|---------|-------------|
| **Auto base detection** | Plugin enumerates VID_2433 on connect and auto-identifies Invicta / Forte / La Prima (and the supported wheels). Slider ceilings adapt to the detected base's spec (12 / 16 / 18 / 27 Nm). |
| **True Steering Lock** | Auto-syncs steering range from the game (LMU REST API + per-car CarClass detection). The wheelbase range matches the car automatically. |
| **FFB Settings** | Full control of all wheelbase parameters: Overall Force, Steering Range, Damping, Friction, Inertia, Anti-Oscillation, Torque Prediction, Slew Rate, HF Limit, Cornering Assist, Bumpstop. |
| **Apply & Save to Flash** | Sends settings to the wheelbase and persists them to flash. |
| **Per-game / per-car profiles** | Unlimited profiles with save / load / rename / delete. Auto-match by Game / CarClass / CarId so the right profile loads when you switch sims or cars. RaceHub XML preset import (Documents\RaceHub Profiles\Wheelbase\Backup\). |
| **FFB Strength +/-** | Bindable SimHub actions — assign to wheel buttons for on-the-fly force adjustment without alt-tabbing. |
| **Steering Range / Force Presets** | Quick-switch between 360° / 540° / 900° / 1080° steering and Low/Med/High/Max force via bindable buttons. |
| **Re-center Wheel** | Sets the current wheel position as the new zero, persisted to flash (also exposed as a bindable SimHub action). |
| **Reset Torque Limits** | Restores the detected base to its factory torque configuration in one click. Recovers a wheelbase that has been silently capped. |
| **Disconnect / Reconnect** | Releases the HID handle on demand so RaceHub can take over without closing SimHub. |
| **RaceHub auto-pause** | Polls for the RaceHub UI process and auto-disconnects when detected, surfacing a warning banner and greying out plugin controls so the two apps never write to the IONI flash at the same time. |

### 🧪 Beta

| Feature | Description |
|---------|-------------|
| **Wheelbase Center LED** | Set color + flag mode (auto-coloured by race flags). |
| **Forte Rev Lights** | External control of the rev-light strip from game telemetry. |
| **360 Hz Compatibility Mode** | Toggle the wheelbase's high-rate FFB pipeline so it stays in sync with iRacing's 360 Hz native telemetry. |

---

## Screenshots

### Overview — Device Status & Profiles
![Overview Tab](screenshots/main.png)

### FFB Settings — Full Parameter Control
![FFB Settings Tab](screenshots/ffb%20settings.png)

### LED Control (Beta)
![LED Control Tab](screenshots/Led%20control.png)

### Controls — Button Mapping
![Controls Tab](screenshots/button%20Mapping.png)

---

## Supported Hardware

- **Asetek Invicta Wheelbase** (VID_2433 : PID_F300) — 27 Nm peak
- **Asetek Forte Wheelbase** (VID_2433 : PID_F301 / PID_F200) — 18 Nm peak
- **Asetek La Prima Wheelbase** (VID_2433 : PID_F303) — 12 Nm peak (16 Nm with high-power PSU)
- **Asetek Forte GT Steering Wheel** (VID_2433 : PID_F207)
- **Asetek Invicta Steering Wheel** (VID_2433 : PID_F400)
- **Asetek Formula Forte Steering Wheel** (VID_2433 : PID_F402)

Plugin auto-detects the model on connect and adapts the Overall Force ceiling to match. Other Asetek devices may enumerate but have not been hands-on tested — please open a GitHub issue with your VID/PID if you have one to test.

---

## Installation

1. **Close RaceHub** if it is running
2. Download `AsetekPlugin.dll` from the [Releases](../../releases) page
3. Copy `AsetekPlugin.dll` into your SimHub installation folder (e.g., `C:\Program Files (x86)\SimHub\`)
4. Launch SimHub — the plugin appears as **"Asetek Control"** in the left menu

---

## Tabs Overview

### Overview
Device connection status (Invicta + Forte), diagnostics, and profile management.

- **Device cards** — Shows connection status for the Invicta wheelbase and Forte GT wheel with hardware IDs
- **Profiles** — Create, load, rename, delete, and set default profiles. Each profile stores all FFB settings, True Steering Lock state, and FFB step size
- **Diagnostics** — Raw HID communication log for troubleshooting
- **Reconnect** — Re-scan for Asetek devices without restarting SimHub

### FFB Settings
All wheelbase FFB parameters with sliders matching the values available in RaceHub.

- **Core** — Steering Range (180°–1890°) and Overall Force (capped to the detected base's peak: 12 Nm La Prima / 16 Nm w/ high-power PSU / 18 Nm Forte / 27 Nm Invicta)
- **Mechanical Feel** — Damping, Friction, Inertia, Anti-Oscillation (0–100%)
- **Torque Shaping** — Torque Prediction (0–10), Torque Accel Limit (capped to the detected base's slew rate: 4.0 Nm/ms La Prima stock / 6.7 Nm/ms La Prima with high-power PSU / 6.7 Nm/ms Forte / 9.4 Nm/ms Invicta), High Frequency Limit (0–4700 Hz)
- **Bumpstop & Cornering** — Cornering Force Assist (0–100%), Bumpstop Hardness (Soft/Medium/Hard), Bumpstop Range (-90°–+90°)
- **Game Integration** — True Steering Lock checkbox (auto-sync from game), link to Controls tab
- **Apply & Save** — Sends all slider values to the wheelbase and persists to flash memory. On first use, set all sliders to match your current RaceHub values

### LED Control (Beta)
Wheelbase center LED color control and Forte rev light customization. This feature is not fully tested yet.

- **Wheelbase Center LED** — Flag Mode (auto-color based on race flags), test colors (Red, Green, Blue, Yellow, White, Orange, Purple, Off)
- **Forte Rev Lights** — RPM Telemetry toggle for external control, pattern presets (Segmented, Blue→Red, Red→Yellow, Green→Red)

### Controls
Assign wheel buttons, joystick buttons, or keyboard keys to any plugin action using SimHub's native ControlsEditor.

- **FFB Strength** — FFB Strength + / FFB Strength −
- **Steering Range Presets** — 360° / 540° / 900° / 1080°
- **Force Presets** — Low (10 Nm) / Medium (18 Nm) / High (24 Nm) / Max (27 Nm)
- **Toggles** — True Steering Lock
- **LED Modes** — LED Off / Flag Mode / Telemetry Mode
- **Device** — Apply & Save / Reconnect

---

## How It Works

### Communication
The plugin communicates with the Invicta wheelbase and Forte GT wheel via **HID (Human Interface Device)** — the standard USB protocol for input devices. It opens the device handle, sends configuration packets, and the wheelbase applies them immediately.

### FFB Settings
Each FFB parameter corresponds to a specific address in the wheelbase profile memory. When you click **Apply & Save**, the plugin sends 3 batches of settings to the active profile, followed by a save-to-flash command. Settings are applied immediately — no restart required.

### True Steering Lock
When enabled, the plugin queries the **LMU REST API** (port 6397) for the current car's steering lock value (e.g., `VM_STEER_LOCK = "450deg"`). It then automatically sets the wheelbase steering range to match. This happens on car change and retries every ~2 seconds until resolved.

### Profiles
Profiles are stored locally as JSON in `%APPDATA%\AsetekPlugin\profiles.json`. Each profile captures:
- All FFB parameter values (steering range, force, damping, friction, etc.)
- True Steering Lock on/off state
- FFB step size for +/- buttons

You can set a **default profile** that loads automatically when SimHub starts.

### Settings Persistence
The wheelbase does not expose a "read settings" command. The plugin maintains a local cache of all settings and persists them in `%APPDATA%\AsetekPlugin\ffb_settings.json`. On first use, make sure to configure all sliders to match your current RaceHub values before applying.

### Coexistence with RaceHub

The plugin detects when RaceHub is running and automatically releases the wheelbase so the two apps never end up controlling it concurrently. Behaviour:

- When RaceHub starts, the plugin pauses itself within a second, greys out the tab content, and shows a warning banner.
- When RaceHub closes, the banner switches to an "appears closed" state with a Reconnect button right inside it.
- An explicit **Disconnect** button on the Overview tab lets you hand the wheelbase over on demand without closing SimHub.

### Reset Torque Limits

If your wheelbase ends up capped well below its rated torque — especially if RaceHub itself shows the slider stuck and a firmware reflash didn't help — open the Overview tab and click **Reset Torque Limits**. The button restores the detected base to its factory torque configuration and re-initialises the drive. After clicking, **power-cycle the wheelbase** (USB unplug + replug) and verify in RaceHub that the Overall Force slider reaches its full peak again.

A confirmation dialog protects the button so it can't be triggered accidentally. Running it on a healthy base is a safe no-op.

---

## SimHub Properties (for dashboard developers)

The plugin exposes the following SimHub properties that can be used in custom dashboards:

| Property | Type | Description |
|----------|------|-------------|
| `Asetek.WheelbaseConnected` | bool | Invicta wheelbase detected |
| `Asetek.ForteConnected` | bool | Forte GT wheel detected |
| `Asetek.Led.Mode` | string | Current LED mode (off/flag/telemetry) |
| `Asetek.FFB.TrueSteeringLock` | bool | True Steering Lock enabled |
| `Asetek.FFB.CurrentStrength` | int | Current FFB strength (main_gain 0–100) |
| `Asetek.FFB.SteeringRange` | int | Current steering range in degrees |
| `Asetek.TSL.Debug` | string | True Steering Lock debug info |

---

## SimHub Actions (for button mapping)

| Action | Description |
|--------|-------------|
| `Asetek.FFB.Strength.Up` | Increase FFB strength |
| `Asetek.FFB.Strength.Down` | Decrease FFB strength |
| `Asetek.FFB.SteeringRange.360` | Set steering range to 360° |
| `Asetek.FFB.SteeringRange.540` | Set steering range to 540° |
| `Asetek.FFB.SteeringRange.900` | Set steering range to 900° |
| `Asetek.FFB.SteeringRange.1080` | Set steering range to 1080° |
| `Asetek.FFB.Force.Low` | Set force to 30 % of the detected base's peak |
| `Asetek.FFB.Force.Medium` | Set force to 60 % of the detected base's peak |
| `Asetek.FFB.Force.High` | Set force to 85 % of the detected base's peak |
| `Asetek.FFB.Force.Max` | Set force to 100 % of the detected base's peak |
| `Asetek.FFB.TrueSteeringLock.Toggle` | Toggle True Steering Lock |

> Force-preset Nm equivalents per model:
>
> | Preset | Invicta (27 Nm) | Forte (18 Nm) | La Prima (12 Nm) | La Prima+ PSU (16 Nm) |
> |--------|-----------------|----------------|-------------------|------------------------|
> | Low    | ≈ 8 Nm         | ≈ 5 Nm         | ≈ 4 Nm            | ≈ 5 Nm                |
> | Medium | ≈ 16 Nm        | ≈ 11 Nm        | ≈ 7 Nm            | ≈ 10 Nm               |
> | High   | ≈ 23 Nm        | ≈ 15 Nm        | ≈ 10 Nm           | ≈ 14 Nm               |
> | Max    | 27 Nm          | 18 Nm          | 12 Nm             | 16 Nm                 |
| `Asetek.ApplyAndSave` | Apply current settings & save to flash |
| `Asetek.Reconnect` | Reconnect to devices |
| `Asetek.Led.Off` | Turn off LEDs |
| `Asetek.Led.FlagMode` | Enable flag-based LED mode |
| `Asetek.Led.TelemetryMode` | Enable telemetry-based LED mode |

---

## Known Limitations

- **RaceHub coexistence** — handled automatically. The plugin auto-pauses (releases its handle, greys out controls, shows a banner) when RaceHub is running, and a Reconnect button appears as soon as RaceHub closes. You can also click Disconnect manually to hand the wheelbase over.
- **True Steering Lock** currently only works with **Le Mans Ultimate / rFactor 2** (requires the LMU REST API on port 6397). Multi-sim support is on the roadmap.
- **LED features are in beta** — behavior may vary depending on firmware version.
- **Settings are not readable from the wheelbase** — the plugin persists your last settings locally. On first use, make sure to set all sliders to match your current RaceHub values before applying.
- **High Torque Mode toggle** must currently be set in RaceHub. If it's disabled there, the wheelbase will cap motor output to a low safe value regardless of the slider. Keeping the auto-enable option turned on in RaceHub is the recommended setup.

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Plugin shows "RaceHub is running — paused" banner | Expected behavior. Close RaceHub completely (or wait for it to release the handle) then click Reconnect in the banner. |
| Wheelbase shows "0 Found" | Another app has the HID handle. Close RaceHub, click Reconnect. If the issue persists, kill `RaceHubWindowsService.exe` from Task Manager. |
| RaceHub Overall Force slider is stuck at ~7 Nm (Invicta) / ~3 Nm (Forte) / ~1 Nm (La Prima), and a firmware reflash didn't help | Open the Overview tab and click **Reset Torque Limits** → confirm → power-cycle the wheelbase (USB unplug + replug). The slider should reach the full peak again. |
| Settings don't apply | Click "Apply & Save" — sliders only update the display until you apply. |
| True Steering Lock shows "err" | Make sure LMU is running and in a session (not at the main menu). |
| Plugin doesn't appear in SimHub | Make sure `AsetekPlugin.dll` is in the SimHub root folder, not a subfolder. |

---

## Roadmap

This plugin is under active development. Planned features include:

- [ ] Multi-sim True Steering Lock (ACC, iRacing, AMS2...)
- [x] Auto-profile switching based on game / car (v1.0.3)
- [x] Per-base torque & slew rate ceiling auto-detection (v1.0.5–1.0.7)
- [x] One-click factory recovery for corrupted SMP limits (v1.0.8)
- [x] Safe RaceHub coexistence — auto-pause + Disconnect/Reconnect (v1.0.8)
- [ ] In-plugin High Torque Mode toggle
- [ ] LED patterns and animations
- [ ] Forte pedal telemetry integration
- [ ] Community-contributed profiles library

Feature requests and bug reports are welcome via [GitHub Issues](../../issues).

---

## License

MIT License — see [LICENSE](LICENSE) file.

This project is provided as-is with no warranty. See disclaimer above.

---

## Support

If you like this plugin and want to support its development:

[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/simrace)

---

*Made with passion by a sim racer, for sim racers.*
