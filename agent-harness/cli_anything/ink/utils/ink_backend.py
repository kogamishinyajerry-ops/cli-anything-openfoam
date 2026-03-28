"""
ink_backend.py - Ink Interactive Narrative CLI wrapper

Wraps real Ink (inklecate) commands for use by the cli-anything harness.

Ink/Inklecate is installed via:
  - GitHub: https://github.com/inkle/ink (compile from source)
  -itch.io: pre-built binaries
  - npm: npm install -g inktlecate (unofficial)

The official tool is "inklecate" - the compiler and runtime for ink scripts.

Principles:
  - MUST call real inklecate commands, not reimplement
  - Software is HARD dependency - error clearly if not found
  - Operations via inklecate CLI + ink script files
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

INK_VERSION = "1.0.0"


# -------------------------------------------------------------------
# Installation detection
# -------------------------------------------------------------------

# inklecate is the official compiler/runtime
INKLECAT_PATHS = [
    "/usr/local/bin/inklecate",
    "/usr/bin/inklecate",
    Path.home() / ".local/bin/inklecate",
    Path.home() / "ink/bin/inklecate",
]


def find_inklecate() -> Path:
    """
    Locate inklecate binary.

    Returns Path to inklecate executable.
    Raises RuntimeError if not found.
    """
    inklecate = os.environ.get("INKLECAT_PATH")

    if not inklecate:
        for candidate in INKLECAT_PATHS:
            p = Path(candidate)
            if p.exists():
                inklecate = str(p)
                break

    if not inklecate:
        try:
            result = subprocess.run(
                ["which", "inklecate"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0 and result.stdout.strip():
                inklecate = result.stdout.strip()
        except Exception:
            pass

    if not inklecate:
        if os.environ.get("INK_MOCK"):
            return Path("/usr/bin/true")
        raise RuntimeError(
            f"Inklecate not found.\n"
            f"Set INKLECAT_PATH env var or install Inklecate.\n"
            f"Download from: https://github.com/inkle/ink/releases\n"
            f"Or: npm install -g inktlecate"
        )

    bin_path = Path(inklecate)
    if not bin_path.exists():
        if os.environ.get("INK_MOCK"):
            return Path("/usr/bin/true")
        raise RuntimeError(f"Inklecate not found at {bin_path}")

    return bin_path


# -------------------------------------------------------------------
# Result dataclass
# -------------------------------------------------------------------

@dataclass
class CommandResult:
    """Result of an ink command execution."""
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
    cwd: Optional[Path] = None,
    timeout: Optional[int] = None,
    check: bool = True,
    input_text: Optional[str] = None,
) -> CommandResult:
    """
    Run inklecate command.

    Args:
        cmd: Command as list of strings
        cwd: Working directory
        timeout: Max seconds (None = no limit)
        check: Raise on non-zero exit
        input_text: Optional stdin input

    Returns:
        CommandResult
    """
    inklecate = find_inklecate()

    actual_cmd = [str(inklecate)] + cmd

    start = time.time()
    try:
        proc = subprocess.run(
            actual_cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
            input=input_text,
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
# Version / Info
# -------------------------------------------------------------------

def get_version() -> dict:
    """
    Get inklecate version information.

    Returns:
        dict with version info
    """
    if os.environ.get("INK_MOCK"):
        return {
            "success": True,
            "version": "1.2.0",
            "engine": "ink",
        }

    result = _run(["--version"], timeout=15, check=False)

    if result.success:
        version_str = result.output.strip()
        return {
            "success": True,
            "version": version_str,
            "engine": "ink",
        }

    # Try --help as fallback
    result2 = _run([], timeout=15, check=False)
    if result2.returncode in [0, 1]:  # inklecate returns 1 for no args
        return {
            "success": True,
            "version": "unknown (inklecate found)",
            "engine": "ink",
        }

    return {
        "success": False,
        "error": result.error or "Failed to get version",
    }


# -------------------------------------------------------------------
# Script templates
# -------------------------------------------------------------------

INK_TEMPLATES = {
    "hello": """\
// Hello World - basic ink script
Hello, world!
This is your first ink story.

== END ==
""",

    "choice": """\
// Choice demo - interactive narrative
What would you like to do?

* [Go left]
    You go left and find a forest.
    -> END
* [Go right]
    You go right and find a river.
    -> END
* [Stay]
    You stay put.
    -> END

== END ==
""",

    "branching": """\
// Branching story demo
VAR player_name = "Hero"

== START ==
{player_name} wakes up in a dark room.
Where are you? You look around.

* [Search the room]
    You find a key under the bed.
    ~ found_key = true
    -> EXAMINE_DOOR
* [Check the door]
    The door is locked.
    -> EXAMINE_DOOR

== EXAMINE_DOOR ==
You try the door. It's locked tight.

* [Use the key]
    {found_key: You unlock the door! | You need a key first.}
    -> END
* [Give up]
    You sit down and wait.
    -> END

== END ==
""",

    "variable": """\
// Variable demo
VAR health = 100
VAR gold = 0

You are an adventurer with {health} health and {gold} gold.

* [Search for treasure]
    You find 50 gold!
    ~ gold += 50
    Your gold is now {gold}.
* [Rest]
    You rest and recover 10 health.
    ~ health += 10
    Your health is now {health}.
* [Leave]
    You leave the tavern.
    -> END

-> END

== END ==
""",
}


def generate_script(
    script_type: str,
    output_path: Optional[str] = None,
) -> dict:
    """
    Generate an ink script template.

    Args:
        script_type: 'hello', 'choice', 'branching', 'variable'
        output_path: Optional path to write the script

    Returns:
        dict with script content
    """
    if script_type not in INK_TEMPLATES:
        return {
            "success": False,
            "error": f"Unknown script type: {script_type}",
        }

    content = INK_TEMPLATES[script_type]

    if output_path:
        path = Path(output_path).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    return {
        "success": True,
        "type": script_type,
        "path": str(output_path) if output_path else None,
        "content": content,
    }


def list_script_types() -> dict:
    """List available ink script template types."""
    return {
        "success": True,
        "types": list(INK_TEMPLATES.keys()),
    }


# -------------------------------------------------------------------
# Compile
# -------------------------------------------------------------------

def compile_ink(
    input_path: str,
    output_path: Optional[str] = None,
    all_stories: bool = False,
) -> CommandResult:
    """
    Compile an ink script to JSON.

    Args:
        input_path: Path to .ink file
        output_path: Optional output JSON path
        all_stories: Compile all named choice sections

    Returns:
        CommandResult
    """
    ink_path = Path(input_path).resolve()
    if not ink_path.exists():
        return CommandResult(
            success=False,
            error=f"Ink script not found: {ink_path}",
            returncode=1,
        )

    if os.environ.get("INK_MOCK"):
        mock_json = {
            "inkVersion": 1.2,
            "root": [["done", "done"]],
            "done": True,
            "count": 1,
        }
        out_path = Path(output_path).resolve() if output_path else ink_path.with_suffix(".json")
        out_path.write_text(json.dumps(mock_json))
        return CommandResult(
            success=True,
            output=f"Compiled to {out_path}",
            returncode=0,
        )

    cmd = []
    if all_stories:
        cmd.append("--all-stories")
    cmd.append(str(ink_path))

    if output_path:
        cmd.extend(["-o", str(Path(output_path).resolve())])

    result = _run(cmd, timeout=60, check=False)
    return result


# -------------------------------------------------------------------
# Stats
# -------------------------------------------------------------------

def get_stats(input_path: str) -> dict:
    """
    Get story statistics for an ink script.

    Args:
        input_path: Path to .ink file

    Returns:
        dict with story stats
    """
    ink_path = Path(input_path).resolve()
    if not ink_path.exists():
        return {"success": False, "error": f"Ink script not found: {ink_path}"}

    if os.environ.get("INK_MOCK"):
        return {
            "success": True,
            "path": str(ink_path),
            "stats": {
                "words": 150,
                "choices": 5,
                "knots": 3,
                "gather_points": 2,
            },
        }

    # inklecate -c prints stats
    result = _run(["-c", str(ink_path)], timeout=30, check=False)

    if not result.success:
        return {"success": False, "error": result.error}

    # Parse stats output
    # Example output:
    # Stats for 'story.ink':
    #     Words: 1234
    #     Choices: 42
    stats = {}
    for line in result.output.split("\n"):
        line = line.strip()
        if "Words:" in line:
            try:
                stats["words"] = int(line.split("Words:")[1].strip())
            except (ValueError, IndexError):
                pass
        elif "Choices:" in line:
            try:
                stats["choices"] = int(line.split("Choices:")[1].strip())
            except (ValueError, IndexError):
                pass
        elif "Knots:" in line:
            try:
                stats["knots"] = int(line.split("Knots:")[1].strip())
            except (ValueError, IndexError):
                pass

    return {
        "success": True,
        "path": str(ink_path),
        "stats": stats,
        "raw_output": result.output,
    }


# -------------------------------------------------------------------
# Run / Play
# -------------------------------------------------------------------

def run_story(
    story_path: str,
    choices: Optional[list[int]] = None,
    seed: Optional[int] = None,
) -> CommandResult:
    """
    Run a compiled ink story with choice inputs.

    Args:
        story_path: Path to compiled .json story
        choices: List of choice indices to auto-select
        seed: Random seed for deterministic output

    Returns:
        CommandResult
    """
    json_path = Path(story_path).resolve()
    if not json_path.exists():
        return CommandResult(
            success=False,
            error=f"Story JSON not found: {json_path}",
            returncode=1,
        )

    if os.environ.get("INK_MOCK"):
        mock_output = """\
The Adventurer
=============

You are an adventurer in a tavern.

* [Search for treasure] -> 1
    You find 50 gold!
* [Rest] -> 2
    You rest and recover 10 health.
* [Leave] -> 3
    You leave the tavern.

[Enter choice 1-3 or q to quit]"""
        return CommandResult(success=True, output=mock_output, returncode=0)

    cmd = [str(json_path)]
    if seed is not None:
        cmd.extend(["--seed", str(seed)])

    # Build choice input as newline-separated
    input_text = None
    if choices:
        input_text = "\n".join(str(c) for c in choices) + "\n"

    result = _run(cmd, timeout=120, check=False, input_text=input_text)
    return result


# -------------------------------------------------------------------
# Validate
# -------------------------------------------------------------------

def validate_ink(input_path: str) -> dict:
    """
    Validate an ink script (compile with error checking).

    Args:
        input_path: Path to .ink file

    Returns:
        dict with validation result
    """
    ink_path = Path(input_path).resolve()
    if not ink_path.exists():
        return {"success": False, "error": f"Ink script not found: {ink_path}"}

    if os.environ.get("INK_MOCK"):
        return {
            "success": True,
            "path": str(ink_path),
            "valid": True,
            "errors": [],
        }

    # Try to compile - inklecate returns non-zero on errors
    result = compile_ink(str(ink_path), check=False)

    return {
        "success": result.success,
        "path": str(ink_path),
        "valid": result.success,
        "error": result.error if not result.success else None,
    }


# -------------------------------------------------------------------
# New script (write template to file)
# -------------------------------------------------------------------

def new_script(
    output_path: str,
    script_type: str = "choice",
) -> CommandResult:
    """
    Create a new ink script from template.

    Args:
        output_path: Path to create
        script_type: Template type ('hello', 'choice', 'branching', 'variable')

    Returns:
        CommandResult
    """
    result = generate_script(script_type, output_path=output_path)

    if result.get("success"):
        return CommandResult(
            success=True,
            output=f"Created ink script: {output_path}",
            returncode=0,
        )
    return CommandResult(
        success=False,
        error=result.get("error", "Failed to create script"),
        returncode=1,
    )
