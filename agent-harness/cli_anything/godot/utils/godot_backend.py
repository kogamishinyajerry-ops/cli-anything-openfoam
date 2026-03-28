"""
godot_backend.py - Godot Engine CLI wrapper

Wraps real Godot commands for use by the cli-anything harness.

Godot is installed via:
  - macOS: DMG from godotengine.org
  - Linux: tarball from godotengine.org
  - Via package managers (brew, apt)
  - Container: pre-built image

Principles:
  - MUST call real Godot commands, not reimplement
  - Software is HARD dependency - error clearly if not found
  - Supports headless/server builds
  - Operations via Godot CLI + GDScript execution
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

GODOT_VERSION = "1.0.0"


# -------------------------------------------------------------------
# Installation detection
# -------------------------------------------------------------------

GODOT_DEFAULT_PATHS = [
    "/usr/local/bin/godot",
    "/usr/bin/godot",
    "/snap/bin/godot",
    "/Applications/Godot.app/Contents/MacOS/Godot",
    "/Applications/Godot 4.app/Contents/MacOS/Godot",
    Path.home() / ".local/bin/godot",
]


def find_godot() -> Path:
    """
    Locate Godot binary.

    Returns Path to godot executable.
    Raises RuntimeError if not found.
    """
    godot_bin = os.environ.get("GODOT_PATH")

    if not godot_bin:
        for candidate in GODOT_DEFAULT_PATHS:
            p = Path(candidate)
            if p.exists():
                godot_bin = str(p)
                break

    if not godot_bin:
        # Try PATH
        try:
            result = subprocess.run(
                ["which", "godot"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0 and result.stdout.strip():
                godot_bin = result.stdout.strip()
        except Exception:
            pass

    if not godot_bin:
        if os.environ.get("GODOT_MOCK"):
            return Path("/usr/bin/true")
        raise RuntimeError(
            f"Godot not found.\n"
            f"Set GODOT_PATH env var or install Godot Engine.\n"
            f"macOS: https://godotengine.org/download/macos\n"
            f"Linux: https://godotengine.org/download/linux\n"
            f"Or: brew install godot (macOS)"
        )

    bin_path = Path(godot_bin)
    if not bin_path.exists():
        if os.environ.get("GODOT_MOCK"):
            return Path("/usr/bin/true")
        raise RuntimeError(f"Godot not found at {bin_path}")

    return bin_path


# -------------------------------------------------------------------
# Result dataclass
# -------------------------------------------------------------------

@dataclass
class CommandResult:
    """Result of a Godot command execution."""
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
    project_path: Optional[Path] = None,
    timeout: Optional[int] = None,
    check: bool = True,
    headless: bool = False,
) -> CommandResult:
    """
    Run Godot command.

    Args:
        cmd: Command as list of strings
        project_path: Path to Godot project (contains project.godot)
        timeout: Max seconds (None = no limit)
        check: Raise on non-zero exit
        headless: Run in headless mode (no display)

    Returns:
        CommandResult
    """
    godot = find_godot()

    actual_cmd = [str(godot)]
    if headless:
        actual_cmd.append("--headless")
    actual_cmd.extend(cmd)

    start = time.time()
    try:
        proc = subprocess.run(
            actual_cmd,
            cwd=project_path,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
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
    Get Godot version information.

    Returns:
        dict with version info
    """
    if os.environ.get("GODOT_MOCK"):
        return {
            "success": True,
            "version": "4.2.2",
            "version_major": 4,
            "version_minor": 2,
            "version_patch": 2,
            "build_config": "release",
        }

    result = _run(["--version"], timeout=15, check=False)

    if result.success:
        # Parse version output like "4.2.2.stable.official"
        version_str = result.output.strip()
        match = re.match(r"(\d+)\.(\d+)\.(\d+)", version_str)
        if match:
            return {
                "success": True,
                "version": version_str,
                "version_major": int(match.group(1)),
                "version_minor": int(match.group(2)),
                "version_patch": int(match.group(3)),
                "build_config": "stable",
            }

    return {
        "success": False,
        "error": result.error or "Failed to get version",
    }


def get_editor_settings() -> dict:
    """
    Get Godot editor settings path.

    Returns:
        dict with settings paths
    """
    result = _run(
        ["--editor-settings"],
        timeout=15,
        check=False,
    )

    paths = {}
    if result.success:
        for line in result.output.split("\n"):
            if "=" in line:
                key, val = line.split("=", 1)
                paths[key.strip()] = val.strip()

    return {"success": result.success, "paths": paths}


# -------------------------------------------------------------------
# Project operations
# -------------------------------------------------------------------

def new_project(
    project_path: str,
    project_name: Optional[str] = None,
) -> CommandResult:
    """
    Create a new Godot project.

    Args:
        project_path: Path where to create the project
        project_name: Optional project name

    Returns:
        CommandResult
    """
    path = Path(project_path).resolve()
    path.mkdir(parents=True, exist_ok=True)

    # Create minimal project.godot
    if project_name is None:
        project_name = path.name

    project_file = path / "project.godot"
    content = f"""\
; Engine configuration file.
; It's best edited using the editor UI and not directly,
; since the parameters that go here are not all obvious.
;
; Format:
;   [section] ; section goes between []
;   param=value ; assign values to parameters

config_version=5

[application]
config/name="{project_name}"
run/main_scene="res://main.tscn"
config/features=PackedStringArray("4.2", "GL Compatibility")
config/icon="res://icon.svg"

[rendering]
renderer/rendering_method="gl_compatibility"
renderer/rendering_method.mobile="gl_compatibility"
"""
    project_file.write_text(content)

    # Create minimal main scene
    main_scene = path / "main.tscn"
    main_scene.write_text('[gd_scene load_steps=2 format=3]\n\n[sub_resource type="GDScript" id="GDScript_1"]\nscript/sub_class = ExtResource("Script_1")\n\n[node name="Node2D" type="Node2D"]\n')

    if os.environ.get("GODOT_MOCK"):
        return CommandResult(success=True, output=f"Created project at {path}", returncode=0)

    result = _run(
        ["--editor", "--quit"],
        project_path=path,
        timeout=30,
        check=False,
    )

    return CommandResult(
        success=result.success,
        output=f"Project created at {path}",
        error=result.error,
        returncode=result.returncode,
    )


def open_project(
    project_path: str,
    headless: bool = True,
    timeout: Optional[int] = None,
) -> CommandResult:
    """
    Open a Godot project (launch editor or server).

    Args:
        project_path: Path to project directory
        headless: Run headless (no window)
        timeout: Max seconds

    Returns:
        CommandResult
    """
    path = Path(project_path).resolve()
    if not (path / "project.godot").exists():
        return CommandResult(
            success=False,
            error=f"Not a Godot project: {path}",
            returncode=1,
        )

    cmd = ["--editor", "--quit"] if headless else ["--editor"]
    result = _run(cmd, project_path=path, timeout=timeout, check=False, headless=headless)
    return result


def import_project(project_path: str) -> CommandResult:
    """
    Import a Godot project (runs import pipeline).

    Returns:
        CommandResult
    """
    path = Path(project_path).resolve()
    if os.environ.get("GODOT_MOCK"):
        return CommandResult(success=True, output="Project imported", returncode=0)

    result = _run(
        ["--headless", "--editor", "--quit"],
        project_path=path,
        timeout=120,
        check=False,
    )
    return result


def export_project(
    export_preset: str,
    output_path: Optional[str] = None,
    project_path: Optional[str] = None,
) -> CommandResult:
    """
    Export a Godot project using a preset.

    Args:
        export_preset: Name of export preset (e.g. 'windows', 'linux', 'web')
        output_path: Optional output file/directory

    Returns:
        CommandResult
    """
    path = Path(project_path).resolve() if project_path else None

    if os.environ.get("GODOT_MOCK"):
        return CommandResult(success=True, output=f"Exported with preset: {export_preset}", returncode=0)

    cmd = ["--headless", "--export-release"]
    if output_path:
        cmd.append(output_path)
    else:
        # Auto-determine path from preset
        cmd.append(export_preset)

    result = _run(cmd, project_path=path, timeout=300, check=False)
    return result


# -------------------------------------------------------------------
# Script execution
# -------------------------------------------------------------------

def run_script(
    script_path: str,
    project_path: Optional[str] = None,
    args: Optional[list] = None,
) -> CommandResult:
    """
    Execute a GDScript script.

    Args:
        script_path: Path to .gd script file
        project_path: Path to Godot project
        args: Command-line arguments to pass to script

    Returns:
        CommandResult
    """
    script = Path(script_path).resolve()
    if not script.exists():
        return CommandResult(
            success=False,
            error=f"Script not found: {script}",
            returncode=1,
        )

    cmd = ["--headless", "--script", str(script)]
    if args:
        cmd.extend(args)

    project = Path(project_path).resolve() if project_path else None
    result = _run(cmd, project_path=project, timeout=120, check=False)
    return result


def run_scene(
    scene_path: str,
    project_path: Optional[str] = None,
) -> CommandResult:
    """
    Run a Godot scene.

    Returns:
        CommandResult
    """
    scene = Path(scene_path).resolve()
    if not scene.exists():
        return CommandResult(
            success=False,
            error=f"Scene not found: {scene}",
            returncode=1,
        )

    cmd = ["--headless", str(scene)]
    project = Path(project_path).resolve() if project_path else None
    result = _run(cmd, project_path=project, timeout=60, check=False)
    return result


# -------------------------------------------------------------------
# Build / Compile
# -------------------------------------------------------------------

def build_project(
    project_path: str,
    export_preset: Optional[str] = None,
) -> CommandResult:
    """
    Build Godot project.

    Args:
        project_path: Path to project
        export_preset: Optional export preset to build

    Returns:
        CommandResult
    """
    path = Path(project_path).resolve()

    if export_preset:
        return export_project(export_preset, project_path=path)

    if os.environ.get("GODOT_MOCK"):
        return CommandResult(success=True, output="Build complete", returncode=0)

    # Headless build
    result = _run(
        ["--headless", "--editor", "--quit"],
        project_path=path,
        timeout=300,
        check=False,
    )
    return result


def clean_project(project_path: str) -> CommandResult:
    """
    Clean Godot project build artifacts.

    Returns:
        CommandResult
    """
    path = Path(project_path).resolve()
    artifacts = [
        ".godot/",
        "*.tcsn",
        "*.scn",
    ]

    if os.environ.get("GODOT_MOCK"):
        return CommandResult(success=True, output="Cleaned build artifacts", returncode=0)

    # Just remove .godot dir
    godot_dir = path / ".godot"
    if godot_dir.exists():
        import shutil
        shutil.rmtree(godot_dir)
        return CommandResult(success=True, output=f"Removed {godot_dir}", returncode=0)

    return CommandResult(success=True, output="Nothing to clean", returncode=0)


# -------------------------------------------------------------------
# Asset / Export templates
# -------------------------------------------------------------------

def list_export_presets(project_path: str) -> dict:
    """
    List available export presets for a project.

    Returns:
        dict with preset list
    """
    project_file = Path(project_path) / "project.godot"
    if not project_file.exists():
        return {"success": False, "error": "Not a Godot project"}

    presets = []
    in_preset = False
    current_preset = {}

    try:
        content = project_file.read_text()
        for line in content.split("\n"):
            line = line.strip()
            if line.startswith("[preset_"):
                if current_preset:
                    presets.append(current_preset)
                in_preset = True
                current_preset = {"name": "unnamed", "platform": "", "runnable": False}
            elif in_preset:
                if line.startswith("["):
                    in_preset = False
                elif "=" in line:
                    key, val = line.split("=", 1)
                    if key == "name":
                        current_preset["name"] = val.strip('"')
                    elif key == "Runnable":
                        current_preset["runnable"] = val == "true"

        if current_preset:
            presets.append(current_preset)
    except Exception as e:
        return {"success": False, "error": str(e)}

    return {"success": True, "presets": presets}


# -------------------------------------------------------------------
# GDScript helpers (for AI agent use)
# -------------------------------------------------------------------

GDSCRIPT_TEMPLATES = {
    "basic_node": '''\
extends Node2D

func _ready():
    print("Hello from Godot!")

func _process(delta):
    pass
''',

    "character_controller": '''\
extends CharacterBody2D

const SPEED = 300.0
const JUMP_VELOCITY = -400.0

var gravity = ProjectSettings.get_setting("physics_2d/safe_margin")

func _physics_process(delta):
    # Add gravity
    if not is_on_floor():
        velocity.y += gravity * delta

    # Handle jump
    if Input.is_action_just_pressed("ui_accept") and is_on_floor():
        velocity.y = JUMP_VELOCITY

    # Get input
    var direction = Input.get_axis("ui_left", "ui_right")
    if direction:
        velocity.x = direction * SPEED
    else:
        velocity.x = move_toward(velocity.x, 0, SPEED)

    move_and_slide()
''',

    "state_machine": '''\
extends Node

signal state_changed(old_state, new_state)

var current_state: State
var states: Dictionary = {}

class State:
    var name: String
    var owner: Node

    func _init(n: String, o: Node):
        name = n
        owner = o

    func enter():
        pass

    func exit():
        pass

    func process(delta):
        pass

    func physics_process(delta):
        pass

func _ready():
    print("State machine ready")

func add_state(name: String, state: State):
    states[name] = state

func set_state(name: String):
    if current_state and name in states:
        current_state.exit()
        var old = current_state.name
        current_state = states[name]
        current_state.enter()
        emit_signal("state_changed", old, name)
''',
}


def generate_script(script_type: str, output_path: Optional[str] = None) -> dict:
    """
    Generate a GDScript template.

    Args:
        script_type: 'basic_node', 'character_controller', 'state_machine'
        output_path: Optional path to write the script

    Returns:
        dict with script content
    """
    if script_type not in GDSCRIPT_TEMPLATES:
        return {
            "success": False,
            "error": f"Unknown script type: {script_type}",
        }

    content = GDSCRIPT_TEMPLATES[script_type]

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
    """List available GDScript template types."""
    return {
        "success": True,
        "types": list(GDSCRIPT_TEMPLATES.keys()),
    }
