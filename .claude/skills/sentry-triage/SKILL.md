---
name: sentry-triage
description: Monthly Sentry triage for ECS. Reads unresolved issues across all production projects, classifies them, and writes one fix handoff per real bug under plans/sentry/. Prepares work for other agents; never fixes code itself. Use when the user asks to triage Sentry, review production errors, or run the monthly bug review.
---

# Sentry triage

You prepare work; you do not fix it. Do not edit application code, run migrations, commit, or
change Sentry issue status. Your only writes are files under `plans/sentry/`.

Tool: `tools/sentry` (reads `SENTRY_*` from `.env`; you cannot read `.env` and must not try).
`tools/sentry --help` lists the commands: `issues`, `projects`, `show ID [-n N]`, `resolve`.

## 1. Collect
1. Read `plans/sentry/index.md` (create it from the template below if missing). It is the memory
   between runs: issue id -> category. Baseline date is in its header.
2. `tools/sentry issues --since <baseline or last run date> --all`. Skip ids already in the index
   unless `lastSeen` is newer than the index row's date (then it recurred: re-check it).
   This skill can run any number of times per month (the owner may run it mid-month after
   spotting something). A run only deals with issues that are new or recurred since the index row.
   If a recurred or new issue belongs to a group that already has a handoff, update that handoff
   (add the issue id, counts, any new evidence, and its resolve command) instead of writing a second
   file. If its handoff was already fixed and resolved in Sentry, say so: it is a regression.
3. Sentry has one issue per project for the same bug. Group issues that share a root cause
   (same exception + same top in-app frame), but confirm by reading traces, not by title alone.

## 2. Investigate each group
- `tools/sentry show <id> -n 3` for at least two issues of the group when it spans projects.
- Read the code at the frames (`tools/pyx show <file> Class.method`) before judging.
- Classify as exactly one of:
  - **bug**: deterministic server defect, including unhandled user input that causes a 500
  - **noise**: expected or harmless, should be filtered in `ecs/settings.py` (`ignore_errors` /
    `before_send`), not fixed
  - **fixed**: not seen since a known fix; propose resolving
  - **infra**: deployment/config, not application code
  - **unclear**: say what is missing to decide
- Do not call something a client or caching error without evidence in the trace. If the server
  fails on input, that is a bug even if the client caused the input.

## 3. Write handoffs
One file per **bug** (and per **infra**/**unclear** worth acting on):
`plans/sentry/<YYYY-MM>/<short-slug>.md`, using this template. Another agent starts from this
file with no other context, so it must stand alone.

```
# <one-line problem>
Class: bug | infra | unclear        Severity: user-facing 500 | data loss | background job | cosmetic
Sentry: <project> <id> (<count>x, <first>..<last>), ... one line per issue in the group
Transaction/endpoint: <url pattern or celery task>

## Evidence
Condensed trace (in-app frames only), the decisive variables, and the request/body fields that
matter. Cite file:line. 2-3 events compared: what is the same, what differs.

## Root cause
What the code does wrong, and why this input reaches it. Mark anything unconfirmed as hypothesis,
with the query or step that would confirm it.

## Fix
Minimal change, where it belongs (follow CLAUDE.md: factories for test data, ruff, no production
changes for test tooling). List any decision the owner must make before coding.

## Verify
Reproduction steps using `ecs/utils/factories.py` / `seed_scenario`, expected before/after, and the
`tools/sentry issues --since <deploy date>` check after deploy.

## After deploy
tools/sentry resolve <id> <id> ...        # resolve; Sentry reopens it on regression
```

Rules for handoff content:
- **No personal data.** The SDK sends PII (`send_default_pii=True`). Replace names, emails, user
  ids, document titles and form values with placeholders. Keep only structure and ids of records.
- Quote error text and code exactly; do not paraphrase traces.
- Do not paste whole SQL breadcrumbs.

## 4. Update the index and report
`plans/sentry/index.md` format (one row per Sentry issue):

```
# Sentry triage index        baseline: 2026-10-26     last run: <date>
| id | project | title | category | handoff / note | seen up to |
```
`noise` rows record the filter that covers them. `fixed` rows record the evidence.

Set `last run` in the index header to today and keep every row's `seen up to` current.

Final message to the user, short: counts per category, the handoff files written or updated,
open handoffs from earlier runs that are still unfixed (rows with category `bug` whose issues are
still unresolved in Sentry), which issues
you propose to resolve or ignore (with the exact `tools/sentry resolve` command, not executed),
and anything `unclear`.
