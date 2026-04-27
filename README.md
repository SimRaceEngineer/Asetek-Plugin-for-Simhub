# Asetek Control — SimHub Plugin for Invicta & Forte

> **v1.0.4-beta** — Direct FFB control, profile auto-match per game / car / track, live torque & clipping monitoring, all from inside SimHub.

A SimHub plugin that brings **direct FFB settings control**, **per-game / per-car / per-track profile auto-matching**, **live torque monitoring**, **True Steering Lock**, and **LED control** to Asetek SimSports wheelbases (Invicta, Forte / La Prima) and the Forte GT steering wheel — without ever opening RaceHub during a session.

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

The plugin fills practical gaps left by RaceHub for sim racers who live inside SimHub:

1. **No more alt-tabbing to RaceHub during a session.** Adjust FFB strength on the fly with a wheel button. Switch between cars and the right preset loads automatically. Re-center the wheel after a rim swap with a single click.
2. **Profiles tied to the actual content you're driving** — game, car class, specific car, even a specific track. The plugin reads SimHub's own telemetry so it works the same in iRacing, LMU, ACC, AMS2, etc.
3. **Per-track FFB tuning** — surfaces vary wildly between Spa and Daytona Roval. The plugin reads iRacing's 360 Hz steering torque telemetry to give you a live "surface roughness" score and store dedicated presets for bumpy / smooth / street circuits.
4. **Live torque & clipping monitoring** — see in real time how much of your configured force ceiling you're using, with a clipping flag you can wire into a Dash widget.
5. **One-click Asetek-style High Torque (360 Hz Compatibility Mode)**, RaceHub preset import, standstill anti-oscillation, and other quality-of-life utilities that previously required digging into RaceHub between sessions.

---

## ✨ What works today (confirmed)

| Feature | Description |
|---------|-------------|
| **Full FFB sliders** | Steering Range, Overall Force (3-27 Nm), Damping, Friction, Inertia, Anti-Oscillation, Torque Behavior Prediction, Torque Acceleration Limit, High Frequency Limit, Cornering Force Assist, Bumpstop Hardness/Range. All confirmed firing and produce a felt change on the wheel. Overall Force pairs main_gain with the SMP torque-limit registers so the motor actually delivers what the slider asks. |
| **Apply & Save to flash** | One button persists every slider to the wheelbase flash, including all 12 FFB parameters. |
| **Per-game / per-car / per-track auto-match** | Profile gains optional Game / CarClass / CarId / Track tags. The plugin watches what you're loading in any sim and switches to the matching profile automatically. Match priority: most specific (game + car + track) wins; falls back gradually to game-only. |
| **Quick-save buttons** | Capture current sliders into a new profile in one click, auto-tagged with the running sim/car/track: "by Class", "by Car", "by Car + Track". |
| **FFB Strength +/- via wheel button** | Bind two buttons, change force during a stint without leaving the cockpit. |
| **Re-center Wheel** | Dedicated UI button + bindable action. Useful after swapping rims so the wheel stops trying to rotate to the previous zero. Saved to flash. |
| **Standstill Damping** | Auto-boosts internal damping under 13 km/h (with hysteresis to 15 km/h) to kill the parasitic wheel oscillations on grid / in pit lane / pause. Restored automatically once you're rolling. |
| **360 Hz Compatibility Mode toggle** | Engages the wheelbase's high-rate FFB pipeline. Persisted on the device, re-applied on reconnect. |
| **Live torque & clipping monitor** | Five SimHub properties refreshing at ~15 Hz: instantaneous Nm, configured ceiling, utilisation %, clipping flag, rolling peak. Wire any of them into a Dash widget. |
| **360 Hz native sampling on iRacing** | Reads `SteeringWheelTorque_ST[6]` (6 sub-samples per 60 Hz tick = 360 Hz effective) and feeds a 1-second rolling buffer. Sharper clipping detection (no missed spikes between frames) plus the `RoughnessNm` property below. |
| **Surface roughness score** | `Asetek.FFB.RoughnessNm` — standard deviation of the 360 Hz signal in Nm units. Smooth tracks sit around 0.5-1.0 Nm, bumpy circuits past 3-4 Nm. Practical anchor for per-track tuning. |
| **Import RaceHub Presets** | Scans `Documents\RaceHub Profiles\Wheelbase\Backup\` and imports every XML preset RaceHub has auto-exported as a plugin profile. Auto-tags the Game heuristically from the preset name. |
| **RaceHub-format XML mirror** | Every saved profile is also written to the Documents folder as a redundant XML backup. |
| **Universal Asetek device scan** | Auto-detects any base in the F2xx-F6xx PID range (Invicta F300, Forte F301, Forte/LaPrima F200) plus wheels (Forte GT F207, Formula Forte F402). |

## 🧪 Still beta / under test

| Feature | Status |
|---------|--------|
| **True Steering Lock** | Works in LMU (uses the LMU REST API on port 6397). Multi-sim support planned. |
| **LED Control** | Wheelbase center LED + Forte rev lights — functional but not exhaustively tested across firmware versions. |
| **Controls-tab button bindings** (range presets, force presets, LED modes, toggles) | Should work but only FFB Strength +/- has been hands-on validated so far. Please open a GitHub issue if any binding misbehaves on your setup. |

---

## Screenshots

### Overview — Device Status & Profiles
![Overview Tab](screenshots/main.png)

### FFB Settings — Full Parameter Control
![FFB Settings Tab](screenshots/ffb%20settings.png)

### Per-car / per-track Quick Save (iRacing example)
The "Detected:" status line shows the running game / car / track in real time. Three one-click buttons capture the current sliders into a profile auto-tagged for that combination — broad (by Class), specific (by Car), or pinned (by Car + Track) for per-track FFB tuning.

![Quick Save by Car / Track](screenshots/quicksave%20car%20track.png)

### Live torque & clipping monitor in SimHub properties
Five Asetek FFB properties exposed to SimHub at ~15 Hz, sourced from iRacing's 360 Hz `_ST` array (or 60 Hz scalar fallback on LMU/ACC). Drop them into a Dash Studio widget for a clipping LED, a utilisation bar or a surface roughness readout.

![SimHub Properties — Live Torque](screenshots/simhub%20properties%20torque.png)

### LED Control (Beta)
![LED Control Tab](screenshots/Led%20control.png)

### Controls — Button Mapping
![Controls Tab](screenshots/button%20Mapping.png)

---

## Supported Hardware

- **Asetek Invicta Wheelbase** (VID_2433 : PID_F300) — primary test platform
- **Asetek Forte Wheelbase** (VID_2433 : PID_F301)
- **Asetek Forte / La Prima Wheelbase** (VID_2433 : PID_F200)
- **Asetek Forte GT Steering Wheel** (VID_2433 : PID_F207)
- **Asetek Formula Forte Steering Wheel** (VID_2433 : PID_F402)

Other Asetek wheelbases or wheels in the F2xx-F6xx PID range are auto-detected and will appear in the UI; specific feature compatibility may vary.

---

## Installation

1. **Close RaceHub** if it's running.
2. Download `AsetekPlugin.dll` from the [Releases](../../releases) page.
3. Copy `AsetekPlugin.dll` into your SimHub installation folder (e.g. `C:\Program Files (x86)\SimHub\`).
4. Launch SimHub — the plugin appears as **"Asetek Control"** in the left menu.

---

## Tabs Overview

### Overview
Device connection status, diagnostics, and the full profile manager.

- **Device cards** — connection status for the wheelbase and the wheel, with the actual detected model name and PID
- **Profile list** — Load / Rename / Save / Tag / Edit / Delete on every profile, plus the inline tag editor (Game / CarClass / CarId / Track)
- **Auto-match toggle** — when enabled, switches to the best-matching profile when the game or car changes (smart-creates one with current sliders if none matches)
- **Import RaceHub Presets** — bulk import RaceHub's XML auto-exports
- **Reconnect** — re-scan for Asetek devices without restarting SimHub

### FFB Settings
All wheelbase FFB parameters with sliders matching the values available in RaceHub.

- **Core** — Steering Range (180°-1890°) and Overall Force (3-27 Nm)
- **Mechanical Feel** — Damping, Friction, Inertia, Anti-Oscillation (0-100%)
- **Torque Shaping** — Torque Prediction (0-10), Torque Acceleration Limit (0.1-9.4 Nm/ms), High Frequency Limit
- **Bumpstop & Cornering** — Cornering Force Assist (0-100%), Bumpstop Hardness (Soft/Medium/Hard), Bumpstop Range (-90°/+90°)
- **Game Integration** — True Steering Lock, Standstill Damping, 360 Hz Compatibility Mode
- **APPLY & SAVE** — sends every slider to the wheelbase, persists to flash, also fires the SMP torque-limit registers paired with main_gain
- **Save current sliders to…** dropdown — write current values to any profile without applying to the wheelbase
- **Quick save → by Car Class / by Car / by Car + Track** — one-click capture with auto-tagging from the running sim
- **↻ RELOAD PRESET** — discard slider edits and restore the active profile values
- **RE-CENTER WHEEL** — set current wheel position as zero, saved to flash
- **Live "Detected:" status line** — shows what the plugin will tag (Game / Class / CarModel / Track) before you save

### LED Control (Beta)
Wheelbase center LED color control and Forte rev light customization.

- **Wheelbase Center LED** — flag mode (auto-color from race flags), test colors
- **Forte Rev Lights** — RPM telemetry toggle, pattern presets (Segmented, Blue→Red, Red→Yellow, Green→Red)

### Controls
SimHub-native button mapping for all plugin actions (see Actions list below).

---

## SimHub Properties (for dashboard developers)

| Property | Type | Description |
|----------|------|-------------|
| `Asetek.WheelbaseConnected` | bool | Wheelbase detected |
| `Asetek.ForteConnected` | bool | Forte wheel detected |
| `Asetek.Led.Mode` | string | Current LED mode |
| `Asetek.FFB.TrueSteeringLock` | bool | True Steering Lock enabled |
| `Asetek.FFB.CurrentStrength` | int | Current main_gain (0-100) |
| `Asetek.FFB.SteeringRange` | int | Current steering range in degrees |
| `Asetek.FFB.CurrentTorqueNm` | double | Live torque from the running sim, in Nm |
| `Asetek.FFB.MaxTorqueNm` | double | Configured ceiling (main_gain × 27) |
| `Asetek.FFB.UtilizationPct` | double | Current / max × 100 |
| `Asetek.FFB.IsClipping` | bool | True when ≥ 95 % of max — perfect for a flashing LED |
| `Asetek.FFB.PeakTorqueNm` | double | Rolling peak with slow decay |
| `Asetek.FFB.RoughnessNm` | double | Surface roughness score (stddev of the 360 Hz buffer in Nm) |
| `Asetek.FFB.SampleRateHz` | int | 360 on iRacing's `_ST` array, 60 on the scalar fallback |
| `Asetek.TSL.Debug` | string | True Steering Lock debug info |

---

## SimHub Actions (for button mapping)

| Action | Description |
|--------|-------------|
| `Asetek.FFB.Strength.Up` / `.Down` | Live FFB strength adjustment from a wheel button |
| `Asetek.FFB.SteeringRange.360` / `540` / `900` / `1080` | Steering range presets |
| `Asetek.FFB.Force.Low` / `Medium` / `High` / `Max` | 10 / 18 / 24 / 27 Nm presets |
| `Asetek.FFB.TrueSteeringLock.Toggle` | Toggle TSL |
| `Asetek.Toggle360Hz` | Toggle 360 Hz Compatibility Mode |
| `Asetek.RecenterWheel` | Re-center the wheel + save to flash |
| `Asetek.ApplyAndSave` | Apply current cache + save to flash |
| `Asetek.Reconnect` | Re-scan for Asetek devices |
| `Asetek.Led.Off` / `Asetek.Led.FlagMode` / `Asetek.Led.TelemetryMode` | LED modes |

---

## How It Works

### Communication
The plugin communicates with the wheelbase and the Forte GT wheel via **HID (Human Interface Device)** — the standard USB protocol for input devices. It opens the device handle, sends configuration packets via WriteFile (interrupt OUT, EP 0x01), and the wheelbase applies them immediately.

### FFB Settings
Each FFB parameter corresponds to a specific address in the wheelbase profile memory. APPLY & SAVE sends three consecutive 9-address batches to the active profile, then a save-to-flash command. The Overall Force slider also fires the SMP torque-limit registers so the motor actually clips at the configured ceiling, not the previous one.

### Profile auto-match
The plugin watches `data.GameName`, `data.NewData.CarClass`, `data.NewData.CarId` and `data.NewData.TrackId` from SimHub on every tick. When the (game, class, carId, track) combination changes and Auto-match is enabled, the best-matching profile is loaded automatically — most-specific match wins.

### Live torque monitor
On iRacing, the plugin reads the 6-sample `SteeringWheelTorque_ST` array (360 Hz effective) on every tick into a rolling 1-second buffer. On other sims it falls back to the 60 Hz scalar `SteeringWheelTorque`. Properties (`CurrentTorqueNm`, `IsClipping`, `RoughnessNm`, etc.) are republished at 15 Hz to spare overhead.

### Profile storage
Profiles are stored locally as JSON in `%APPDATA%\AsetekPlugin\profiles.json`. Each save also writes a RaceHub-format XML mirror to `Documents\RaceHub Profiles\Wheelbase\Backup\Plugin - <Name> - Asetek Plugin Backup.xml` as a redundant backup.

### Settings persistence
The wheelbase does not expose a "read settings" command. The plugin maintains a local cache and persists it in `%APPDATA%\AsetekPlugin\ffb_settings.json`. On a fresh install, configure all sliders to match your current RaceHub values before the first APPLY.

---

## Known Limitations

- **RaceHub conflict** — RaceHub and this plugin cannot run simultaneously. Close RaceHub before launching SimHub.
- **True Steering Lock** is currently LMU-only (uses the LMU REST API on port 6397). Multi-sim support planned.
- **LED features are still beta** — behavior may vary depending on firmware version.
- **Settings are not readable from the wheelbase** — the plugin persists the last-known cache locally.
- **Forte GT HID conflict** — if Leoxz SimBridge is managing the Forte wheel, the plugin skips Forte enumeration to avoid conflicts.

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Both devices show "DISCONNECTED" | Close RaceHub, click Reconnect |
| Wheelbase shows "0 Found" | RaceHub is still running, or another app has the HID handle |
| Settings don't apply | Click APPLY & SAVE — sliders only update the display until you apply |
| True Steering Lock shows "err" | Make sure LMU is running and you're in a session (not at the main menu) |
| Plugin doesn't appear in SimHub | `AsetekPlugin.dll` must be in the SimHub root folder, not a subfolder |
| Torque monitor shows 0 Nm | The running sim doesn't expose its steering torque on a known SimHub property path — open a GitHub issue with the sim name |

---

## Roadmap

- [ ] Multi-sim True Steering Lock (ACC, iRacing, AMS2…)
- [ ] Auto-tune presets by track surface (use the live `RoughnessNm` to suggest HF Limit, Slew Rate and Anti-Oscillation values)
- [ ] LED patterns and animations driven by telemetry
- [ ] Forte pedal telemetry integration
- [ ] Community-contributed profile library

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
