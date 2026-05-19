# Asetek Control — Changelog

> Public release notes.

---

## v1.6.2 — Smart Driving Mode, Phase 2 (May 19, 2026)

### Added — Adaptive FFB Zones beta : modulation runtime
- The plugin now closes the loop on Phase 1's learning :
  - Phase 1 (already shipping) : watches where your FFB peaks per
    track + per car over a few laps. Pure observation.
  - **Phase 2 (new)** : pre-emptively softens your Damping a fraction
    of a second before each learned hot zone, then restores your
    value on exit. Lookahead scales with speed (more anticipation at
    high speed). Smooth software-side ramp so the wheel feels a grip
    change, not a slider step.
- New **"Apply modulation runtime"** toggle + **Modulation Strength**
  slider in *FFB Settings → Adaptive FFB Zones — Beta*. Off by default
  ; turn it on once you've captured a few laps on a track + car so
  the learner has zones to act on.
- Modulation is bounded by your existing slider values — it only
  raises Damping while you're crossing a known peak spot, never below
  your set point.

### Note
- The first version modulates Damping only. If field tests show that
  one filter isn't enough, more parameters will join the modulation
  in a later release.

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

## v1.6.0 — Live FFB sliders (May 19, 2026)

### Added
- All FFB sliders (Damping, Friction, Inertia, Anti-Oscillation,
  HF Limit, Slew Rate, Bumpstop, Steering Range, Cornering Force
  Assist) react instantly when you move the slider — no save,
  no restart.

---
