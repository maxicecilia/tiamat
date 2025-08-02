<code style="color : red"><b>:warning: Disclaimer!!! This was entirely done by vibecoding hard. Handle with caution. :warning:</b></code>

# Tiamat

A command-line tool for managing GitHub repositories, pull requests, releases, and GitHub Actions workflows.

## Features

- Repository management and comparison
- Pull request creation
- Release management with semantic versioning
- GitHub Actions workflow triggering
- Interactive shell with tab completion

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
tiamat>
```

