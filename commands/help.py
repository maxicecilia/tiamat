import click
from rich.console import Console
from rich.table import Table
from rich import print as rprint

console = Console()

# Define command categories and their display order
COMMAND_CATEGORIES = {
    "GH Repos": ["check", "createpr", "releases", "bump"],
    "GH Actions": ["run", "deploy"],
    "Jira": ["jira", "issues", "projects", "issue", "sprint-report"],
    "Other": ["help", "settings", "shell", "exit"],
}

# For commands not explicitly categorized
DEFAULT_CATEGORY = "Other"


def register_help_command(cli):
    @cli.command()
    @click.argument("command_name", required=False)
    def help(command_name=None):
        """Show help for Tiamat commands.

        If COMMAND_NAME is specified, show detailed help for that command.
        """
        # Create a context for getting command help info
        ctx = click.Context(cli, info_name="tiamat", parent=None)

        if command_name:
            # Find the command
            cmd = cli.get_command(ctx, command_name)
            if cmd:
                # Show help for specific command
                help_text = cmd.get_help(ctx)
                rprint(
                    f"[bold blue]Help for command [cyan]{command_name}[/cyan]:[/bold blue]\n"
                )
                click.echo(help_text)
            else:
                rprint(
                    f"[bold red]Error:[/bold red] Command '{command_name}' not found."
                )
        else:
            # General help with command descriptions
            rprint("\n[bold blue]🐉 Tiamat - Repository Management Tool[/bold blue]")
            rprint(
                "\nTiamat helps you manage GitHub repositories, check pending commits, create PRs, "
                "run GitHub Actions workflows, and interact with Jira."
            )

            rprint("\n[bold cyan]Quick Start:[/bold cyan]")
            rprint("  • Run with no arguments to enter interactive shell mode")
            rprint("  • Use `check main...release` to compare branches")
            rprint("  • Use `createpr main...release` to create PRs")
            rprint('  • Use `jira "sprint = current()"` to search Jira issues')

            # Get all commands and their help text
            all_commands = {}
            for cmd_name in cli.list_commands(ctx):
                cmd = cli.get_command(ctx, cmd_name)
                help_text = cmd.short_help or cmd.help.split("\n")[0]
                all_commands[cmd_name] = help_text

            # Organize commands by category
            categorized_commands = {}
            # Initialize with predefined categories
            for category in COMMAND_CATEGORIES:
                categorized_commands[category] = []

            # Add default category for uncategorized commands
            categorized_commands[DEFAULT_CATEGORY] = []

            # Sort commands into categories
            for cmd_name, help_text in all_commands.items():
                # Find which category this command belongs to
                found_category = False
                for category, commands in COMMAND_CATEGORIES.items():
                    if cmd_name in commands:
                        categorized_commands[category].append((cmd_name, help_text))
                        found_category = True
                        break

                # If not found in any category, put in default
                if not found_category:
                    categorized_commands[DEFAULT_CATEGORY].append((cmd_name, help_text))

            # Sort commands within each category alphabetically
            for category in categorized_commands:
                categorized_commands[category].sort(key=lambda x: x[0])

            # Create a single table for all commands, grouped by category
            rprint("\n[bold cyan]Available Commands:[/bold cyan]")
            table = Table()
            table.add_column("Category", style="blue")
            table.add_column("Command", style="green")
            table.add_column("Description", style="cyan")

            # Add each category of commands to the table
            for category in COMMAND_CATEGORIES.keys():
                commands = categorized_commands[category]
                if not commands:
                    continue

                # Add each command in this category
                for i, (cmd_name, help_text) in enumerate(commands):
                    # Only show category name for the first row of each category
                    if i == 0:
                        table.add_row(category, cmd_name, help_text)
                    else:
                        table.add_row("", cmd_name, help_text)

                # Add an empty row for visual separation between categories
                if category != list(COMMAND_CATEGORIES.keys())[-1]:
                    table.add_row("", "", "")

            # Add any uncategorized commands at the end
            uncategorized = categorized_commands[DEFAULT_CATEGORY]
            if uncategorized and DEFAULT_CATEGORY not in COMMAND_CATEGORIES:
                table.add_row("", "", "")  # Add separator
                for i, (cmd_name, help_text) in enumerate(uncategorized):
                    if i == 0:
                        table.add_row(DEFAULT_CATEGORY, cmd_name, help_text)
                    else:
                        table.add_row("", cmd_name, help_text)

            console.print(table)

            rprint("\n[bold cyan]Usage Examples:[/bold cyan]")
            rprint(
                "  • [green]check main...develop[/green] - Check pending commits from main to develop"
            )
            rprint(
                "  • [green]check main...release coralreef[/green] - Check specific repository"
            )
            rprint(
                "  • [green]createpr develop...main[/green] - Create PRs for all repos"
            )
            rprint("  • [green]bump coralreef --patch[/green] - Create a patch release")
            rprint(
                '  • [green]jira "sprint = current()"[/green] - Search current sprint issues'
            )
            rprint("  • [green]settings[/green] - Show current settings")

    # Return a reference to the command for direct usage in shell mode
    return help
