import os
import base64
import requests
from rich import print as rprint
from rich.table import Table
from rich.console import Console
from datetime import datetime

# Jira API configuration
JIRA_TOKEN = os.getenv("JIRA_TOKEN")
JIRA_USER = os.getenv("JIRA_USER")
JIRA_URL = os.getenv("JIRA_URL", "https://your-domain.atlassian.net")
JIRA_DEFAULT_PROJECT = os.getenv("JIRA_DEFAULT_PROJECT")

console = Console()


class JiraService:
    """Service for interacting with Jira API"""

    @staticmethod
    def _get_headers():
        """Get the authorization headers for Jira API"""
        if not JIRA_TOKEN or not JIRA_USER:
            return None

        auth_str = f"{JIRA_USER}:{JIRA_TOKEN}"
        auth_bytes = auth_str.encode("ascii")
        auth_b64 = base64.b64encode(auth_bytes).decode("ascii")

        return {
            "Authorization": f"Basic {auth_b64}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    @staticmethod
    def _get_url(path: str) -> str:
        """Get the Jira API URL"""
        if path.startswith("/"):
            path = path[1:]
        return f"{JIRA_URL}/rest/api/3/{path}"

    @staticmethod
    def search_issues(
        query: str, project_key: str = None, max_results: int = 20
    ) -> bool:
        """
        Search for issues in Jira and display totals for story points

        Args:
            query: Search query
            project_key: Limit search to specific project
            max_results: Maximum number of results to return

        Returns:
            bool: True if search was successful, False otherwise
        """
        headers = JiraService._get_headers()
        if not headers:
            rprint(
                "[bold red]❌ JIRA_TOKEN and JIRA_USER must be set in your environment.[/bold red]"
            )
            return False

        # Build JQL query
        jql = query

        # Add project filter if specified
        if project_key:
            if "project" not in jql.lower():
                if jql:
                    jql = f"project = {project_key} {jql}"
                else:
                    jql = f"project = {project_key}"

        # Set up search parameters - add story points field
        params = {
            "jql": jql,
            "maxResults": max_results,
            "fields": "key,summary,status,assignee,priority,created,updated,issuetype,customfield_10035",  # customfield_10016 is typically the story points field
        }

        search_url = JiraService._get_url("search")

        try:
            response = requests.get(search_url, headers=headers, params=params)

            if response.status_code == 200:
                data = response.json()
                issues = data.get("issues", [])
                total = data.get("total", 0)

                if not issues:
                    rprint(f"[yellow]No issues found matching query: {jql}[/yellow]")
                    return True

                # Count story points
                total_story_points = 0
                issues_with_points = 0

                for issue in issues:
                    fields = issue.get("fields", {})
                    story_points = fields.get("customfield_10035")

                    if story_points is not None and isinstance(
                        story_points, (int, float)
                    ):
                        total_story_points += story_points
                        issues_with_points += 1

                # Display totals
                rprint(f"[bold blue]📊 Issue Statistics:[/bold blue]")
                rprint(
                    f"  • [green]Total Issues:[/green] {total} (showing {len(issues)})"
                )
                rprint(
                    f"  • [green]Total Story Points:[/green] {total_story_points:.1f}"
                )
                rprint(
                    f"  • [green]Issues Estimated:[/green] {issues_with_points} of {len(issues)} ({issues_with_points/len(issues)*100:.1f}% if shown)"
                )

                if total > len(issues):
                    rprint(
                        f"  • [yellow]Note:[/yellow] Only showing {len(issues)} of {total} total issues"
                    )

                # Display issues in a table
                table = Table(title=f"Jira Issues ({len(issues)} of {total})")
                table.add_column("Key", style="cyan")
                table.add_column("Points", style="magenta", justify="right")
                table.add_column("Type", style="blue")
                table.add_column("Summary", style="green")
                table.add_column("Status", style="yellow")
                table.add_column("Assignee")
                table.add_column("Updated", style="dim")

                for issue in issues:
                    key = issue.get("key", "")
                    fields = issue.get("fields", {})

                    # Extract field values with proper null handling
                    summary = fields.get("summary", "No summary")
                    status = fields.get("status", {}).get("name", "Unknown")

                    # Story points
                    story_points = fields.get("customfield_10035")
                    points_display = (
                        str(int(story_points))
                        if isinstance(story_points, (int, float))
                        else "-"
                    )

                    assignee = "Unassigned"
                    if fields.get("assignee"):
                        assignee = fields.get("assignee", {}).get(
                            "displayName", "Unassigned"
                        )

                    issue_type = "Issue"
                    if fields.get("issuetype"):
                        issue_type = fields.get("issuetype", {}).get("name", "Issue")

                    updated = "Unknown"
                    if fields.get("updated"):
                        updated_str = fields.get("updated")
                        updated = datetime.fromisoformat(
                            updated_str.replace("Z", "+00:00")
                        ).strftime("%Y-%m-%d")

                    table.add_row(
                        key,
                        points_display,
                        issue_type,
                        summary,
                        status,
                        assignee,
                        updated,
                    )

                console.print(table)
                return True
            else:
                rprint(
                    f"[bold red]❌ Failed to search issues: {response.status_code}[/bold red]"
                )
                error_message = response.text
                try:
                    error_data = response.json()
                    if "errorMessages" in error_data:
                        error_message = ", ".join(error_data["errorMessages"])
                    elif "message" in error_data:
                        error_message = error_data["message"]
                except:
                    pass
                rprint(f"[red]Error: {error_message}[/red]")
                return False

        except Exception as e:
            rprint(f"[bold red]❌ Error connecting to Jira: {str(e)}[/bold red]")
            return False

    @staticmethod
    def get_projects(max_results: int = 50) -> list:
        """
        Get list of available Jira projects

        Args:
            max_results: Maximum number of projects to return

        Returns:
            list: List of project dictionaries or empty list on failure
        """
        headers = JiraService._get_headers()
        if not headers:
            rprint(
                "[bold red]❌ JIRA_TOKEN and JIRA_USER must be set in your environment.[/bold red]"
            )
            return []

        projects_url = JiraService._get_url("project/search")
        params = {"maxResults": max_results}

        try:
            response = requests.get(projects_url, headers=headers, params=params)

            if response.status_code == 200:
                data = response.json()
                return data.get("values", [])
            else:
                rprint(
                    f"[bold red]❌ Failed to get projects: {response.status_code}[/bold red]"
                )
                return []

        except Exception as e:
            rprint(f"[bold red]❌ Error connecting to Jira: {str(e)}[/bold red]")
            return []

    @staticmethod
    def list_projects() -> bool:
        """
        List all available Jira projects

        Returns:
            bool: True if successful, False otherwise
        """
        projects = JiraService.get_projects()

        if not projects:
            return False

        table = Table(title=f"Jira Projects ({len(projects)})")
        table.add_column("Key", style="cyan")
        table.add_column("Name", style="green")
        table.add_column("Type", style="blue")
        table.add_column("Lead", style="yellow")

        for project in projects:
            key = project.get("key", "")
            name = project.get("name", "")
            project_type = project.get("projectTypeKey", "")

            lead = "Unknown"
            if project.get("lead"):
                lead = project.get("lead", {}).get("displayName", "Unknown")

            table.add_row(key, name, project_type, lead)

        console.print(table)
        return True

    @staticmethod
    def get_issue(issue_key: str) -> bool:
        """
        Get detailed information about a specific Jira issue

        Args:
            issue_key: The Jira issue key (e.g., PROJECT-123)

        Returns:
            bool: True if successful, False otherwise
        """
        headers = JiraService._get_headers()
        if not headers:
            rprint(
                "[bold red]❌ JIRA_TOKEN and JIRA_USER must be set in your environment.[/bold red]"
            )
            return False

        issue_url = JiraService._get_url(f"issue/{issue_key}")
        params = {
            "fields": "summary,description,status,assignee,priority,created,updated,issuetype,comment,reporter"
        }

        try:
            response = requests.get(issue_url, headers=headers, params=params)

            if response.status_code == 200:
                issue = response.json()
                fields = issue.get("fields", {})

                # Display issue details
                rprint(f"[bold blue]🎫 Issue [cyan]{issue_key}[/cyan][/bold blue]")
                rprint(f"[bold]{fields.get('summary', 'No summary')}[/bold]\n")

                # Create a table for issue metadata
                table = Table(show_header=False, box=None)
                table.add_column("Field", style="dim")
                table.add_column("Value", style="green")

                # Type and Status
                issue_type = fields.get("issuetype", {}).get("name", "Unknown")
                status = fields.get("status", {}).get("name", "Unknown")
                table.add_row("Type", issue_type)
                table.add_row("Status", status)

                # Assignee and Reporter
                assignee = "Unassigned"
                if fields.get("assignee"):
                    assignee = fields.get("assignee", {}).get(
                        "displayName", "Unassigned"
                    )

                reporter = "Unknown"
                if fields.get("reporter"):
                    reporter = fields.get("reporter", {}).get("displayName", "Unknown")

                table.add_row("Assignee", assignee)
                table.add_row("Reporter", reporter)

                # Priority
                priority = "None"
                if fields.get("priority"):
                    priority = fields.get("priority", {}).get("name", "None")
                table.add_row("Priority", priority)

                # Dates
                created = "Unknown"
                if fields.get("created"):
                    created_str = fields.get("created")
                    created = datetime.fromisoformat(
                        created_str.replace("Z", "+00:00")
                    ).strftime("%Y-%m-%d %H:%M")

                updated = "Unknown"
                if fields.get("updated"):
                    updated_str = fields.get("updated")
                    updated = datetime.fromisoformat(
                        updated_str.replace("Z", "+00:00")
                    ).strftime("%Y-%m-%d %H:%M")

                table.add_row("Created", created)
                table.add_row("Updated", updated)

                console.print(table)

                # Description
                if fields.get("description"):
                    rprint("\n[bold]Description:[/bold]")
                    # For simplicity, we're just showing raw content
                    # A more advanced version would parse Jira's Atlassian Document Format
                    description = fields.get("description", {})
                    if isinstance(description, dict) and "content" in description:
                        # Try to extract text from Atlassian Document Format
                        text = []
                        for content in description.get("content", []):
                            if content.get("type") == "paragraph":
                                for paragraph_content in content.get("content", []):
                                    if paragraph_content.get("type") == "text":
                                        text.append(paragraph_content.get("text", ""))
                        if text:
                            rprint("\n".join(text))
                    else:
                        rprint(str(description))

                # Comments
                comments = fields.get("comment", {}).get("comments", [])
                if comments:
                    rprint("\n[bold]Comments:[/bold]")
                    for i, comment in enumerate(
                        comments[:5], 1
                    ):  # Show up to 5 comments
                        author = comment.get("author", {}).get("displayName", "Unknown")
                        created = datetime.fromisoformat(
                            comment.get("created", "").replace("Z", "+00:00")
                        ).strftime("%Y-%m-%d %H:%M")

                        rprint(f"[dim]{i}. By {author} on {created}:[/dim]")

                        # Extract text from comment body
                        body = comment.get("body", {})
                        if isinstance(body, dict) and "content" in body:
                            text = []
                            for content in body.get("content", []):
                                if content.get("type") == "paragraph":
                                    for paragraph_content in content.get("content", []):
                                        if paragraph_content.get("type") == "text":
                                            text.append(
                                                paragraph_content.get("text", "")
                                            )
                            if text:
                                rprint("   " + "\n   ".join(text))
                        else:
                            rprint(f"   {str(body)}")

                        rprint("")  # Empty line between comments

                # Display a link to the issue
                rprint(f"\n[dim]View in browser: {JIRA_URL}/browse/{issue_key}[/dim]")

                return True
            else:
                rprint(
                    f"[bold red]❌ Failed to get issue: {response.status_code}[/bold red]"
                )
                error_message = response.text
                try:
                    error_data = response.json()
                    if "errorMessages" in error_data:
                        error_message = ", ".join(error_data["errorMessages"])
                    elif "message" in error_data:
                        error_message = error_data["message"]
                except:
                    pass
                rprint(f"[red]Error: {error_message}[/red]")
                return False

        except Exception as e:
            rprint(f"[bold red]❌ Error connecting to Jira: {str(e)}[/bold red]")
            return False

    @staticmethod
    def sprint_report(query: str, project_key: str = None) -> bool:
        """
        Generate a sprint report with story point totals based on JQL query

        Args:
            query: JQL query to filter issues
            project_key: Limit to specific project

        Returns:
            bool: True if successful, False otherwise
        """
        headers = JiraService._get_headers()
        if not headers:
            rprint(
                "[bold red]❌ JIRA_TOKEN and JIRA_USER must be set in your environment.[/bold red]"
            )
            return False

        # Build JQL query
        jql = query

        # Add project filter if specified
        if project_key:
            if "project" not in jql.lower():
                if jql:
                    jql = f"project = {project_key} {jql}"
                else:
                    jql = f"project = {project_key}"

        # Set up search parameters - we need ALL matching issues for accurate counts
        params = {
            "jql": jql,
            "maxResults": 500,  # Increased to get more complete data
            "fields": "issuetype,customfield_10035,status",  # Minimal fields
        }

        search_url = JiraService._get_url("search")

        try:
            response = requests.get(search_url, headers=headers, params=params)

            if response.status_code == 200:
                data = response.json()
                issues = data.get("issues", [])
                total = data.get("total", 0)

                if not issues:
                    rprint(f"[yellow]No issues found matching query: {jql}[/yellow]")
                    return True

                # Process counts by issue type and status
                issue_types = {}
                statuses = {}
                total_story_points = 0
                issues_with_points = 0

                for issue in issues:
                    fields = issue.get("fields", {})

                    # Story points
                    story_points = fields.get("customfield_10035")
                    if story_points is not None and isinstance(
                        story_points, (int, float)
                    ):
                        total_story_points += story_points
                        issues_with_points += 1

                    # Count by issue type
                    issue_type = fields.get("issuetype", {}).get("name", "Unknown")
                    if issue_type not in issue_types:
                        issue_types[issue_type] = {"count": 0, "points": 0}

                    issue_types[issue_type]["count"] += 1
                    if story_points is not None and isinstance(
                        story_points, (int, float)
                    ):
                        issue_types[issue_type]["points"] += story_points

                    # Count by status
                    status = fields.get("status", {}).get("name", "Unknown")
                    if status not in statuses:
                        statuses[status] = {"count": 0, "points": 0}

                    statuses[status]["count"] += 1
                    if story_points is not None and isinstance(
                        story_points, (int, float)
                    ):
                        statuses[status]["points"] += story_points

                # Sort by most common issue types
                sorted_issue_types = sorted(
                    issue_types.items(), key=lambda x: x[1]["count"], reverse=True
                )

                # Sort statuses by workflow order (approximated)
                status_order = [
                    "backlog",
                    "to do",
                    "open",
                    "in progress",
                    "review",
                    "testing",
                    "done",
                    "closed",
                    "deployed",
                    "resolved",
                ]

                def status_sort_key(status_item):
                    status_name = status_item[0].lower()
                    for i, ordered_status in enumerate(status_order):
                        if ordered_status in status_name:
                            return i
                    return 999  # Unknown statuses at the end

                sorted_statuses = sorted(statuses.items(), key=status_sort_key)

                # Display summary
                rprint(
                    f"\n[bold blue]🎯 Sprint Report: [cyan]{len(issues)} issues[/cyan][/bold blue]"
                )
                if total > len(issues):
                    rprint(
                        f"[yellow]Warning: Only analyzing {len(issues)} of {total} matching issues[/yellow]"
                    )

                rprint(f"\n[bold]📊 Overview[/bold]")
                rprint(f"  • [green]Total Issues:[/green] {len(issues)}")
                rprint(
                    f"  • [green]Total Story Points:[/green] {total_story_points:.1f}"
                )
                rprint(
                    f"  • [green]Average Points/Issue:[/green] {total_story_points/len(issues):.2f}"
                )
                rprint(
                    f"  • [green]Issues Estimated:[/green] {issues_with_points} ({issues_with_points/len(issues)*100:.1f}%)"
                )

                # By Issue Type table
                issue_type_table = Table(title="By Issue Type")
                issue_type_table.add_column("Type", style="cyan")
                issue_type_table.add_column("Count", justify="right", style="green")
                issue_type_table.add_column("Points", justify="right", style="magenta")
                issue_type_table.add_column("Avg", justify="right", style="blue")
                issue_type_table.add_column("% of Total", justify="right")

                for issue_type, data in sorted_issue_types:
                    count = data["count"]
                    points = data["points"]
                    avg = points / count if count > 0 else 0
                    percent = count / len(issues) * 100

                    issue_type_table.add_row(
                        issue_type,
                        str(count),
                        f"{points:.1f}",
                        f"{avg:.1f}",
                        f"{percent:.1f}%",
                    )

                console.print(issue_type_table)

                # By Status table
                status_table = Table(title="By Status")
                status_table.add_column("Status", style="yellow")
                status_table.add_column("Count", justify="right", style="green")
                status_table.add_column("Points", justify="right", style="magenta")
                status_table.add_column("% of Total", justify="right")

                for status, data in sorted_statuses:
                    count = data["count"]
                    points = data["points"]
                    percent = count / len(issues) * 100

                    status_table.add_row(
                        status, str(count), f"{points:.1f}", f"{percent:.1f}%"
                    )

                console.print(status_table)

                # Add query info at the end
                if project_key:
                    rprint(f"\n[dim]Query: {jql}[/dim]")
                    rprint(f"[dim]Project: {project_key}[/dim]")
                else:
                    rprint(f"\n[dim]Query: {jql}[/dim]")

                return True
            else:
                rprint(
                    f"[bold red]❌ Failed to search issues: {response.status_code}[/bold red]"
                )
                error_message = response.text
                try:
                    error_data = response.json()
                    if "errorMessages" in error_data:
                        error_message = ", ".join(error_data["errorMessages"])
                    elif "message" in error_data:
                        error_message = error_data["message"]
                except:
                    pass
                rprint(f"[red]Error: {error_message}[/red]")
                return False

        except Exception as e:
            rprint(f"[bold red]❌ Error connecting to Jira: {str(e)}[/bold red]")
            return False
