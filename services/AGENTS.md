<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-06-16 | Updated: 2026-06-16 -->

# services

## Purpose
API client abstractions for external services. Each module encapsulates all HTTP communication with one platform, exposing a single static-method class. Commands and `main.py` import from here and never call `requests` directly.

## Key Files

| File | Description |
|------|-------------|
| `__init__.py` | Empty package marker |
| `github.py` | `GitHubService` — all GitHub REST API calls: branch comparison, PR creation/merge, releases, workflow dispatch, semver bump logic |
| `slack.py` | `SlackService` — Slack messaging via Bot Token API or Incoming Webhook, with optional developer tagging |

## For AI Agents

### Working In This Directory

**github.py**
- `GITHUB_TOKEN` and `HEADERS` are module-level constants read from env at import time; they are not refreshed per-call. If the token changes at runtime, the process must restart.
- `_get_url(path)` is the sole URL builder — always use it instead of string-concatenating `GITHUB_URL`.
- `GitHubService` uses `@staticmethod` throughout; do not introduce instance state.
- `bump_version()` is pure logic (no I/O) and safe to unit-test in isolation.
- `trigger_workflow()` resolves workflow filenames to numeric IDs with two passes (exact path match, then substring match) before dispatching — be aware of this when naming workflow files.
- `create_pull_request()` handles HTTP 422 (PR already exists) by fetching and returning the existing PR URL.

**slack.py**
- `SlackService.send_message()` auto-selects webhook vs. Bot API depending on which env var is set (webhook takes priority).
- Developer tagging (`tag_be_developers`, `tag_fe_developers`) prepends `<@user_id>` mentions from `SLACK_BE_DEVELOPERS` / `SLACK_FE_DEVELOPERS` env vars (comma-separated Slack user IDs).
- `is_configured()` is a cheap pre-flight check used by `settings` command and callers before sending.

### Testing Requirements
- Run: `pytest`
- Lint: `ruff check`
- Both services make real HTTP calls — mock `requests.get`/`requests.post`/`requests.put` when unit-testing.
- `bump_version()` can be tested without mocking.

### Common Patterns
- All methods return a `bool` or the created resource URL on success, `False`/`None` on failure.
- Failures print a rich error message directly and return — callers do not raise exceptions.
- HTTP status codes are checked explicitly; unexpected statuses print `response.text` for debugging.

## Dependencies

### External
- `requests` — HTTP client
- `rich` — terminal error/success output
- GitHub REST API v3 (`https://api.github.com`)
- Slack Web API (`https://slack.com/api`) / Incoming Webhooks

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
