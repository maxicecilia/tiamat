<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-06-16 | Updated: 2026-06-16 -->

# commands

## Purpose
Click command registrations, one module per feature area. Each module exposes a `register_<feature>_commands(cli, ...)` function that attaches commands to the root `cli` group defined in `main.py` and returns the registered command handle(s) for reference. No business logic lives here — commands delegate immediately to `services/`.

## Key Files

| File | Description |
|------|-------------|
| `__init__.py` | Empty package marker |
| `actions.py` | Registers `run` (arbitrary workflow dispatch) and `deploy` (preset-based workflow dispatch with environment configs for staging/prod/demo) |
| `help.py` | Registers `help` command; displays categorized command table using `COMMAND_CATEGORIES` |
| `merge.py` | Registers `merge` command; merges a specific PR by number with confirmation prompt |
| `release.py` | Registers `bump` (semver bump + GitHub release creation) and `releases` (list recent releases) |
| `shell.py` | Registers `shell` command; starts a readline-based interactive REPL with tab completion and command history |
| `slack.py` | Registers `send` command; sends a free-form message to a Slack channel |

## For AI Agents

### Working In This Directory
- Every module follows the same registration pattern: a top-level `register_*` function takes `cli` (and optionally `REPOSITORIES`, `GITHUB_TOKEN`, etc.) and uses `@cli.command()` decorators inside it. Do not define commands at module level.
- `resolve_repo()` is duplicated in `actions.py`, `merge.py`, and `release.py`. If adding a new command that needs repo resolution, copy the same pattern or refactor to a shared helper in `helpers/`.
- `WORKFLOW_PRESETS` in `actions.py` is the place to add new predefined deploy targets (staging, prod, demo, etc.).
- `COMMAND_CATEGORIES` in `help.py` must be updated when adding new commands, otherwise they fall into the uncategorized "Other" bucket.
- `shell.py` hard-codes the list of `repo_commands` that get tab-completion for repository names — update it when adding repo-aware commands.

### Testing Requirements
- Run: `pytest`
- Lint: `ruff check`
- Commands can be tested with Click's `CliRunner` — invoke via `runner.invoke(cli, ['command', 'args'])`.

### Common Patterns
- All commands guard on `GITHUB_TOKEN` before making any API call.
- Confirmation prompts (`click.confirm`) are used before destructive/irreversible operations (merge, bump).
- Rich formatting (`rprint`, emoji prefixes) is used for all user-facing output — maintain this style.

## Dependencies

### Internal
- `services/github.py` — `GitHubService`, `GITHUB_TOKEN`
- `services/slack.py` — `SlackService`

### External
- `click` — command and argument decorators
- `rich` — terminal output formatting

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
