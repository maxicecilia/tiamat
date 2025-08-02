import os
import requests
from rich import print as rprint
from typing import Optional


# Slack API configuration
SLACK_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")
SLACK_API_URL = "https://slack.com/api"
SLACK_BE_DEVELOPERS = os.getenv("SLACK_BE_DEVELOPERS", "").split(",")
SLACK_FE_DEVELOPERS = os.getenv("SLACK_FE_DEVELOPERS", "").split(",")


class SlackService:
    """Service for interacting with Slack API"""

    @staticmethod
    def is_configured() -> bool:
        """Check if Slack is properly configured"""
        return bool(SLACK_TOKEN or SLACK_WEBHOOK_URL)

    @staticmethod
    def send_message(
        message: str,
        channel: Optional[str] = None,
        username: Optional[str] = None,
        icon_emoji: Optional[str] = None,
        attachments: Optional[list] = None,
        tag_be_developers: bool = False,
        tag_fe_developers: bool = False,
    ) -> bool:
        """
        Send a message to a Slack channel

        Args:
            channel: Channel name or ID (e.g., '#general' or 'C1234567890')
            message: The message text to send
            username: Custom username for the message (optional)
            icon_emoji: Custom emoji for the message (optional)
            attachments: List of attachment objects (optional)
            tag_developers: Whether to tag developers in the message
        Returns:
            bool: True if message was sent successfully, False otherwise
        """
        if not SlackService.is_configured():
            rprint(
                "[bold yellow]⚠️ Slack not configured. Set SLACK_BOT_TOKEN or SLACK_WEBHOOK_URL[/bold yellow]"
            )
            return False

        if not channel:
            channel = os.getenv("SLACK_DEFAULT_CHANNEL", "#general")

        if tag_be_developers:
            message = f"{' '.join(f'<@{u}>' for u in SLACK_BE_DEVELOPERS)} {message}"
        elif tag_fe_developers:
            message = f"{' '.join(f'<@{u}>' for u in SLACK_FE_DEVELOPERS)} {message}"

        # Use webhook if available, otherwise use API
        if SLACK_WEBHOOK_URL:
            return SlackService._send_via_webhook(
                channel, message, username, icon_emoji, attachments
            )
        elif SLACK_TOKEN:
            return SlackService._send_via_api(
                channel, message, username, icon_emoji, attachments
            )
        else:
            rprint("[bold red]❌ No Slack configuration found[/bold red]")
            return False

    @staticmethod
    def _send_via_webhook(
        channel: str,
        message: str,
        username: Optional[str] = None,
        icon_emoji: Optional[str] = None,
        attachments: Optional[list] = None,
    ) -> bool:
        """Send message via Slack webhook"""
        payload = {
            "channel": channel,
            "text": message,
        }

        if username:
            payload["username"] = username
        if icon_emoji:
            payload["icon_emoji"] = icon_emoji
        if attachments:
            payload["attachments"] = attachments

        try:
            response = requests.post(SLACK_WEBHOOK_URL, json=payload)
            if response.status_code == 200:
                rprint(f"[bold green]✅ Slack message sent to {channel}[/bold green]")
                return True
            else:
                rprint(
                    f"[bold red]❌ Failed to send Slack message: {response.status_code}[/bold red]"
                )
                return False
        except Exception as e:
            rprint(f"[bold red]❌ Error sending Slack message: {str(e)}[/bold red]")
            return False

    @staticmethod
    def _send_via_api(
        channel: str,
        message: str,
        username: Optional[str] = None,
        icon_emoji: Optional[str] = None,
        attachments: Optional[list] = None,
    ) -> bool:
        """Send message via Slack API"""
        headers = {
            "Authorization": f"Bearer {SLACK_TOKEN}",
            "Content-Type": "application/json",
        }

        payload = {
            "channel": channel,
            "text": message,
        }

        if attachments:
            payload["attachments"] = attachments

        try:
            response = requests.post(
                f"{SLACK_API_URL}/chat.postMessage",
                headers=headers,
                json=payload,
            )

            if response.status_code == 200:
                data = response.json()
                if data.get("ok"):
                    rprint(
                        f"[bold green]✅ Slack message sent to {channel}[/bold green]"
                    )
                    return True
                else:
                    error = data.get("error", "Unknown error")
                    rprint(f"[bold red]❌ Slack API error: {error}[/bold red]")
                    return False
            else:
                rprint(
                    f"[bold red]❌ Failed to send Slack message: {response.status_code}[/bold red]"
                )
                return False
        except Exception as e:
            rprint(f"[bold red]❌ Error sending Slack message: {str(e)}[/bold red]")
            return False
