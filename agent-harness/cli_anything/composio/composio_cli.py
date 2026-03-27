"""
composio_cli.py - Click CLI entry point for cli-anything-composio

Command groups:
  tools       - List and manage Composio tools
  actions     - List and execute actions
  agents      - Manage agent configurations
  auth        - Login/logout management
  project     - Project initialization

All commands support --json for machine-readable output.

Follows HARNESS.md principles:
  - Real Composio CLI calls
  - Structured JSON output
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

import click

from .utils import composio_backend as cb

__all__ = ["main"]

JSON_MODE = False


# -------------------------------------------------------------------
# Utility helpers
# -------------------------------------------------------------------

def echo(msg: str, **kwargs) -> None:
    click.echo(msg, err=True, **kwargs)


def success(msg: str) -> None:
    click.echo(f"[OK] {msg}", err=True)


def error(msg: str) -> None:
    click.echo(f"[ERROR] {msg}", err=True, color="red")


def warn(msg: str) -> None:
    click.echo(f"[WARN] {msg}", err=True, color="yellow")


def json_out(data: dict) -> None:
    click.echo(json.dumps(data, indent=2))


# -------------------------------------------------------------------
# Main group
# -------------------------------------------------------------------

@click.group(invoke_without_command=True)
@click.option("--json", "json_output", is_flag=True, help="JSON output mode")
@click.option("--project", "-p", type=click.Path(), help="Composio project path")
@click.pass_context
def cli(ctx, json_output: bool, project: Optional[str]):
    """Composio agent tool management CLI — manage tools, actions, and integrations.

    Composio provides a unified interface for 100+ tool integrations
    that AI agents can use to perform tasks.

    Examples:
      composio tools list
      composio tools list --category code
      composio actions list --tool github
      composio execute github_create_issue --title "Bug" --body "Description"
    """
    global JSON_MODE
    JSON_MODE = json_output
    ctx.ensure_object(dict)
    ctx.obj["json"] = json_output
    ctx.obj["project"] = project


# ==================================================================
# tools command
# ==================================================================

@cli.group("tools")
def cmd_tools():
    """List and manage Composio tools."""
    pass


@cmd_tools.command("list")
@click.option("--category", "-c", help="Filter by category (browser, code, communication, etc.)")
@click.pass_context
def cmd_tools_list(ctx, category: Optional[str]):
    """List available Composio tools."""
    global JSON_MODE
    project = ctx.obj.get("project")

    result = cb.list_tools(category=category)

    if JSON_MODE:
        json_out(result)
    else:
        if result.get("success"):
            tools = result.get("tools", [])
            success(f"Found {len(tools)} tools")
            echo("")

            if category:
                echo(f"Category: {category}")
                echo("")

            for tool in tools:
                echo(f"  {tool.get('name', 'unknown'):<20} [{tool.get('category', '')}]")
                desc = tool.get("description", "")
                if desc:
                    echo(f"    {desc}")
                actions = tool.get("actions", 0)
                if actions:
                    echo(f"    {actions} actions")

            echo("")
            echo(f"Total: {len(tools)} tools")
        else:
            error(f"Failed to list tools")


@cmd_tools.command("add")
@click.argument("tool_name")
@click.pass_context
def cmd_tools_add(ctx, tool_name: str):
    """Add a Composio tool to the project."""
    global JSON_MODE
    project = ctx.obj.get("project")

    result = cb.add_tool(tool_name, project_path=project)

    if JSON_MODE:
        json_out({"success": result.success, "tool": tool_name, "output": result.output})
    else:
        if result.success:
            success(f"Added tool: {tool_name}")
        else:
            error(f"Failed to add tool: {tool_name}")
            if result.error:
                echo(f"  {result.error[:200]}")


@cmd_tools.command("remove")
@click.argument("tool_name")
@click.pass_context
def cmd_tools_remove(ctx, tool_name: str):
    """Remove a Composio tool from the project."""
    global JSON_MODE
    project = ctx.obj.get("project")

    result = cb.remove_tool(tool_name, project_path=project)

    if JSON_MODE:
        json_out({"success": result.success, "tool": tool_name, "output": result.output})
    else:
        if result.success:
            success(f"Removed tool: {tool_name}")
        else:
            error(f"Failed to remove tool: {tool_name}")


@cmd_tools.command("info")
@click.argument("tool_name")
def cmd_tools_info(tool_name: str):
    """Show detailed information about a tool."""
    global JSON_MODE

    result = cb.get_tool(tool_name)

    if JSON_MODE:
        json_out(result)
    else:
        if result.get("success"):
            echo(f"Tool: {result.get('name', tool_name)}")
            echo(f"  Category: {result.get('category', 'unknown')}")
            echo(f"  Description: {result.get('description', '')}")
            actions = result.get("actions", [])
            if actions:
                echo(f"  Actions:")
                for action in actions[:10]:
                    echo(f"    - {action}")
                if len(actions) > 10:
                    echo(f"    ... and {len(actions) - 10} more")
        else:
            error(f"Tool not found: {tool_name}")


# ==================================================================
# actions command
# ==================================================================

@cli.group("actions")
def cmd_actions():
    """List and execute Composio actions."""
    pass


@cmd_actions.command("list")
@click.option("--tool", "-t", help="Filter by tool name")
@click.option("--category", "-c", help="Filter by category")
@click.pass_context
def cmd_actions_list(ctx, tool: Optional[str], category: Optional[str]):
    """List available Composio actions."""
    global JSON_MODE

    result = cb.list_actions(tool=tool, category=category)

    if JSON_MODE:
        json_out(result)
    else:
        if result.get("success"):
            actions = result.get("actions", [])
            success(f"Found {len(actions)} actions")
            echo("")

            for action in actions:
                name = action.get("name", "unknown")
                tool_name = action.get("tool", "")
                desc = action.get("description", "")
                echo(f"  {name}")
                if tool_name:
                    echo(f"    Tool: {tool_name}")
                if desc:
                    echo(f"    {desc}")

            echo("")
            echo(f"Total: {len(actions)} actions")
        else:
            error(f"Failed to list actions")


@cmd_actions.command("execute")
@click.argument("action_name")
@click.option("--param", "-p", multiple=True, help="Action parameters as key=value")
@click.pass_context
def cmd_actions_execute(ctx, action_name: str, param: tuple):
    """Execute a Composio action."""
    global JSON_MODE
    project = ctx.obj.get("project")

    # Parse parameters
    params = {}
    for p in param:
        if "=" in p:
            key, value = p.split("=", 1)
            params[key] = value

    result = cb.execute_action(action_name, params=params, project_path=project)

    if JSON_MODE:
        json_out(result)
    else:
        if result.get("success"):
            success(f"Executed: {action_name}")
            res_data = result.get("result", {})
            if isinstance(res_data, dict):
                for key, value in res_data.items():
                    echo(f"  {key}: {value}")
            else:
                echo(f"  {result.get('result', '')}")
        else:
            error(f"Execution failed: {result.get('error', 'unknown')}")


# ==================================================================
# agents command
# ==================================================================

@cli.group("agents")
def cmd_agents():
    """Manage agent configurations."""
    pass


@cmd_agents.command("list")
@click.pass_context
def cmd_agents_list(ctx):
    """List configured agents."""
    global JSON_MODE
    project = ctx.obj.get("project")

    result = cb.list_agents(project_path=project)

    if JSON_MODE:
        json_out(result)
    else:
        if result.get("success"):
            agents = result.get("agents", [])
            success(f"Found {len(agents)} agents")
            echo("")

            for agent in agents:
                name = agent.get("name", "unknown")
                status = agent.get("status", "unknown")
                tools = agent.get("tools", [])
                echo(f"  {name} [{status}]")
                if tools:
                    echo(f"    Tools: {', '.join(tools)}")
        else:
            error(f"Failed to list agents")


# ==================================================================
# auth command
# ==================================================================

@cli.group("auth")
def cmd_auth():
    """Authentication management."""
    pass


@cmd_auth.command("login")
@click.option("--api-key", help="Composio API key")
def cmd_auth_login(api_key: Optional[str]):
    """Login to Composio."""
    global JSON_MODE

    result = cb.login(api_key=api_key)

    if JSON_MODE:
        json_out({"success": result.success, "output": result.output})
    else:
        if result.success:
            success("Logged in to Composio")
        else:
            error("Login failed")
            if result.error:
                echo(f"  {result.error[:200]}")


@cmd_auth.command("logout")
def cmd_auth_logout():
    """Logout from Composio."""
    global JSON_MODE

    result = cb.logout()

    if JSON_MODE:
        json_out({"success": result.success, "output": result.output})
    else:
        if result.success:
            success("Logged out from Composio")
        else:
            error("Logout failed")


@cmd_auth.command("whoami")
def cmd_auth_whoami():
    """Show current Composio user info."""
    global JSON_MODE

    result = cb.whoami()

    if JSON_MODE:
        json_out(result)
    else:
        if result.get("success"):
            user = result.get("user", {})
            echo(f"User: {user.get('email', 'unknown')}")
            echo(f"  ID: {user.get('id', 'unknown')}")
            echo(f"  Plan: {user.get('plan', 'unknown')}")
            echo(f"  Workspace: {user.get('workspace', 'unknown')}")
        else:
            error("Not logged in")


# ==================================================================
# project command
# ==================================================================

@cli.command("init")
@click.option("--path", "-p", type=click.Path(), default=".", help="Project path")
def cmd_init(path: str):
    """Initialize a new Composio project."""
    global JSON_MODE

    result = cb.init_project(path)

    if JSON_MODE:
        json_out({"success": result.success, "path": path, "output": result.output})
    else:
        if result.success:
            success(f"Initialized Composio project at: {path}")
        else:
            error("Failed to initialize project")


# ==================================================================
# Entry point
# ==================================================================

def main():
    cli(obj={})


if __name__ == "__main__":
    main()
