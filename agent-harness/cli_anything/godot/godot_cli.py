"""
godot_cli.py - Click CLI entry point for cli-anything-godot

Command groups:
  project     - Project creation and management
  run         - Run scripts and scenes
  export      - Export/build projects
  script      - GDScript generation
  info        - Version and settings

All commands support --json for machine-readable output.

Follows HARNESS.md principles:
  - Real Godot CLI commands
  - Headless/server builds supported
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

import click

from .utils import godot_backend as gb

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
@click.option("--project", "-p", type=click.Path(), help="Godot project path")
@click.pass_context
def cli(ctx, json_output: bool, project: Optional[str]):
    """Godot Engine CLI — create, build, and run Godot projects from the command line.

    Godot is an open-source game engine with a powerful CLI for
    headless builds, script execution, and project management.

    Examples:
      godot project new --path mygame --name "My Game"
      godot export --preset web --project mygame
      godot run script --script res://ai_controller.gd --project mygame
    """
    global JSON_MODE
    JSON_MODE = json_output
    ctx.ensure_object(dict)
    ctx.obj["json"] = json_output
    ctx.obj["project"] = project

    if ctx.invoked_subcommand is None:
        echo(f"Godot harness (CLI wrapper)")
        version_info = gb.get_version()
        if version_info.get("success"):
            echo(f"Version: {version_info['version']}")
        else:
            echo("Godot: not found")


# ==================================================================
# info command
# ==================================================================

@cli.group("info")
def cmd_info():
    """Version and settings information."""
    pass


@cmd_info.command("version")
def cmd_version():
    """Show Godot version."""
    global JSON_MODE
    info = gb.get_version()

    if JSON_MODE:
        json_out(info)
    else:
        if info.get("success"):
            echo(f"Godot {info['version']}")
            echo(f"  Major: {info['version_major']}")
            echo(f"  Minor: {info['version_minor']}")
            echo(f"  Patch: {info['version_patch']}")
            echo(f"  Config: {info['build_config']}")
        else:
            error("Failed to get version")
            echo(f"  {info.get('error', '')}")


@cmd_info.command("settings")
def cmd_settings():
    """Show Godot editor settings paths."""
    global JSON_MODE
    info = gb.get_editor_settings()

    if JSON_MODE:
        json_out(info)
    else:
        if info.get("success"):
            echo("Editor settings:")
            for key, val in info.get("paths", {}).items():
                echo(f"  {key}: {val}")


# ==================================================================
# project command
# ==================================================================

@cli.group("project")
def cmd_project():
    """Project creation and management."""
    pass


@cmd_project.command("new")
@click.option("--path", "-p", required=True, help="Project directory path")
@click.option("--name", "-n", help="Project name")
@click.pass_context
def cmd_new(ctx, path: str, name: Optional[str]):
    """Create a new Godot project."""
    global JSON_MODE
    project = ctx.obj.get("project")

    result = gb.new_project(path, project_name=name)

    if JSON_MODE:
        json_out({"success": result.success, "path": path, "output": result.output})
    else:
        if result.success:
            success(f"Project created: {path}")
        else:
            error(f"Failed to create project")
            echo(f"  {result.error[:200]}")


@cmd_project.command("open")
@click.pass_context
def cmd_open(ctx):
    """Open Godot project (launch editor)."""
    global JSON_MODE
    project = ctx.obj.get("project")

    if not project:
        error("Project path required (--project)")
        return

    result = gb.open_project(project, headless=True)

    if JSON_MODE:
        json_out({"success": result.success, "output": result.output})
    else:
        if result.success:
            success("Project opened")
        else:
            error("Failed to open project")
            echo(f"  {result.error[:200]}")


@cmd_project.command("import")
@click.pass_context
def cmd_import(ctx):
    """Import project (run import pipeline)."""
    global JSON_MODE
    project = ctx.obj.get("project")

    if not project:
        error("Project path required (--project)")
        return

    result = gb.import_project(project)

    if JSON_MODE:
        json_out({"success": result.success, "output": result.output})
    else:
        if result.success:
            success("Project imported")
        else:
            error("Import failed")
            echo(f"  {result.error[:200]}")


@cmd_project.command("clean")
@click.pass_context
def cmd_clean(ctx):
    """Clean project build artifacts."""
    global JSON_MODE
    project = ctx.obj.get("project")

    if not project:
        error("Project path required (--project)")
        return

    result = gb.clean_project(project)

    if JSON_MODE:
        json_out({"success": result.success, "output": result.output})
    else:
        if result.success:
            success("Project cleaned")
        else:
            error("Clean failed")
            echo(f"  {result.error[:200]}")


@cmd_project.command("presets")
@click.pass_context
def cmd_presets(ctx):
    """List export presets for project."""
    global JSON_MODE
    project = ctx.obj.get("project")

    if not project:
        error("Project path required (--project)")
        return

    result = gb.list_export_presets(project)

    if JSON_MODE:
        json_out(result)
    else:
        if result.get("success"):
            presets = result.get("presets", [])
            success(f"Found {len(presets)} export presets")
            for p in presets:
                runnable = " [runnable]" if p.get("runnable") else ""
                echo(f"  {p.get('name', 'unknown')}: {p.get('platform', '')}{runnable}")
        else:
            error(f"Failed to list presets")
            echo(f"  {result.get('error', '')}")


# ==================================================================
# export command
# ==================================================================

@cli.command("export")
@click.option("--preset", "-r", required=True, help="Export preset name (e.g. windows, linux, web)")
@click.option("--output", "-o", help="Output file/directory path")
@click.option("--project", "-p", help="Project path (if not using --project global)")
@click.pass_context
def cmd_export(ctx, preset: str, output: Optional[str], project: Optional[str]):
    """Export project with specified preset."""
    global JSON_MODE
    proj = project or ctx.obj.get("project")

    result = gb.export_project(preset, output_path=output, project_path=proj)

    if JSON_MODE:
        json_out({"success": result.success, "preset": preset, "output": result.output})
    else:
        if result.success:
            success(f"Exported: {preset}")
        else:
            error(f"Export failed")
            echo(f"  {result.error[:200]}")


# ==================================================================
# run command
# ==================================================================

@cli.group("run")
def cmd_run():
    """Run scripts and scenes."""
    pass


@cmd_run.command("script")
@click.option("--script", "-s", required=True, help="Path to GDScript file")
@click.option("--args", "-a", multiple=True, help="Arguments to pass to script")
@click.option("--project", "-p", help="Project path")
@click.pass_context
def cmd_run_script(ctx, script: str, args: tuple, project: Optional[str]):
    """Execute a GDScript script."""
    global JSON_MODE
    proj = project or ctx.obj.get("project")

    arg_list = list(args) if args else None
    result = gb.run_script(script, project_path=proj, args=arg_list)

    if JSON_MODE:
        json_out({
            "success": result.success,
            "script": script,
            "output": result.output,
            "error": result.error,
        })
    else:
        if result.success:
            success(f"Script executed: {script}")
            if result.output:
                echo(result.output)
        else:
            error(f"Script failed")
            echo(f"  {result.error[:200]}")


@cmd_run.command("scene")
@click.option("--scene", "-s", required=True, help="Path to scene file (.tscn)")
@click.option("--project", "-p", help="Project path")
@click.pass_context
def cmd_run_scene(ctx, scene: str, project: Optional[str]):
    """Run a Godot scene."""
    global JSON_MODE
    proj = project or ctx.obj.get("project")

    result = gb.run_scene(scene, project_path=proj)

    if JSON_MODE:
        json_out({"success": result.success, "scene": scene, "output": result.output})
    else:
        if result.success:
            success(f"Scene ran: {scene}")
        else:
            error(f"Scene run failed")
            echo(f"  {result.error[:200]}")


# ==================================================================
# script command
# ==================================================================

@cli.group("script")
def cmd_script():
    """GDScript generation."""
    pass


@cmd_script.command("generate")
@click.option("--type", "-t", type=click.Choice(["basic_node", "character_controller", "state_machine"]),
              required=True, help="Script template type")
@click.option("--output", "-o", help="Output file path")
def cmd_script_generate(type: str, output: Optional[str]):
    """Generate a GDScript template."""
    global JSON_MODE

    result = gb.generate_script(type, output_path=output)

    if JSON_MODE:
        json_out(result)
    else:
        if result.get("success"):
            success(f"Script generated: {type}")
            if output:
                echo(f"  Saved to: {output}")
            else:
                echo("---")
                echo(result.get("content", ""))
                echo("---")
        else:
            error(f"Generation failed: {result.get('error', '')}")


@cmd_script.command("list-templates")
def cmd_list_templates():
    """List available script templates."""
    global JSON_MODE

    result = gb.list_script_types()

    if JSON_MODE:
        json_out(result)
    else:
        if result.get("success"):
            echo("Available script templates:")
            for t in result.get("types", []):
                echo(f"  - {t}")


# ==================================================================
# Entry point
# ==================================================================

def main():
    cli(obj={})


if __name__ == "__main__":
    main()
