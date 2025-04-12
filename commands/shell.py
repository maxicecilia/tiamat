import os
import click
from rich.console import Console
from rich.table import Table
from rich import print as rprint

console = Console()


def register_shell_command(cli, repositories, github_token, TiamatContext):
    @cli.command()
    def shell():
        """Start an interactive shell session."""
        try:
            import readline
            import atexit
            import os.path

            # Set up history file
            histfile = os.path.expanduser("~/.tiamat_history")

            # Create history file if it doesn't exist
            if not os.path.exists(histfile):
                with open(histfile, "w") as f:
                    pass

            # Read history file
            try:
                readline.read_history_file(histfile)
                # Set history length
                readline.set_history_length(1000)
            except FileNotFoundError:
                pass

            # Tab completion for repository names and commands
            def completer(text, state):
                # Get the current line buffer and cursor position
                line = readline.get_line_buffer()
                line_parts = line.split()

                # Calculate which word position we're currently completing
                if text and len(line_parts) > 0 and line.endswith(text):
                    current_position = len(line_parts) - 1
                else:
                    current_position = len(line_parts)

                # Start with all commands as possible completions
                ctx = click.Context(cli, info_name="tiamat", parent=None)
                all_commands = sorted(cli.list_commands(ctx))

                # If it's the start of the line, offer commands
                if not line_parts or text == line:
                    matches = [c for c in all_commands if c.startswith(text)]
                    return matches[state] if state < len(matches) else None

                # Commands that accept repository arguments
                repo_commands = (
                    "check",
                    "createpr",
                    "releases",
                    "release",
                    "workflows",
                    "run",
                    "bump",
                )

                first_word = line_parts[0]

                # Handle repository completions
                if first_word in repo_commands:
                    # Determine if we're at the position where a repo should be completed
                    repo_position = False

                    if first_word == "releases" and current_position == 1:
                        # For 'releases', the repo is the first argument
                        repo_position = True
                    elif first_word == "release" and current_position == 2:
                        # For 'release', the repo is the second argument (after tag)
                        repo_position = True
                    elif first_word in ("check", "createpr"):
                        if current_position == 1 and not ".." in text:
                            # First arg could be a repo if it's not a branch spec
                            repo_position = True
                        elif current_position == 2 and any(
                            ".." in part for part in line_parts[1:current_position]
                        ):
                            # If there was a branch spec earlier, this position is for repo
                            repo_position = True

                    if repo_position:
                        # Offer short repo names first, then full repo names
                        short_repos = [r.split("/")[-1] for r in repositories]
                        full_repos = repositories

                        # Combine both short and full repo names for completion
                        all_repos = short_repos + full_repos
                        matches = [r for r in all_repos if r.startswith(text)]
                        return matches[state] if state < len(matches) else None

                # Branch name completions
                branch_option_commands = {"setbase", "setrelease", "setdev"}
                common_branches = [
                    "main",
                    "master",
                    "develop",
                    "release",
                    "staging",
                    "hotfix",
                ]

                # Handle branch name completions for set commands
                if first_word in branch_option_commands and current_position == 1:
                    matches = [b for b in common_branches if b.startswith(text)]
                    return matches[state] if state < len(matches) else None

                # For the run command, support branch completion
                if first_word == "run" and current_position > 2:
                    if text.startswith("--branch") or text.startswith("-b"):
                        options = ["--branch", "-b"]
                        matches = [opt for opt in options if opt.startswith(text)]
                        return matches[state] if state < len(matches) else None
                    elif (
                        line_parts[-2] in ("--branch", "-b")
                        and current_position == len(line_parts) - 1
                    ):
                        matches = [b for b in common_branches if b.startswith(text)]
                        return matches[state] if state < len(matches) else None
                    elif text.startswith("--input") or text.startswith("-i"):
                        options = ["--input", "-i"]
                        matches = [opt for opt in options if opt.startswith(text)]
                        return matches[state] if state < len(matches) else None

                # Add completion for bump options
                if first_word == "bump" and text.startswith("-"):
                    options = [
                        "--major",
                        "--minor",
                        "--patch",
                        "--branch",
                        "-b",
                        "--name",
                        "-n",
                        "--body",
                        "-m",
                        "--draft",
                        "--no-draft",
                        "--prerelease",
                        "--no-prerelease",
                    ]
                    matches = [opt for opt in options if opt.startswith(text)]
                    return matches[state] if state < len(matches) else None

            readline.set_completer(completer)
            readline.set_completer_delims(" \t\n;")
            readline.parse_and_bind("tab: complete")

            # Save history on exit
            atexit.register(readline.write_history_file, histfile)

            rprint(f"[dim](Command history saved to {histfile})[/dim]")
        except ImportError:
            rprint(
                "[yellow]Note: readline module not available, command history and tab completion disabled[/yellow]"
            )

        rprint("\n[bold blue]🐉 Tiamat Interactive Shell[/bold blue]")
        rprint(
            "\n[cyan]Welcome to Tiamat![/cyan] Type commands directly without the 'tiamat' prefix."
        )
        rprint("  • Type [green]help[/green] for a list of available commands")
        rprint(
            "  • Type [green]help <command>[/green] for help with a specific command"
        )
        rprint("  • Type [green]exit[/green] or press Ctrl+D to exit")
        rprint("  • Use [green]↑/↓[/green] arrow keys to navigate command history")
        rprint(
            "  • Press [green]TAB[/green] to autocomplete commands and repository names"
        )

        # Show current settings as a quick reference
        ctx = click.get_current_context()
        table = Table(title="Current Settings", show_header=False)
        table.add_column("Setting", style="dim")
        table.add_column("Value", style="green")

        ctx_obj = ctx.find_object(TiamatContext)
        table.add_row("Base Branch", ctx_obj.base_branch)
        table.add_row("Head Branch", ctx_obj.head_branch)
        table.add_row("GitHub Token", "Set ✅" if github_token else "Not Set ❌")

        console.print(table)
        rprint("")  # Empty line for spacing

        # Get reference to the help command
        help_command = cli.get_command(ctx, "help")

        while True:
            try:
                command = input("tiamat> ")
                command = command.strip()

                if not command:
                    continue

                if command.lower() in ("exit", "quit"):
                    break

                # Special handling for help command in shell mode
                if command.lower() == "help":
                    help_command.callback()
                    continue

                if command.lower().startswith("help "):
                    parts = command.split(maxsplit=1)
                    if len(parts) > 1:
                        help_command.callback(parts[1])
                        continue

                # Process the command
                try:
                    cli(command.split(), standalone_mode=False)
                except SystemExit:
                    pass  # Prevent click from exiting
                except Exception as e:
                    rprint(f"[bold red]Error:[/bold red] {str(e)}")

            except (KeyboardInterrupt, EOFError):
                break

        rprint("[bold blue]Goodbye! 👋[/bold blue]")

    # Return the command for reference
    return shell
