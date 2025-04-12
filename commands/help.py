import click
from rich.console import Console
from rich.table import Table
from rich import print as rprint

console = Console()


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
                "\nTiamat helps you manage GitHub repositories, check pending commits, and create PRs."
            )

            rprint("\n[bold cyan]Quick Start:[/bold cyan]")
            rprint("  • Run with no arguments to enter interactive shell mode")
            rprint("  • Use `check main...release` to compare branches")
            rprint("  • Use `createpr main...release` to create PRs")

            rprint("\n[bold cyan]Available Commands:[/bold cyan]")
            commands = []
            for cmd_name in sorted(cli.list_commands(ctx)):
                cmd = cli.get_command(ctx, cmd_name)
                help_text = cmd.short_help or cmd.help.split("\n")[0]
                commands.append((cmd_name, help_text))

            table = Table()
            table.add_column("Command", style="green")
            table.add_column("Description", style="cyan")

            for cmd_name, help_text in commands:
                table.add_row(cmd_name, help_text)

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
            rprint("  • [green]settings[/green] - Show current settings")

            rprint("\n[bold cyan]Tips:[/bold cyan]")
            rprint("  • In shell mode, commands don't need the 'tiamat' prefix")
            rprint(
                "  • Use [green]help <command>[/green] for detailed help on specific commands"
            )
            rprint("  • Branch comparison spec can use '..' or '...' (like Git)")

    # Return a reference to the command for direct usage in shell mode
    return help
