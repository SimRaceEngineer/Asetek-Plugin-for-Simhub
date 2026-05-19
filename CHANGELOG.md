# Asetek Control — Changelog

> Public release notes. Detailed engineering history is kept in the
> private dev repo.

---

## v1.6.1 — Overall Force save fix (May 19, 2026)

### Fixed
- **"Save to Wheelbase" now correctly applies your Overall Force change.**
  Previously the slider value updated only the plugin's memory ;
  clicking Save persisted everything *except* the Overall Force.
  Reported by a community user testing on a 12 Nm wheelbase.

### Note on live Overall Force
- Moving the Overall Force slider in the plugin doesn't apply in real
  time — the firmware needs a deliberate save to commit it. Two
  alternatives for live changes during a session :
  - Bind `Asetek.FFB.Force.Low/Medium/High/Max` to a button on your
    wheel / button box — these presets apply instantly.
  - Bind `Asetek.ApplyAndSave` to a button — workflow becomes
    *slider → press button → applied*.
- All other sliders (Damping, Friction, Inertia, Anti-Oscillation,
  HF Limit, Slew Rate, Bumpstop, Steering Range, Cornering Force
  Assist) remain fully live as introduced in v1.6.0.

---

## v1.6.0 — Live FFB sliders (May 19, 2026)

### Added
- **All FFB sliders are now live.** Damping, Friction, Inertia,
  Anti-Oscillation, HF Limit, Slew Rate, Bumpstop, Steering Range
  and Cornering Force Assist react instantly when you move the
  slider — no save, no restart, no audible click.
- This unblocks the upcoming **Adaptive FFB Zones Phase 2** module
  (auto-soften your profile in approach of learned hot zones like
  the Karussell or kerbs).

### Note
- Overall Force still requires a Save click (see v1.6.1 release notes
  for live alternatives).

---
