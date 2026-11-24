#!/usr/bin/env python3
"""PostToolUse hook: lint the edited .py file with ruff and report violations to Claude.

Report only, no autofix and no formatting: the codebase is not ruff-formatted, so
rewriting a touched file would bury the real change in the diff.
"""
import json
import os
import subprocess
import sys

payload = json.load(sys.stdin)
path = payload.get("tool_input", {}).get("file_path", "")
if not path.endswith((".py", ".pyi")) or not os.path.isfile(path):
    sys.exit(0)

cwd = payload.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR", ".")
try:
    r = subprocess.run(
        ["uvx", "ruff", "check", "--no-fix", "--force-exclude", "--output-format", "concise", path],
        cwd=cwd, capture_output=True, text=True, timeout=60)
except (FileNotFoundError, subprocess.TimeoutExpired):
    sys.exit(0)  # tooling unavailable: never block editing

if r.returncode == 1:
    print(r.stdout.strip(), file=sys.stderr)
    print("Fix violations your edit introduced; leave pre-existing ones alone.", file=sys.stderr)
    sys.exit(2)
