# Asetek Control — SimHub Plugin for Invicta & Forte

> **Beta Release — v1.0.0-beta**

A SimHub plugin that brings **direct FFB settings control**, **True Steering Lock**, **per-game profiles**, and **LED control** to Asetek SimSports Invicta wheelbases and Forte GT steering wheels — all from within SimHub.

---

## ⚠️ IMPORTANT DISCLAIMER

**This plugin is an independent, community-driven project.**

- This plugin is **NOT affiliated with, endorsed by, or supported by Asetek SimSports** or any of its subsidiaries.
- This is a **beta release** — features may not work as expected on all configurations. **Use at your own risk.**
- This plugin communicates with Asetek hardware via the standard HID (Human Interface Device) protocol, the same USB interface used by any compatible software.
- **No warranty** is provided, express or implied. The authors are not responsible for any damage, misconfiguration, or unexpected behavior that may result from using this plugin.
- This plugin **may stop working** after a firmware update from Asetek.
- **RaceHub must be closed** before launching SimHub with this plugin — both applications cannot access the wheelbase simultaneously.
- By using this plugin, you acknowledge that you understand these limitations and accept full responsibility.

### Why this plugin exists

The goal of this plugin is to fill gaps that the official Asetek software (RaceHub) does not currently address:

1. **True Steering Lock** — Automatically match the wheelbase steering range to the car you're driving (e.g., 380° for a Hypercar, 540° for a GT3). No more manual adjustment between sessions.
2. **In-game FFB adjustment** — Change FFB strength directly from your wheel buttons while driving, without alt-tabbing to RaceHub.
3. **Per-game / per-car profiles** — Create unlimited FFB profiles and switch between them instantly. Save your perfect setup for each sim and each car.

These are features the Asetek community has been requesting for a long time, and this plugin aims to deliver them through SimHub's ecosystem.

---

## Features

### ✅ Confirmed Working

| Feature | Status | Description |
|---------|--------|-------------|
| **FFB Settings** | Stable | Full control of all wheelbase parameters: Overall Force, Steering Range, Damping, Friction, Inertia, Anti-Oscillation, Torque Prediction, Slew Rate, HF Limit, Cornering Assist, Bumpstop |
| **True Steering Lock** | Stable | Auto-syncs steering range from the game via LMU/rF2 REST API. The wheelbase range matches the car automatically |
| **FFB Strength +/-** | Stable | Bindable SimHub actions — assign to wheel buttons for on-the-fly force adjustment without leaving the cockpit |
| **Steering Range Presets** | Stable | Quick-switch between 360° / 540° / 900° / 1080° via bindable buttons |
| **Force Presets** | Stable | Quick-switch between Low (10 Nm) / Medium (18 Nm) / High (24 Nm) / Max (27 Nm) |
| **Software Profiles** | Stable | Unlimited profiles with save/load/rename/delete. Set a default profile loaded at startup |
| **Apply & Save to Flash** | Stable | Send settings to the wheelbase and persist to flash memory |

### 🧪 Beta

| Feature | Status | Description |
|---------|--------|-------------|
| **Wheelbase Center LED** | Beta | Set the center LED color, flag mode (auto-color based on race flags) |
| **Forte Rev Lights** | Beta | External control of the rev light strip from game telemetry |

---

## Supported Hardware

- **Asetek Invicta Wheelbase** (VID_2433 : PID_F300)
- **Asetek Forte GT Steering Wheel** (VID_2433 : PID_F207)

Other Asetek wheelbases or wheels may work but have not been tested.

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

### FFB Settings
All wheelbase FFB parameters with sliders matching the values available in RaceHub. Changes are sent to the wheelbase when you click **"Apply & Save"**.

### LED Control (Beta)
Wheelbase center LED color control and Forte rev light customization. This feature is not fully tested yet.

### Controls
Assign wheel buttons, joystick buttons, or keyboard keys to plugin actions:
- FFB Strength +/-
- Steering Range presets (360° / 540° / 900° / 1080°)
- Force presets (Low / Medium / High / Max)
- True Steering Lock toggle
- Apply & Save
- Reconnect

---

## Known Limitations

- **RaceHub conflict** — RaceHub and this plugin cannot run simultaneously. Close RaceHub before launching SimHub.
- **True Steering Lock** currently only works with **Le Mans Ultimate / rFactor 2** (requires the LMU REST API on port 6397).
- **LED features are in beta** — behavior may vary depending on firmware version.
- **Settings are not readable from the wheelbase** — the plugin persists your last settings locally. On first use, make sure to set all sliders to match your current RaceHub values before applying.

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
| `Asetek.FFB.Force.Low` | Set force to 10 Nm |
| `Asetek.FFB.Force.Medium` | Set force to 18 Nm |
| `Asetek.FFB.Force.High` | Set force to 24 Nm |
| `Asetek.FFB.Force.Max` | Set force to 27 Nm |
| `Asetek.FFB.TrueSteeringLock.Toggle` | Toggle True Steering Lock |
| `Asetek.ApplyAndSave` | Apply current settings & save to flash |
| `Asetek.Reconnect` | Reconnect to devices |

---

## License

This project is provided as-is with no warranty. See disclaimer above.

---

*Made with passion by a sim racer, for sim racers.*
