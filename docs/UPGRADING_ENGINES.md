# Adding case studies and upgrading engines

## Add a new case study

1. Add the Python dynamics file to `tunerPID/case_studies/<Name>.py` with a top-level
   `dynamics(t, x, u)` function.
2. Add matching `gaTunerPID/case_studies/json/<Name>.json` metadata (`num_states`,
   `num_inputs`, target, channels, control limits, trim values, fixed targets).
3. Start the stack and confirm `GET /api/v1/catalog` lists the new entry.
4. Create it from the catalog, run a manual simulation, then a tiny GA optimization
   (`population_size=5`, `generations=2`, `seed=42`).
5. Add or update a golden fixture in `backend/tests/fixtures/golden/` only when the new
   snapshot is intentional, and run the contract tests.

## Upgrade an engine

Engines are read-only upstream repositories. Upgrade deliberately:

1. Check out and pin the new engine commit for both `gaTunerPID` and `tunerPID`.
2. Run `python scripts/verify_engines.py` to see exactly which tracked files changed.
3. Update `scripts/engine_sources.sha256` only after reviewing the diff:
   `python scripts/verify_engines.py --write`.
4. Run the contract tests (`backend/tests/contract`) and inspect differences.
5. Regenerate golden snapshots intentionally:
   `python scripts/baseline.py`.
6. Review golden diffs and run the full backend + frontend suites.
7. Rebuild Compose images and run `scripts/e2e_smoke.py`.
