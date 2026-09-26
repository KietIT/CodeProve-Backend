# Simulated golden-set sessions (P1.3b)

The 40 scripted sessions played through production on 2026-09-25 with
`python -m app.features.calibration.simulate` (39 exported; sim-15 has no code snapshot).

- `scripts/sim-XX.json`: what each simulated student did (built by `build_scripts.py`).
- `profiles.json`: the intended level per axis (verification = what actually happened), used only as a sanity check.
- `answers.json`: the explain-back answers written for the generated questions.

Kept out of git on purpose: account passwords (`state.json`), raw logs, the raters' exports,
`engine.json` and `keys.json`. Results: `docs/calibration/results-2026-09-26.md`.
