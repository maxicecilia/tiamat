<code style="color : red"><b>:warning: Disclaimer!!! This was entirely done by vibecoding hard. Handle with caution. :warning:</b></code>

# Tiamat

<p align="left">
  <img src="https://raw.githubusercontent.com/maxicecilia/tiamat/main/assets/tiamat_logo.svg" alt="Tiamat Logo" width="200"/>
</p>


Release tooling for a set of GitHub repositories: compare branches, open release PRs, bump versions, trigger deploy workflows and track DORA metrics. It comes as a command-line tool with an interactive shell, and (since v2) as a local web dashboard.

## Features

- **Dashboard (v2)**: a local web UI to deploy, follow runs, see pending changes, open release PRs, create releases and track DORA metrics per team. See [Dashboard](#dashboard-web-ui).
- Repository management and branch comparison
- Pull request creation
- Release management with semantic versioning
- GitHub Actions workflow triggering
- Interactive shell with tab completion
- Slack integration for notifications

## Quick start

```bash
uv sync
uv run python main.py        # CLI / interactive shell
docker compose up --build    # dashboard on http://localhost:8000
```

## Installation

```bash
# Clone the repository
git clone https://github.com/maxicecilia/tiamat.git
cd tiamat
```

Install dependencies:
```bash
uv sync
```
Create a `.env` file and add:
- GITHUB_TOKEN: your github access token
- GITHUB_TOKEN_<ORG>: optional token for one GitHub org, used instead of GITHUB_TOKEN for that org's repos. The org name is uppercased with other characters turned into `_`, so `my-org/app` uses `GITHUB_TOKEN_MY_ORG`
- REPOSITORIES: a comma separated list of repositories, in the format `org/repo_name`
- REPOSITORIES_v2: a comma separated list of repositories that use the v2 release workflows (the `v2` entries in your presets). `deploy <env> <repo>` triggers these with only the branch as input, and `bump` is not needed since the workflow creates the release automatically
- TIAMAT_PRESETS_FILE: optional path to your deploy presets (see below)
- SLACK_BOT_TOKEN: your slack bot token (optional, for Slack integration)
- SLACK_WEBHOOK_URL: your slack webhook URL (optional, alternative to bot token)
- SLACK_DEFAULT_CHANNEL: default slack channel for notifications (optional, defaults to "#general")
- BETA_REPOSITORIES, ML_REPOSITORIES, DATAOPS_REPOSITORIES, FE_REPOSITORIES: optional team lists, in the same format. `stats --team` uses them, and the dashboard uses them to assign teams on its first start (repos in `REPOSITORIES` and `FE_REPOSITORIES` are `fnd`; `FE_REPOSITORIES` also marks frontend repos for Slack)

### Deploy presets
`deploy <environment> <repo>` and the dashboard's Deploy buttons run the GitHub Actions workflow set for each environment. Copy `presets.example.json` to `presets.json` (not tracked) and fill in your workflow files, inputs and default branch per environment:
```bash
cp presets.example.json presets.json
```
Without a `presets.json`, the generic example is used. The dashboard imports the presets into its database on first start. After that, edit them in Settings → Workflows.

## Usage
```bash
uv run python main.py
```

Use `help` to check for available commands.
```bash
(Command history saved to ~/.tiamat_history)

🐉 Tiamat Interactive Shell

Welcome to Tiamat! Type commands directly without the 'tiamat' prefix.
  • Type help for a list of available commands
  • Type help <command> for help with a specific command
  • Type exit or press Ctrl+D to exit
  • Use ↑/↓ arrow keys to navigate command history
  • Press TAB to autocomplete commands and repository names
     Current Settings
┌──────────────┬─────────┐
│ Base Branch  │ main    │
│ Head Branch  │ release │
│ GitHub Token │ Set ✅  │
└──────────────┴─────────┘

tiamat> help

🐉 Tiamat - Repository Management Tool

Tiamat helps you manage GitHub repositories, check pending commits, and create PRs.

Quick Start:
  • Run with no arguments to enter interactive shell mode
  • Use `check main...release` to compare branches
  • Use `createpr main...release` to create PRs

Available Commands:
┏━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Command   ┃ Description                                       ┃
┡━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ bump      │ Bump version and create a new release.            │
│ check     │ Check for pending commits between branches.       │
│ createpr  │ Create pull requests between branches.            │
│ deploy    │ Run a predefined workflow.                        │
│ help      │ Show help for Tiamat commands.                    │
│ list      │ List all repositories.                            │
│ releases  │ List recent releases for a repository.            │
│ run       │ Run a GitHub Actions workflow.                    │
│ settings  │ Display current settings.                         │
│ shell     │ Start an interactive shell session.               │
│ workflows │ List GitHub Actions workflows for a repository.   │
└───────────┴───────────────────────────────────────────────────┘

Usage Examples:
  • check main...develop - Check pending commits from main to develop
  • check main...release my-service - Check specific repository
  • createpr develop...main - Create PRs for all repos
  • settings - Show current settings

Tips:
  • In shell mode, commands don't need the 'tiamat' prefix
  • Use help <command> for detailed help on specific commands
  • Branch comparison spec can use '..' or '...' (like Git)

## Dashboard (web UI)

Tiamat also runs as a local web dashboard: a FastAPI backend (`api/`) with a SQLite database and a React + Vite + shadcn/ui frontend (`frontend/`). The CLI keeps working and uses the same `services/`.

On first start, the API applies database migrations and imports your `.env` repo lists (`REPOSITORIES`, `REPOSITORIES_v2`, and the team lists; a repo in several team lists joins all of those teams) and the deploy presets into the database. This import runs once per database. After that the database is the source of truth, so edits and deletes made in the dashboard are never overwritten from `.env`.

### What you can do
- **Deploys** has two tabs: **Environments** and **Recent deployments** (the last 100 deploys started from the dashboard, filterable by project and environment, with status, duration and **Dismiss** for stuck ones).
- **Environments**: one table of every project and environment. **Deploy** opens a short confirmation with the workflow, inputs and an editable branch, then triggers the GitHub Actions `workflow_dispatch` run. Tiamat follows each run in the background (every 10s, set with `TIAMAT_POLL_SECONDS`) and shows its status, duration and a link to the run. **Refresh releases** pulls the latest GitHub releases into the database. While a deploy to a project and environment is running, a second one is refused. Presets can lock the branch (prod presets are locked by default). A locked environment always deploys the preset's branch, or the project's base branch if the preset has none, and the API refuses any other branch. Unlock it in Settings → Workflows. If GitHub doesn't confirm a dispatch (for example, after a timeout), Tiamat keeps looking for the run instead of marking the deploy as failed. A deploy Tiamat can't track any more ends as "Check GitHub", and **Dismiss** clears one that is stuck.
- **New release** (the tag button next to a project's latest release on Deploys): the dashboard version of `bump`. It shows the latest release, how many commits on the target branch aren't released yet, and the next patch, minor and major versions. It then creates the GitHub release and tag with generated notes. Tags that aren't plain `x.y.z` (for example `3.4.0.web`) need the version typed in, because bumping them automatically would restart at 0.x. If a newer release appeared since you opened the dialog, it refuses and asks you to review. v2 projects are skipped, because their workflows create releases.
- **Pending changes** (on the Deploys page): the dashboard version of `check` and `createpr`. Each project row shows how many commits on its head branch aren't on its base yet. Only starred projects are compared on GitHub when the page opens; use a row's refresh button, or **Check the rest**, for the others. You can star up to 5 projects. Open the row to see them (newest first, with a link to the full diff) and whether a release PR is already open. Pick another target ← origin pair (`main ← release`, `release ← develop`, or a **Custom** one, which is remembered in this browser) to compare other branches. **Create PR** opens head → base PRs with the same title as the CLI, and the page's **Create PRs** button does it for every listed project with pending commits on its own branches. New PRs can be announced on Slack the same way the CLI does it: one message for frontend repos (tagged `frontend`) and one for backend repos. PRs that were already open aren't announced again.
- **Metrics**: DORA-style metrics per team for the last 3, 6 or 12 months, using the same rules as `stats`: releases count as deploys, lead time runs from the oldest commit since the previous release, change failure rate comes from `[hotfix]`, `[rollback]` and similar markers in release notes, and tickets are `[ABC-123]` references. The page shows summary tiles, monthly charts, team and project tables, and recent releases. **Refresh data** fetches releases and works out lead times in the background (one GitHub compare call per release, done once and then kept). A project in several teams counts toward each of them, but never twice for the same team.
- **Stars**: click the star next to a project on any page to keep it at the top of every list. A **starred** filter pill shows only starred projects.
- **Settings**, with three tabs:
  - **Projects**: add, edit, archive or delete repos. Set one or more teams, tags, workflow version (v1/v2), base and head branches, and which deploy environments each project uses.
  - **Workflows**: manage deploy presets, meaning which GitHub Actions workflow file, branch and inputs run per environment and workflow version. Renaming or deleting a preset updates the projects that use it.
  - **Teams & tags**: create, rename and delete teams and tags, with a project count for each. Both are stored lowercase.
- **Themes**, picked at the bottom of the sidebar:
  - **Boring**: the plain default, with light, dark and system modes.
  - **Phosphor**: a green-on-black terminal look.
  - **Gibson**: neon magenta and cyan.
  - **Tiamat**: each area is one of the dragon's heads, with its own colour. Deploys is red, Metrics is white, Settings is black. Green and blue are kept for future integrations such as Jira.

### Run with Docker
```bash
docker compose up --build
```
Open http://localhost:8000 (bound to localhost only, because the API has no auth). The database is saved to `./data/tiamat.db`, and `.env` is passed to the container if it exists. Set `TIAMAT_PORT` to use a different port.

### Run for development
```bash
uv run uvicorn api.main:app --reload       # API on :8000
cd frontend && npm install && npm run dev  # UI on :5173, sends /api to :8000
```

### Settings
| Variable | Default | Purpose |
|---|---|---|
| `TIAMAT_DATA_DIR` | `./data` (`/data` in Docker) | Where the SQLite file lives |
| `TIAMAT_DATABASE_URL` | `sqlite:///$TIAMAT_DATA_DIR/tiamat.db` | Full SQLAlchemy URL |
| `TIAMAT_CORS_ORIGINS` | `http://localhost:5173` | Comma-separated allowed origins |
| `TIAMAT_POLL_SECONDS` | `10` | How often running deploys are checked on GitHub |
| `TIAMAT_ALLOWED_HOSTS` | `localhost,127.0.0.1,testserver` | Host names the API answers to. The API has no login, so keep this local. |
| `TIAMAT_DISABLE_POLLER` | unset | Set to `1` to turn off the background run poller (tests do this) |

### Schema changes
```bash
uv run alembic revision --autogenerate -m "describe change"
uv run alembic upgrade head   # also applied automatically on API start
```

### Tests
```bash
uv run pytest
uv run ruff check api tests migrations
```

## Slack Integration

Tiamat includes Slack integration for sending notifications about command executions. This is useful for team collaboration and keeping track of repository operations.

### Setup

1. **Bot Token Method** (Recommended):
   - Create a Slack app and get a Bot User OAuth Token
   - Set `SLACK_BOT_TOKEN` in your `.env` file
   - Invite the bot to your channels

2. **Webhook Method** (Alternative):
   - Create a Slack webhook URL
   - Set `SLACK_WEBHOOK_URL` in your `.env` file

3. **Optional Configuration**:
   - Set `SLACK_DEFAULT_CHANNEL` to specify a default channel for notifications

### Slack Commands

- `send <channel> <message>` - Send a custom message to a Slack channel (channel name without quotes)

### Automatic Notifications

Some commands automatically send Slack notifications:
- `merge` - Sends notifications when PRs are merged or merge attempts fail

### Examples

```bash
# Send a custom message
send #deployments "Deployment completed successfully!"
send #team-eng "Testing with spaces in message"

```

tiamat>
```

