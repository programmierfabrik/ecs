# Python navigation

Use `tools/pyx` (stdlib only, no install) before grep or line-range reads:

- `tools/pyx outline <file|dir>` — symbols with line ranges, signatures, return types, docstring lines
- `tools/pyx show <file> Class.method` — one symbol in full
- `tools/pyx find <name> [dir]` — definitions and references, each with its enclosing symbol

# Linting

- Ruff is configured in `[tool.ruff]` in `pyproject.toml`; run it with `uvx ruff check <path>`. Do not use black, flake8, isort or pylint.
- A hook runs ruff on every edited `.py` file. Fix violations your edit introduced; leave pre-existing ones alone.
- No `# noqa` without a rule code. Do not run `ruff format`: the codebase is not formatted with it.
