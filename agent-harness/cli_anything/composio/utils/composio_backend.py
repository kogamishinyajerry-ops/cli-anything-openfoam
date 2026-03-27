"""
composio_backend.py - Composio CLI wrapper

Wraps Composio CLI for use by the cli-anything harness.

Composio is installed via:
  pip install composio-core

Principles:
  - Calls real Composio CLI commands
  - Tool for managing agent tool integrations
  - Outputs structured JSON
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional


# -------------------------------------------------------------------
# Version
# -------------------------------------------------------------------

COMPOSIO_VERSION = "1.0.0"


# -------------------------------------------------------------------
# Installation detection
# -------------------------------------------------------------------

def find_composio() -> Path:
    """
    Locate Composio CLI.

    Returns Path to composio binary.
    Raises RuntimeError if not found.
    """
    if os.environ.get("COMPOSIO_MOCK"):
        return Path("/usr/bin/true")

    candidates = ["composio", "composio-core"]

    for name in candidates:
        try:
            result = subprocess.run(
                [name, "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                return Path(name)
        except Exception:
            pass

    # Try python module
    try:
        result = subprocess.run(
            ["python", "-c", "import composio; print(composio.__version__)"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return Path("composio")
    except Exception:
        pass

    raise RuntimeError(
        "Composio not found.\n"
        "Install with: pip install composio-core\n"
        "Or: pip install composio"
    )


# -------------------------------------------------------------------
# Result dataclass
# -------------------------------------------------------------------

@dataclass
class CommandResult:
    """Result of a Composio CLI command execution."""
    success: bool
    output: str = ""
    error: str = ""
    returncode: int = 0
    duration_seconds: float = 0.0


# -------------------------------------------------------------------
# Core runner
# -------------------------------------------------------------------

def _run(
    cmd: list[str],
    timeout: Optional[int] = None,
    check: bool = True,
    cwd: Optional[Path] = None,
) -> CommandResult:
    """
    Run Composio CLI command.

    Args:
        cmd: Command as list of strings
        timeout: Max seconds (None = no limit)
        check: Raise on non-zero exit
        cwd: Working directory

    Returns:
        CommandResult
    """
    start = time.time()
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
            cwd=cwd,
        )
        duration = time.time() - start

        if check and proc.returncode != 0:
            return CommandResult(
                success=False,
                output=proc.stdout,
                error=proc.stderr,
                returncode=proc.returncode,
                duration_seconds=duration,
            )

        return CommandResult(
            success=proc.returncode == 0,
            output=proc.stdout,
            error=proc.stderr,
            returncode=proc.returncode,
            duration_seconds=duration,
        )
    except subprocess.TimeoutExpired:
        return CommandResult(
            success=False,
            output="",
            error=f"Command timed out after {timeout}s",
            returncode=-1,
            duration_seconds=timeout or 0,
        )
    except Exception as e:
        return CommandResult(
            success=False,
            output="",
            error=str(e),
            returncode=-99,
            duration_seconds=time.time() - start,
        )


# -------------------------------------------------------------------
# Tool categories
# -------------------------------------------------------------------

TOOL_CATEGORIES = {
    "browser": {"description": "Browser automation tools", "examples": ["chrome", "firefox", "playwright"]},
    "code": {"description": "Code development tools", "examples": ["github", "gitlab", "jira", "linear"]},
    "communication": {"description": "Communication and collaboration", "examples": ["slack", "discord", "gmail", "outlook"]},
    "productivity": {"description": "Productivity tools", "examples": ["notion", "asana", "trello", "google_calendar"]},
    "database": {"description": "Database tools", "examples": ["postgresql", "mysql", "mongodb", "redis"]},
    "file": {"description": "File and storage tools", "examples": ["google_drive", "dropbox", "s3", "google_drive"]},
    "web": {"description": "Web scraping and APIs", "examples": ["requests", "serpapi", "rapidapi"]},
    "ml": {"description": "ML and AI tools", "examples": ["openai", "anthropic", "huggingface"]},
}


# -------------------------------------------------------------------
# Tool operations
# -------------------------------------------------------------------

def list_tools(
    category: Optional[str] = None,
    json_output: bool = True,
) -> dict:
    """
    List available Composio tools.

    Args:
        category: Filter by category
        json_output: Expect JSON output from CLI

    Returns:
        dict with tool list
    """
    if os.environ.get("COMPOSIO_MOCK"):
        return _mock_list_tools(category)

    cmd = ["composio", "tools", "list"]
    if json_output:
        cmd.append("--json")

    result = _run(cmd, timeout=30, check=False)

    if result.success and json_output:
        try:
            data = json.loads(result.output)
            if category:
                data = [t for t in data if t.get("category") == category]
            return {"success": True, "tools": data}
        except json.JSONDecodeError:
            pass

    # Fallback: parse from text
    tools = _parse_tools_from_text(result.output)
    if category:
        tools = [t for t in tools if t.get("category") == category]

    return {"success": result.success, "tools": tools, "raw": result.output}


def _mock_list_tools(category: Optional[str]) -> dict:
    """Mock list tools for testing."""
    mock_tools = [
        {"name": "github", "category": "code", "description": "GitHub API integration", "actions": 15},
        {"name": "slack", "category": "communication", "description": "Slack messaging API", "actions": 12},
        {"name": "chrome", "category": "browser", "description": "Chrome browser automation", "actions": 8},
        {"name": "notion", "category": "productivity", "description": "Notion workspace API", "actions": 20},
        {"name": "postgresql", "category": "database", "description": "PostgreSQL database", "actions": 6},
        {"name": "openai", "category": "ml", "description": "OpenAI API integration", "actions": 5},
        {"name": "jira", "category": "code", "description": "Jira issue tracking", "actions": 18},
        {"name": "gmail", "category": "communication", "description": "Gmail email API", "actions": 10},
        {"name": "google_drive", "category": "file", "description": "Google Drive API", "actions": 14},
        {"name": "serpapi", "category": "web", "description": "Search engine results API", "actions": 3},
    ]

    if category:
        mock_tools = [t for t in mock_tools if t.get("category") == category]

    return {"success": True, "tools": mock_tools}


def _parse_tools_from_text(text: str) -> list[dict]:
    """Parse tools from Composio CLI text output."""
    tools = []
    lines = text.split("\n")

    current_tool = None
    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Try to detect tool entries
        if re.match(r"^[a-z][a-z0-9_]*$", line) and len(line) < 30:
            if current_tool:
                tools.append(current_tool)
            current_tool = {"name": line, "description": "", "category": "", "actions": 0}
        elif current_tool and ":" in line:
            parts = line.split(":", 1)
            key = parts[0].strip().lower()
            val = parts[1].strip()
            if key in ["description", "category", "actions"]:
                current_tool[key] = val

    if current_tool:
        tools.append(current_tool)

    return tools


def add_tool(
    tool_name: str,
    project_path: Optional[str] = None,
) -> CommandResult:
    """
    Add a Composio tool to a project.

    Args:
        tool_name: Name of tool to add
        project_path: Path to Composio project

    Returns:
        CommandResult
    """
    if os.environ.get("COMPOSIO_MOCK"):
        return CommandResult(success=True, output=f"Added {tool_name}", returncode=0)

    cmd = ["composio", "add", tool_name]
    result = _run(cmd, timeout=60, check=False, cwd=Path(project_path) if project_path else None)
    return result


def remove_tool(
    tool_name: str,
    project_path: Optional[str] = None,
) -> CommandResult:
    """
    Remove a Composio tool from a project.

    Returns:
        CommandResult
    """
    if os.environ.get("COMPOSIO_MOCK"):
        return CommandResult(success=True, output=f"Removed {tool_name}", returncode=0)

    cmd = ["composio", "remove", tool_name]
    result = _run(cmd, timeout=30, check=False, cwd=Path(project_path) if project_path else None)
    return result


def get_tool(
    tool_name: str,
) -> dict:
    """
    Get details about a specific tool.

    Returns:
        dict with tool information
    """
    if os.environ.get("COMPOSIO_MOCK"):
        for cat, info in TOOL_CATEGORIES.items():
            if tool_name in info.get("examples", []):
                return {
                    "success": True,
                    "tool": tool_name,
                    "category": cat,
                    "description": info["description"],
                    "actions": [],
                }
        return {"success": False, "error": f"Unknown tool: {tool_name}"}

    cmd = ["composio", "tools", "get", tool_name, "--json"]
    result = _run(cmd, timeout=30, check=False)

    if result.success:
        try:
            return {"success": True, **json.loads(result.output)}
        except json.JSONDecodeError:
            pass

    return {"success": False, "error": result.error or f"Unknown tool: {tool_name}"}


# -------------------------------------------------------------------
# Action operations
# -------------------------------------------------------------------

def list_actions(
    tool: Optional[str] = None,
    category: Optional[str] = None,
) -> dict:
    """
    List available Composio actions.

    Args:
        tool: Filter by tool name
        category: Filter by category

    Returns:
        dict with action list
    """
    if os.environ.get("COMPOSIO_MOCK"):
        return _mock_list_actions(tool, category)

    cmd = ["composio", "actions", "list"]
    if tool:
        cmd.extend(["--tool", tool])
    if category:
        cmd.extend(["--category", category])
    cmd.append("--json")

    result = _run(cmd, timeout=30, check=False)

    if result.success:
        try:
            return {"success": True, "actions": json.loads(result.output)}
        except json.JSONDecodeError:
            pass

    return {"success": result.success, "actions": [], "raw": result.output}


def _mock_list_actions(tool: Optional[str], category: Optional[str]) -> dict:
    """Mock list actions for testing."""
    mock_actions = [
        {"name": "github_create_issue", "tool": "github", "description": "Create a GitHub issue"},
        {"name": "github_get_pull_request", "tool": "github", "description": "Get PR details"},
        {"name": "slack_send_message", "tool": "slack", "description": "Send Slack message"},
        {"name": "slack_channel_info", "tool": "slack", "description": "Get channel information"},
        {"name": "notion_create_page", "tool": "notion", "description": "Create Notion page"},
        {"name": "notion_search", "tool": "notion", "description": "Search Notion database"},
        {"name": "gmail_send_email", "tool": "gmail", "description": "Send email via Gmail"},
        {"name": "jira_create_issue", "tool": "jira", "description": "Create Jira issue"},
    ]

    if tool:
        mock_actions = [a for a in mock_actions if a.get("tool") == tool]
    if category:
        mock_actions = [a for a in mock_actions if a.get("category") == category]

    return {"success": True, "actions": mock_actions}


def execute_action(
    action_name: str,
    params: Optional[dict] = None,
    project_path: Optional[str] = None,
) -> dict:
    """
    Execute a Composio action.

    Args:
        action_name: Name of action to execute
        params: Action parameters
        project_path: Path to Composio project

    Returns:
        dict with execution result
    """
    if os.environ.get("COMPOSIO_MOCK"):
        return {
            "success": True,
            "action": action_name,
            "result": {"status": "success", "mock": True},
            "output": f"Executed {action_name} (mock)",
        }

    params = params or {}

    # Build command
    cmd = ["composio", "execute", action_name]
    for key, value in params.items():
        cmd.extend([f"--{key}", str(value)])

    result = _run(cmd, timeout=120, check=False, cwd=Path(project_path) if project_path else None)

    try:
        output = json.loads(result.output) if result.output else {}
    except json.JSONDecodeError:
        output = {"raw": result.output}

    return {
        "success": result.success,
        "action": action_name,
        "params": params,
        "result": output,
        "error": result.error if not result.success else "",
    }


# -------------------------------------------------------------------
# Agent operations
# -------------------------------------------------------------------

def list_agents(
    project_path: Optional[str] = None,
) -> dict:
    """
    List configured agents.

    Returns:
        dict with agent list
    """
    if os.environ.get("COMPOSIO_MOCK"):
        return {
            "success": True,
            "agents": [
                {"name": "default", "status": "active", "tools": ["github", "slack"]},
                {"name": "research", "status": "active", "tools": ["serpapi", "google_drive"]},
            ],
        }

    cmd = ["composio", "agents", "list", "--json"]
    result = _run(cmd, timeout=30, check=False, cwd=Path(project_path) if project_path else None)

    if result.success:
        try:
            return {"success": True, "agents": json.loads(result.output)}
        except json.JSONDecodeError:
            pass

    return {"success": result.success, "agents": [], "raw": result.output}


def init_project(
    project_path: str,
) -> CommandResult:
    """
    Initialize a new Composio project.

    Returns:
        CommandResult
    """
    if os.environ.get("COMPOSIO_MOCK"):
        return CommandResult(success=True, output=f"Initialized project at {project_path}", returncode=0)

    cmd = ["composio", "init", "--yes"]
    result = _run(cmd, timeout=30, check=False, cwd=Path(project_path))
    return result


# -------------------------------------------------------------------
# Auth operations
# -------------------------------------------------------------------

def login(
    api_key: Optional[str] = None,
) -> CommandResult:
    """
    Login to Composio.

    Args:
        api_key: Optional API key (if not set via env)

    Returns:
        CommandResult
    """
    if os.environ.get("COMPOSIO_MOCK"):
        return CommandResult(success=True, output="Logged in to Composio", returncode=0)

    if api_key:
        cmd = ["composio", "login", "--api-key", api_key]
    else:
        cmd = ["composio", "login"]

    result = _run(cmd, timeout=30, check=False)
    return result


def logout() -> CommandResult:
    """
    Logout from Composio.

    Returns:
        CommandResult
    """
    if os.environ.get("COMPOSIO_MOCK"):
        return CommandResult(success=True, output="Logged out from Composio", returncode=0)

    result = _run(["composio", "logout"], timeout=15, check=False)
    return result


def whoami() -> dict:
    """
    Get current Composio user info.

    Returns:
        dict with user information
    """
    if os.environ.get("COMPOSIO_MOCK"):
        return {
            "success": True,
            "user": {
                "id": "mock_user_123",
                "email": "user@example.com",
                "plan": "free",
                "workspace": "default",
            },
        }

    cmd = ["composio", "whoami", "--json"]
    result = _run(cmd, timeout=15, check=False)

    if result.success:
        try:
            return {"success": True, **json.loads(result.output)}
        except json.JSONDecodeError:
            pass

    return {"success": False, "error": result.error or "Not logged in"}
