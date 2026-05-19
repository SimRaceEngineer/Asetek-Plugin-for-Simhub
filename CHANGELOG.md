# Asetek Control — Changelog

> Public release notes.

---

## v1.6.8 — FFB output now strictly matches Asetek native (May 19, 2026)

### What this means for you
- **Invicta, Forte, La Prima and Tony Kanaan editions** now deliver
  their full factory torque through the plugin — strictly identical
  to what Asetek's native software outputs. No more silent caps, no
  more "feels light", no more discrepancy between what your slider
  shows and what your wheel actually does.
- One click on **"Restore Factory Default"** is all it takes. If
  you've ever felt your base was underpowered, run it once and the
  difference will be immediate.

### Per-track and per-car FFB profiles
- Beyond the raw FFB fix, the plugin now offers a full **per-car /
  per-track profile** system : different setups for different car
  classes, different tracks, even different conditions — all
  auto-loaded when SimHub detects the active sim + car + track. No
  more manual swapping. Big quality-of-life upgrade for anyone
  juggling multiple sims and many cars.

### What's next — driven by the community
- The FFB plumbing is now fully nailed down. From here we're opening
  the door to a whole new layer of features :
  - **Smart FFB modulation** (per-track, per-car learned softening of
    clipping zones — already shipping in beta as *Adaptive FFB Zones*)
  - **Live in-race tuning** with full slider response, no save/restart
  - **External controllers** — picture binding base profiles, FFB
    strength and Smart modes to a **Stream Deck / Loupedeck** for
    instant in-cockpit control without lifting a hand off the wheel
  - More to come
- **Roadmap is community-driven.** Tell us in the Discord which
  features you'd actually use — that's what gets built next.

### 🐧 Linux support
- Because the plugin runs inside SimHub, and SimHub for Linux now
  exists, this is the first time an **Asetek wheelbase can be
  configured and tuned from a Linux machine**. Same DLL, same
  features, on Ubuntu / Steam Deck OS / any desktop Linux — for sim
  racers who left Windows behind.

### Notes on Initium
- The Initium wheelbase (the Asetek entry-level / console-compatible
  model) is **not supported yet** — it uses a different
  communication protocol from the Invicta / Forte / La Prima family,
  so it needs a separate implementation path. Asetek selling Initium
  as a cross-platform (console + PC) base means a SimHub-based
  configurator for it could open interesting doors. Tell us in the
  Discord if you'd use it.

### Project scope
- This plugin is an independent, parallel project. It is not
  affiliated with Asetek SimSports or RaceHub. It complements
  Asetek's official software for users who want to drive their
  wheelbase from inside the SimHub ecosystem.

### How to upgrade
- Update the SimHub plugin DLL, restart SimHub.
- If your base ever felt lighter than its rated torque, click
  *Restore Factory Default* (Debug tab) once after install.

---

## v1.6.1 — Overall Force save fix (May 19, 2026)

### Fixed
- "Save to Wheelbase" now correctly applies your Overall Force change.

### Note on live Overall Force
- For live Overall Force changes during a session :
  - Bind `Asetek.FFB.Force.Low/Medium/High/Max` to a button on your
    wheel / button box.
  - Or bind `Asetek.ApplyAndSave` to a button.
- All other sliders are fully live since v1.6.0.

---
