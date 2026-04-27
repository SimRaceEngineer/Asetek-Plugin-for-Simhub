# Asetek Control — Changelog

> All notable changes to this plugin will be documented in this file.

---

## v1.0.4-beta — Overall Force fix, live torque monitor, per-track profiles & 360 Hz reading (April 27, 2026)

This patch fixes a real-world FFB issue and adds three long-asked features: live torque/clipping monitoring, per-track profile matching and 360 Hz native sampling on iRacing. The slider plumbing and per-game/car profile auto-match introduced in v1.0.3-beta are now confirmed working in iRacing and LMU.

### Fixed (CRITICAL)

- **Overall Force slider had little perceptible effect.** The plugin was writing the profile-side gain (`main_gain`) but skipping the SMP torque-limit registers that drive the actual motor power cap. Without those, raising the slider didn't raise the felt force because the motor still clipped at the previous limit. RaceHub pairs both writes — we now do the same. Confirmed in iRacing: the Overall Force slider now produces a clear, immediate change in felt torque, comparable to RaceHub.
- The same dual-write now also fires when you load a profile from the list, so saved profiles restore their full intended force level too.

### Added

- **Live torque monitoring** for clipping detection. New SimHub properties refresh at ~15 Hz so you can wire them into a dashboard widget:
  - `Asetek.FFB.CurrentTorqueNm` — instantaneous |Nm| reported by the running sim
  - `Asetek.FFB.MaxTorqueNm` — your configured ceiling (`main_gain × 27`)
  - `Asetek.FFB.UtilizationPct` — current / max × 100 (jumps over 100 = you're clipping)
  - `Asetek.FFB.IsClipping` — boolean, true when ≥ 95 % of max (perfect for a flashing LED)
  - `Asetek.FFB.PeakTorqueNm` — rolling peak with slow decay
  - Reads from iRacing's irsdk telemetry first, falls back to LMU shared memory and ACC physics. Cross-sim compatible out of the box.
- **"360 Hz Compatibility Mode" toggle** (FFB Settings → Game Integration). Engages the wheelbase's high-rate FFB pipeline so it stays in sync with iRacing's 360 Hz native steering torque telemetry and LMU's shared-memory feed. State is persisted by the device in flash and re-applied on reconnect. Also exposed as the `Asetek.Toggle360Hz` SimHub action (Controls → TOGGLES) — bindable to a wheel/box button for on-the-fly toggling.

### Confirmed working (from v1.0.3-beta tests in LMU + iRacing)

- All four FFB sliders that were silently broken before the v1.0.3 mapping fix (Damping / Friction / Inertia / Anti-Oscillation) now produce a perceptible change on the wheelbase.
- Auto-match by game / car class / car id is working across sims. Detection lights up correctly in iRacing too — `Game = IRacing`, `CarClass`, `CarId` and `CarModel` come straight from the SimHub telemetry pipeline. Track is also picked up via `GameData.TrackId`.
- Quick-Save buttons (by Class / by Car) auto-name and auto-tag profiles correctly across both LMU and iRacing.
- Re-center wheel button + Standstill Damping toggle behaving as intended.

- **FFB Strength +/- bindings confirmed working** — bind two wheel buttons to `Asetek.FFB.Strength.Up` / `.Down` and adjust force on the fly without digging into a tab.

### Added — Per-track profiles

- **`Track` field on profiles**, alongside Game / CarClass / CarId. Persisted in `profiles.json`. Auto-match priority extended:
  `(game, carId, track)` > `(game, carClass, track)` > `(game, carId)` > `(game, carClass)` > `(game, track)` > carId-only > carClass-only > track-only > game-only.
  This means you can now have one base profile per car AND a more specific one for that car at a given track — the more specific one wins automatically.
- **"Quick save → by Car + Track"** button (3rd button on the FFB Settings tab, alongside by Class and by Car). One-click captures a profile pinned to the current `(game, carId, track)`, e.g. `iRacing Porsche 911 Cup (992.2) @ ledenon`.
- **Edit dialog** now has a 4th field for `Track`. Empty = matches anything (so you can keep a generic per-car profile and only override per-track when you actually need to).
- **Tag display** updated: `[iRacing/car: porsche9922cup @ ledenon]` shown next to the profile name.

### Added — 360 Hz native FFB signal reading (iRacing)

Up to v1.0.3-beta we were reading the game's `SteeringWheelTorque` scalar at 60 Hz then republishing at 15 Hz. That misses fast spikes that happen between two 60 Hz frames. iRacing actually exposes a higher-rate array — `SteeringWheelTorque_ST` — that contains **6 sub-samples per 60 Hz tick (= 360 Hz effective rate)**. The plugin now ingests all 6 samples every tick into a rolling 1-second buffer (360 entries) instead of the single scalar. LMU and ACC fall back cleanly to the 60 Hz scalar source.

What this gives you:

- **Sharper clipping detection.** Clipping spikes that happen in the gap between 60 Hz ticks are no longer missed — `Asetek.FFB.IsClipping` is now driven by the max of all 6 samples per tick.
- **`Asetek.FFB.RoughnessNm` — surface roughness score.** Standard deviation of the 360 Hz signal over a rolling 1-second window. Smooth modern tarmac sits around 0.5-1.0 Nm, fast bumpy tracks (Daytona Roval, Nordschleife 24h) easily climb past 3-4 Nm, street circuits with kerbs even higher. Wire it into a Dash widget and you get a live readout of how rough the surface is, in the same Nm units as your torque.
- **`Asetek.FFB.SampleRateHz`** advertises 360 (iRacing array) or 60 (scalar fallback) so you know which mode you're in.

**Why it matters for tuning** — same idea as community guides like Karsten Hvidberg's: smooth surfaces let you run no high-frequency filtering and full slew rate, but on bumpy or street circuits the road noise saturates the wheel and buries the genuine "limit signal". Lowering the High Frequency Limit + Slew Rate + raising Anti-Oscillation cleans the signal so you can still feel grip transitions through the noise. The Roughness number gives you a quantitative anchor instead of guessing — pair it with the per-track profile system above and you can store a tuned set per surface type per car, loaded automatically when you arrive on track.

> **Note:** other Controls-tab bindings (steering range presets, force presets, toggles, LED modes) haven't been hands-on tested across all configurations yet. They should work but are still experimental — please open a GitHub issue if any of them misbehaves on your setup.

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
