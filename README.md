<code style="color : red"><b>:warning: Disclaimer!!! This was entirely done by vibecoding hard. Handle with caution. :warning:</b></code>

# Tiamat

A command-line tool for managing GitHub repositories, pull requests, releases, and GitHub Actions workflows.

## Features

- Repository management and comparison
- Pull request creation
- Release management with semantic versioning
- GitHub Actions workflow triggering
- Interactive shell with tab completion
- Slack integration for notifications

## Installation

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/tiamat.git
cd tiamat
```

# Install dependencies
```bash
uv sync
```
create a `.env` file and add:
- GITHUB_TOKEN: your github access token
- REPOSITORIES: a comma separated list of repositories, in the format `org/repo_name`
- SLACK_BOT_TOKEN: your slack bot token (optional, for Slack integration)
- SLACK_WEBHOOK_URL: your slack webhook URL (optional, alternative to bot token)
- SLACK_DEFAULT_CHANNEL: default slack channel for notifications (optional, defaults to "#general")

## Usage
```bash
uv run python main.py
```

Use `help` to check for available commands.
```bash
(Command history saved to /Users/mcecilia/.tiamat_history)

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
  • check main...release coralreef - Check specific repository
  • createpr develop...main - Create PRs for all repos
  • settings - Show current settings

Tips:
  • In shell mode, commands don't need the 'tiamat' prefix
  • Use help <command> for detailed help on specific commands
  • Branch comparison spec can use '..' or '...' (like Git)

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

