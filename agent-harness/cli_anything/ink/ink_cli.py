"""
ink_cli.py - Click CLI entry point for cli-anything-ink

Command groups:
  compile     - Compile ink scripts to JSON
  run         - Run compiled ink stories
  stats       - Story statistics
  validate    - Validate ink scripts
  new         - Create new ink script
  list        - List available templates

All commands support --json for machine-readable output.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

import click

from .utils import ink_backend as ib

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
@click.pass_context
def cli(ctx, json_output: bool):
    """Ink Interactive Narrative Scripting — create branching stories with choices.

    Ink is a scripting language for writing interactive narrative.
    Use inklecate to compile .ink scripts to JSON and run them.

    Examples:
      ink new --path story.ink --type choice
      ink compile story.ink
      ink stats story.ink
      ink validate story.ink
    """
    global JSON_MODE
    JSON_MODE = json_output
    ctx.ensure_object(dict)
    ctx.obj["json"] = json_output

    if ctx.invoked_subcommand is None:
        echo("Ink harness (inklecate CLI wrapper)")
        version_info = ib.get_version()
        if version_info.get("success"):
            echo(f"Version: {version_info['version']}")
        else:
            echo("Inklecate: not found")


# ==================================================================
# info command
# ==================================================================

@cli.group("info")
def cmd_info():
    """Version and settings information."""
    pass


@cmd_info.command("version")
def cmd_version():
    """Show inklecate version."""
    global JSON_MODE
    info = ib.get_version()

    if JSON_MODE:
        json_out(info)
    else:
        if info.get("success"):
            echo(f"Ink {info['version']}")
        else:
            error("Failed to get version")
            echo(f"  {info.get('error', '')}")


# ==================================================================
# new command
# ==================================================================

@cli.command("new")
@click.option("--path", "-p", required=True, help="Output .ink file path")
@click.option("--type", "-t",
              type=click.Choice(["hello", "choice", "branching", "variable"]),
              default="choice",
              help="Script template type")
def cmd_new(path: str, type: str):
    """Create a new ink script from template."""
    global JSON_MODE

    result = ib.new_script(path, script_type=type)

    if JSON_MODE:
        json_out({"success": result.success, "path": path, "output": result.output})
    else:
        if result.success:
            success(f"Created: {path}")
        else:
            error("Failed to create script")
            echo(f"  {result.error[:200]}")


# ==================================================================
# list command
# ==================================================================

@cli.command("list")
def cmd_list():
    """List available ink script templates."""
    global JSON_MODE

    result = ib.list_script_types()

    if JSON_MODE:
        json_out(result)
    else:
        if result.get("success"):
            echo("Available templates:")
            for t in result.get("types", []):
                echo(f"  - {t}")


# ==================================================================
# compile command
# ==================================================================

@cli.group("compile")
def cmd_compile():
    """Compile ink scripts to JSON."""
    pass


@cmd_compile.command("run")
@click.option("--input", "-i", required=True, help="Input .ink file")
@click.option("--output", "-o", help="Output .json file")
@click.option("--all", "all_stories", is_flag=True, help="Compile all named choice sections")
def cmd_compile_run(input: str, output: Optional[str], all_stories: bool):
    """Compile ink to JSON."""
    global JSON_MODE

    result = ib.compile_ink(input, output_path=output, all_stories=all_stories)

    if JSON_MODE:
        json_out({"success": result.success, "input": input, "output": result.output})
    else:
        if result.success:
            success(f"Compiled: {input}")
            if output:
                echo(f"  Output: {output}")
        else:
            error("Compilation failed")
            echo(f"  {result.error[:200]}")


# ==================================================================
# stats command
# ==================================================================

@cli.command("stats")
@click.option("--input", "-i", required=True, help="Input .ink file")
def cmd_stats(input: str):
    """Show story statistics."""
    global JSON_MODE

    info = ib.get_stats(input)

    if JSON_MODE:
        json_out(info)
    else:
        if info.get("success"):
            echo(f"Stats for: {input}")
            stats = info.get("stats", {})
            if "words" in stats:
                echo(f"  Words: {stats['words']}")
            if "choices" in stats:
                echo(f"  Choices: {stats['choices']}")
            if "knots" in stats:
                echo(f"  Knots: {stats['knots']}")
            if "gather_points" in stats:
                echo(f"  Gather points: {stats['gather_points']}")
        else:
            error("Failed to get stats")
            echo(f"  {info.get('error', '')}")


# ==================================================================
# validate command
# ==================================================================

@cli.command("validate")
@click.option("--input", "-i", required=True, help="Input .ink file")
def cmd_validate(input: str):
    """Validate an ink script."""
    global JSON_MODE

    info = ib.validate_ink(input)

    if JSON_MODE:
        json_out(info)
    else:
        if info.get("success") and info.get("valid"):
            success(f"Valid: {input}")
        else:
            error(f"Invalid: {input}")
            if info.get("error"):
                echo(f"  {info['error'][:200]}")


# ==================================================================
# run command
# ==================================================================

@cli.group("run")
def cmd_run():
    """Run compiled ink stories."""
    pass


@cmd_run.command("story")
@click.option("--story", "-s", required=True, help="Compiled .json story path")
@click.option("--choice", "-c", multiple=True, type=int, help="Choice index (can repeat, auto-selects in order)")
@click.option("--seed", type=int, help="Random seed")
def cmd_run_story(story: str, choice: tuple, seed: Optional[int]):
    """Run a compiled ink story with choices."""
    global JSON_MODE

    choices = list(choice) if choice else None
    result = ib.run_story(story, choices=choices, seed=seed)

    if JSON_MODE:
        json_out({"success": result.success, "output": result.output, "error": result.error})
    else:
        if result.success:
            success("Story complete")
            echo("---")
            echo(result.output)
        else:
            error("Story run failed")
            echo(f"  {result.error[:200]}")


# ==================================================================
# Entry point
# ==================================================================

def main():
    cli(obj={})


if __name__ == "__main__":
    main()
