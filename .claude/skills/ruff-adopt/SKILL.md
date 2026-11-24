---
name: ruff-adopt
description: Adopt one new ruff rule family in this repo (e.g. DJ, UP, B, S) - count violations, fix them safely in batches, then enable the rule in pyproject.toml. Use when asked to tighten linting or add ruff rules.
---

# Adopt a ruff rule family

Run ruff with `uvx ruff`. Do not run `ruff format`. Never commit; the user commits.

1. **Count**: `uvx ruff check ecs --select <RULES> --statistics`. Report the per-rule counts and how many are auto-fixable. If the total is large, propose splitting by rule code and ask which to start with.
2. **Safe fixes first**: `uvx ruff check ecs --select <RULES> --fix` (safe fixes only; never `--unsafe-fixes` without asking). Look at `git diff --stat` and spot-check a few hunks.
3. **Manual fixes**: fix the remaining violations in small groups by rule. A rule that is a false positive for this codebase (e.g. S-rules in tests) goes into `[tool.ruff.lint.per-file-ignores]` with a comment, never into a blanket `# noqa`.
4. **Verify**: `./manage.py check` plus the tests of the touched apps, or a real DB/HTTP flow when the test runner is unavailable. A rule whose fixes change behaviour (B, S, UP rewrites of Django code) needs this before enabling.
5. **Enable**: add the family to `select` in `[tool.ruff.lint]` in `pyproject.toml` only once `uvx ruff check ecs` is clean for it.
6. Summarise: rules enabled, files touched, anything left ignored and why.
