"""
perforce_backend.py - Perforce Helix Core CLI wrapper

Perforce is an enterprise version control system optimized for large binary assets.

Key commands:
  - p4 client              Create/edit client workspace
  - p4 sync                Sync files from depot
  - p4 submit              Submit changes to depot
  - p4 add                 Add files to depot
  - p4 edit                Mark files for edit
  - p4 delete               Mark files for deletion
  - p4 files               List files in depot
  - p4 changes             List recent changes
  - p4 describe            Show change details
  - p4 integrate           Branch/merge files
  - p4 resolve             Resolve merge conflicts
  - p4 revert              Revert changes
  - p4 status              Show workspace status
  - p4 diff                Show diffs

Install:
  - Download from perforce.com (Helix Core)
  - Linux: sudo apt install helix-binaries
  - macOS: brew install perforce

Principles:
  - MUST call real p4 commands, not reimplement
  - Perforce requires a workspace (client) configured
  - Set P4PORT, P4USER, P4CLIENT environment variables
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


# -------------------------------------------------------------------
# Version
# -------------------------------------------------------------------

PERFORCE_VERSION = "1.0.0"


# -------------------------------------------------------------------
# Installation detection
# -------------------------------------------------------------------

P4_PATHS = [
    "/usr/bin/p4",
    "/usr/local/bin/p4",
    "/opt/perforce/bin/p4",
    Path.home() / "p4/bin/p4",
]


def find_p4() -> Path:
    """Locate p4 binary."""
    if os.environ.get("P4_MOCK"):
        return Path("/usr/bin/true")

    path = os.environ.get("P4_PATH")
    if path:
        p = Path(path)
        if p.exists():
            return p

    for candidate in P4_PATHS:
        p = Path(candidate)
        if p.exists():
            return p

    try:
        result = subprocess.run(["which", "p4"], capture_output=True, text=True, timeout=10)
        if result.returncode == 0 and result.stdout.strip():
            return Path(result.stdout.strip())
    except Exception:
        pass

    raise RuntimeError(
        "Perforce (p4) not found.\n"
        "Set P4_PATH env var or install Helix Core.\n"
        "Download: https://www.perforce.com/downloads/helix-core\n"
        "Set P4_MOCK=1 for testing."
    )


# -------------------------------------------------------------------
# Result dataclass
# -------------------------------------------------------------------

@dataclass
class CommandResult:
    """Result of a Perforce command execution."""
    success: bool
    output: str = ""
    error: str = ""
    returncode: int = 0
    duration_seconds: float = 0.0


# -------------------------------------------------------------------
# Core runner
# -------------------------------------------------------------------

def _run(args: list, timeout: int = 120, check: bool = True) -> CommandResult:
    """Run a p4 command."""
    p4 = find_p4()
    cmd = [str(p4)] + args

    start = time.time()
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
            env={**os.environ, "P4_MOCK": os.environ.get("P4_MOCK", "")},
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
            error="Command timed out after {}s".format(timeout),
            returncode=-1,
            duration_seconds=timeout,
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
# Version / Info
# -------------------------------------------------------------------

def get_version() -> dict:
    """Get Perforce version."""
    if os.environ.get("P4_MOCK"):
        return {"success": True, "version": "2023.2", "server": "Helix Core"}

    result = _run(["rev"], timeout=10, check=False)
    if result.success or "2023" in result.output or "2022" in result.output:
        match = re.search(r"Rev\. (\S+)", result.output)
        v = match.group(1) if match else "unknown"
        return {"success": True, "version": v}
    return {"success": False, "error": result.error}


def get_info() -> dict:
    """Get Perforce server/client info."""
    if os.environ.get("P4_MOCK"):
        return {
            "success": True,
            "server": "perforce:1666",
            "client": "my-workspace",
            "user": "testuser",
            "root": "/home/user/depot",
            "server_version": "2023.2",
        }

    result = _run(["info"], timeout=15, check=False)
    if result.success:
        info = {}
        for line in result.output.split("\n"):
            if ":" in line:
                key, val = line.split(":", 1)
                info[key.strip()] = val.strip()
        return {"success": True, **info}
    return {"success": False, "error": result.error}


# -------------------------------------------------------------------
# Workspace
# -------------------------------------------------------------------

def create_client(
    client_name: str,
    root_dir: str,
    host: Optional[str] = None,
    description: str = "Created by cli-anything-perforce",
) -> CommandResult:
    """
    Create a Perforce client workspace.

    Args:
        client_name: Client workspace name
        root_dir: Root directory path
        host: Perforce server host
        description: Description

    Returns:
        CommandResult
    """
    if os.environ.get("P4_MOCK"):
        return CommandResult(
            success=True,
            output="Client {} created.".format(client_name),
            returncode=0,
        )

    root = Path(root_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)

    spec = "Client: {name}\nRoot: {root}\nHost: {host}\nDescription:\n  {desc}\nOptions: noallwrite noclobber compress unlocked\nReview:\n\n".format(
        name=client_name,
        root=str(root),
        host=host or os.environ.get("P4HOST", ""),
        desc=description,
    )

    result = _run(["client", "-i"], timeout=30, check=False)
    return result


def sync(branch: str = "//depot/main", client_path: Optional[str] = None) -> CommandResult:
    """
    Sync files from depot.

    Args:
        branch: Depot path to sync
        client_path: Optional client path override

    Returns:
        CommandResult
    """
    if os.environ.get("P4_MOCK"):
        return CommandResult(
            success=True,
            output="Sync from {} complete\n"
                    "  //depot/main/file1.cpp#1 - added\n"
                    "  //depot/main/file2.h#1 - updated".format(branch),
            returncode=0,
        )

    target = client_path or branch
    result = _run(["sync", target], timeout=300, check=False)
    return result


# -------------------------------------------------------------------
# Files
# -------------------------------------------------------------------

def list_files(depot_path: str, max_results: int = 100) -> dict:
    """
    List files in a depot path.

    Args:
        depot_path: Depot path (e.g. '//depot/main/...')
        max_results: Maximum number of files to return

    Returns:
        dict with file list
    """
    if os.environ.get("P4_MOCK"):
        return {
            "success": True,
            "files": [
                {"depotFile": "//depot/main/file1.cpp", "rev": "1", "headType": "text"},
                {"depotFile": "//depot/main/file2.h", "rev": "2", "headType": "text"},
                {"depotFile": "//depot/main/assets/model.fbx", "rev": "1", "headType": "binary"},
            ],
        }

    result = _run(["files", depot_path], timeout=30, check=False)
    if not result.success:
        return {"success": False, "error": result.error}

    files = []
    for line in result.output.split("\n"):
        if not line.strip() or line.startswith("..."):
            continue
        parts = line.split()
        if len(parts) >= 3:
            files.append({
                "depotFile": parts[0],
                "rev": parts[1],
                "action": parts[2] if len(parts) > 2 else "",
            })

    return {"success": True, "files": files[:max_results]}


# -------------------------------------------------------------------
# Changes
# -------------------------------------------------------------------

def list_changes(depot_path: str = "...", max_changes: int = 10) -> dict:
    """
    List recent changes.

    Args:
        depot_path: Depot path to search
        max_changes: Maximum number of changes to return

    Returns:
        dict with change list
    """
    if os.environ.get("P4_MOCK"):
        return {
            "success": True,
            "changes": [
                {"change": "12345", "user": "alice", "time": "1700000000", "desc": "Add new feature module"},
                {"change": "12344", "user": "bob", "time": "1699990000", "desc": "Fix rendering bug"},
                {"change": "12343", "user": "charlie", "time": "1699980000", "desc": "Update assets"},
            ],
        }

    result = _run(["changes", "-l", "-m", str(max_changes), depot_path], timeout=30, check=False)
    if not result.success:
        return {"success": False, "error": result.error}

    changes = []
    for line in result.output.split("\n"):
        if line.startswith("Change"):
            m = re.match(r"Change (\d+) on (\S+) by (\S+)@(\S+) '(.+)'", line)
            if m:
                changes.append({
                    "change": m.group(1),
                    "date": m.group(2),
                    "user": m.group(3),
                    "client": m.group(4),
                    "desc": m.group(5),
                })

    return {"success": True, "changes": changes}


def describe_change(change_num: str) -> dict:
    """
    Describe a change (show files in change).

    Args:
        change_num: Change number

    Returns:
        dict with change details
    """
    if os.environ.get("P4_MOCK"):
        return {
            "success": True,
            "change": change_num,
            "user": "testuser",
            "desc": "Update module",
            "files": ["//depot/main/file1.cpp", "//depot/main/file2.h"],
        }

    result = _run(["describe", str(change_num)], timeout=30, check=False)
    if not result.success:
        return {"success": False, "error": result.error}

    data = {"success": True, "change": change_num, "files": []}
    in_files = False
    for line in result.output.split("\n"):
        if line.startswith("Affected files ..."):
            in_files = True
            continue
        if in_files and line.strip():
            if line.startswith("//"):
                data["files"].append(line.strip())
            elif not line.startswith("..."):
                in_files = False

    return data


# -------------------------------------------------------------------
# Submit
# -------------------------------------------------------------------

def submit(description: str, file_paths: Optional[list] = None) -> dict:
    """
    Submit changes to depot.

    Args:
        description: Change description
        file_paths: Specific files to submit (default: all opened files)

    Returns:
        dict with submit result
    """
    if os.environ.get("P4_MOCK"):
        return {
            "success": True,
            "change": "12346",
            "submitted": True,
            "desc": description,
        }

    if file_paths:
        result = _run(["submit", "-c", description] + file_paths, timeout=60, check=False)
    else:
        result = _run(["submit", "-c", description], timeout=60, check=False)

    if result.success:
        m = re.search(r"Change (\d+) created", result.output)
        change_num = m.group(1) if m else "unknown"
        return {"success": True, "change": change_num, "submitted": True}
    return {"success": False, "error": result.error or "Submit failed"}


# -------------------------------------------------------------------
# Workspace status
# -------------------------------------------------------------------

def status() -> dict:
    """
    Get workspace status (opened files, pending changes).

    Returns:
        dict with status info
    """
    if os.environ.get("P4_MOCK"):
        return {
            "success": True,
            "opened_files": ["//depot/main/file1.cpp", "//depot/main/file2.h"],
            "added_files": ["//depot/main/newfile.cpp"],
            "deleted_files": [],
            "untracked": ["./local_only.txt"],
        }

    result = _run(["fstat", "-F", "headAction=delete", "./..."], timeout=30, check=False)
    return {"success": True, "raw": result.output}
