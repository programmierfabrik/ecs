# Python navigation

Use `tools/pyx` (stdlib only, no install) before grep or line-range reads:

- `tools/pyx outline <file|dir>` — symbols with line ranges, signatures, return types, docstring lines
- `tools/pyx show <file> Class.method` — one symbol in full
- `tools/pyx find <name> [dir]` — definitions and references, each with its enclosing symbol

# Linting

- Ruff is configured in `[tool.ruff]` in `pyproject.toml`; run it with `uvx ruff check <path>`. Do not use black, flake8, isort or pylint.
- A hook runs ruff on every edited `.py` file. Fix violations your edit introduced; leave pre-existing ones alone.
- No `# noqa` without a rule code. Do not run `ruff format`: the codebase is not formatted with it.

# Test data and verification

- Create domain objects with `ecs/utils/factories.py`, which follows the real lifecycle: `create_submission_form(**fields)` (study type is just fields), `create_meeting`, `schedule` (runs initial review and categorization, which put the study on a meeting), `start_meeting`, `record_vote`, `end_meeting`, `finish_vote_workflow` (or `vote_in_meeting` for all of it). Pass only the fields the scenario is about; placeholders fill the rest. Never create a Vote directly. Do tasks with `do_task(data, node_uid=None, choice=..., user=None, **form_fields)` or `run_workflow(data, until=node_uid, fields={node_uid: {...}})`: each one saves the task page's form first (categorization, checklist, vote preparation/review, signing), then completes the task. Choice and user are picked automatically unless you name them. Add the tasks the office creates by hand with `create_task(submission, node_uid, assign_to=None)` (specialist, statistical, external review …); a specialist review puts its user on the TOP, which is what `schedule(participants=...)` does. For a ready local scenario: `manage.py seed_scenario study [--set FIELD=VALUE] [--votes 3b 1] [--lane board|expedited|thesis|localec] [--until scheduled|started|voted|ended|published|NODE_UID] [--protocol]` (DEBUG only); a node uid stops once that task is open. Then `manage.py seed_scenario tasks SUBMISSION [--do NODE_UID [--choice X] [--user EMAIL] [--set FIELD=VALUE]]` lists or does the open tasks of the study, its votes and checklists. The django MCP caches modules, so run a just-edited command from the shell.
- Verify mails in Mailpit (`curl -s localhost:8025/api/v1/messages`), never by mocking `deliver`: a mock proves the recipients, not that anything was sent.
