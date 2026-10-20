<!-- Generated: 2026-06-16 | Updated: 2026-06-16 -->

# tiamat

## Purpose
A Python CLI tool for managing GitHub repositories across an organization. Tiamat wraps the GitHub and Slack APIs to automate common release-engineering tasks: comparing branches, creating PRs, bumping semantic versions, triggering GitHub Actions workflows, and sending Slack notifications. It runs as both a one-shot CLI and an interactive REPL shell.

## Key Files

| File | Description |
|------|-------------|
| `main.py` | Entry point; defines `cli` Click group, `TiamatContext`, `check`, `createpr`, `list`, `settings` commands, and wires all sub-command registrations |
| `pyproject.toml` | Project metadata and dependencies (click, rich, requests, dotenv, ipython) |
| `README.md` | User-facing setup and usage documentation |
| `.env` | Local environment variables (never committed); see README for required keys |
| `.python-version` | Pins the Python interpreter version for `uv` |
| `uv.lock` | Reproducible dependency lockfile managed by `uv` |

## Subdirectories

| Directory | Purpose |
|-----------|---------|
| `commands/` | Click command registrations, one module per feature area (see `commands/AGENTS.md`) |
| `services/` | API client abstractions for GitHub and Slack (see `services/AGENTS.md`) |
| `helpers/` | Shared utilities (currently empty placeholder, see `helpers/AGENTS.md`) |
| `assets/` | Static assets such as the project logo (see `assets/AGENTS.md`) |

## For AI Agents

### Working In This Directory
- `main.py` is the sole entry point; run it with `uv run python main.py`.
- Environment is loaded via `python-dotenv` at the top of `main.py` before any service imports — keep this order.
- `TiamatContext` is the Click context object that carries `base_branch` and `head_branch` across commands. Pass it with `@pass_tiamat_context`.
- `resolve_repo()` in `main.py` converts short repo names (e.g. `coralreef`) to full `org/repo` form using the `REPOSITORIES` env var. Commands in `commands/` replicate this locally — consider consolidating if adding more commands.
- Default branches are `main` (base) and `release` (head), configurable via `--base`/`--head` flags.

### Testing Requirements
- Run tests: `pytest`
- Lint: `ruff check`
- No test files exist yet; add them under a `tests/` directory following pytest conventions.

### Common Patterns
- All commands check `GITHUB_TOKEN` at call time and print a rich error if missing.
- Rich (`rprint`, `Console`, `Table`) is used for all terminal output — keep this consistent.
- Command registration follows the pattern: `register_<feature>_commands(cli, ...)` returns the command handle(s) for reference.

## Dependencies

### Internal
- `services/github.py` — used by `main.py` and all commands that touch GitHub
- `services/slack.py` — used by `main.py` (`createpr`) and `commands/slack.py`

### External
- `click` — CLI framework
- `rich` — terminal formatting
- `requests` — HTTP client for GitHub and Slack APIs
- `python-dotenv` — `.env` file loading

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
