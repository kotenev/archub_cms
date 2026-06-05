---
name: checks
description: Run the full local CI gate for ArcHub CMS before committing — ruff lint, ruff format, compileall syntax check, and pytest. Use when asked to verify changes, run checks, or prep a commit.
---

Run the same checks CI runs, in this order, from the repo root. Report results clearly and stop at the first hard failure so the user can fix it.

1. `ruff check src tests` — lint. If it reports fixable issues, mention `ruff check --fix src tests`.
2. `ruff format src tests` — format. Report whether any files were reformatted.
3. `python -m compileall -q src` — syntax gate.
4. `pytest -q` — test suite.

If `$ARGUMENTS` names a specific test or path, scope step 4 to it (e.g. `pytest -q $ARGUMENTS`) but still run steps 1–3 on `src tests`.

After all steps, give a one-line summary: which passed, what (if anything) failed, and the exact command to reproduce a failure.
