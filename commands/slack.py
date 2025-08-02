import click
from rich import print as rprint
from services.slack import SlackService


def register_slack_commands(cli):
    """Register Slack-related commands with the CLI"""

    @cli.command()
    @click.argument("channel", required=True)
    @click.argument("message", nargs=-1, required=True)
    @click.option("--username", help="Custom username for the message")
    @click.option("--emoji", help="Custom emoji for the message")
    def send(channel, message, username, emoji):
        """Send a message to a Slack channel.

        Args:
            channel: Channel name or ID (e.g., '#general' or 'C1234567890')
            message: The message to send (can contain spaces)

        Examples:
          - send #general "Hello from Tiamat!"
          - send #team-eng "Testing with spaces in message"
          - send #deployments "Deployment completed" --username "Deploy Bot" --emoji ":rocket:"
        """
        # Join the message parts back together
        full_message = " ".join(message)

        success = SlackService.send_message(
            channel=channel,
            message=full_message,
            username=username,
            icon_emoji=emoji,
            tag_be_developers=True,
        )

        if success:
            rprint(f"[bold green]✅ Message sent to {channel}[/bold green]")
        else:
            rprint(f"[bold red]❌ Failed to send message to {channel}[/bold red]")

    return send
