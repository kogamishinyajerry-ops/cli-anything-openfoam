"""
gltf_cli.py - Click CLI entry point for cli-anything-gltf

Commands:
  info      - Show glTF file info (nodes, meshes, images count)
  validate  - Validate glTF/GLB file
  convert   - Convert glTF <-> GLB
  version   - Show version

Follows HARNESS.md principles:
  - Real glTF operations via Python stdlib
  - Supports both JSON (glTF) and binary (GLB) formats
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

import click

from .utils import gltf_backend as gb

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
    """glTF CLI - validate, convert, and inspect glTF files.

    glTF (Graphics Library Transmission Format) is a runtime 3D asset
    delivery format. This CLI handles both JSON (.gltf) and binary (.glb)
    variants.

    Examples:
      gltf info model.gltf
      gltf validate scene.glb
      gltf convert model.gltf --output scene.glb
      gltf convert scene.glb --output model.gltf
    """
    global JSON_MODE
    JSON_MODE = json_output
    ctx.ensure_object(dict)
    ctx.obj["json"] = json_output

    if ctx.invoked_subcommand is None:
        echo(f"glTF harness (CLI wrapper)")
        version_info = gb.get_version()
        if version_info.get("success"):
            echo(f"Version: {version_info['version']}")
            echo(f"Tool: {version_info.get('tool', 'unknown')}")
        else:
            echo("glTF: not available")


# ==================================================================
# version command
# ==================================================================

@cli.command("version")
def cmd_version():
    """Show glTF version information."""
    global JSON_MODE
    info = gb.get_version()

    if JSON_MODE:
        json_out(info)
    else:
        if info.get("success"):
            echo(f"glTF version: {info['version']}")
            echo(f"Tool: {info.get('tool', 'unknown')}")
        else:
            error("Failed to get version")


# ==================================================================
# info command
# ==================================================================

@cli.command("info")
@click.argument("gltf_file", type=click.Path(exists=True))
def cmd_info(gltf_file: str):
    """Show glTF file information.

    Displays statistics about the glTF file including:
    - nodes, meshes, images, accessors count
    - materials, animations, cameras, skins count
    """
    global JSON_MODE

    info = gb.gltf_info(gltf_file)

    if JSON_MODE:
        json_out(info)
    else:
        if info.get("success"):
            echo(f"File: {info.get('path')}")
            echo(f"Format: {info.get('format', 'glTF 2.0')}")
            echo(f"Asset version: {info.get('asset_version', 'unknown')}")
            echo("")
            echo("Statistics:")
            echo(f"  Nodes:     {info.get('nodes', 0)}")
            echo(f"  Meshes:    {info.get('meshes', 0)}")
            echo(f"  Images:    {info.get('images', 0)}")
            echo(f"  Accessors: {info.get('accessors', 0)}")
            echo(f"  Materials: {info.get('materials', 0)}")
            echo(f"  Animations: {info.get('animations', 0)}")
            echo(f"  Cameras:   {info.get('cameras', 0)}")
            echo(f"  Skins:     {info.get('skins', 0)}")
            echo(f"  Buffers:   {info.get('buffers', 0)}")
            echo(f"  BufferViews: {info.get('bufferViews', 0)}")
        else:
            error(f"Failed to get info: {info.get('error', 'unknown error')}")


# ==================================================================
# validate command
# ==================================================================

@cli.command("validate")
@click.argument("gltf_file", type=click.Path(exists=False))
def cmd_validate(gltf_file: str):
    """Validate a glTF or GLB file.

    Checks if the file is valid glTF 2.0 format.
    Works with both JSON (.gltf) and binary (.glb) files.
    """
    global JSON_MODE

    # Check if file exists first (only in non-mock mode)
    path = Path(gltf_file)
    if not path.exists() and not os.environ.get("GLTF_MOCK"):
        if JSON_MODE:
            json_out({"success": False, "error": f"File not found: {gltf_file}"})
        else:
            error(f"File not found: {gltf_file}")
        return

    result = gb.validate_gltf(gltf_file)

    if JSON_MODE:
        json_out({
            "success": result.success,
            "output": result.output,
            "error": result.error,
            "returncode": result.returncode,
        })
    else:
        if result.success:
            success(f"Valid glTF file: {gltf_file}")
        else:
            error(f"Invalid glTF file: {gltf_file}")
            if result.error:
                echo(f"  {result.error}")


# ==================================================================
# convert command
# ==================================================================

@cli.command("convert")
@click.argument("input_file", type=click.Path(exists=False))
@click.option("--output", "-o", required=True, help="Output file path")
def cmd_convert(input_file: str, output: str):
    """Convert between glTF (JSON) and GLB (binary) formats.

    Automatically detects the format based on file extensions:
    - .gltf -> .glb conversion (JSON to binary)
    - .glb -> .gltf conversion (binary to JSON)
    """
    global JSON_MODE

    import os

    input_path = Path(input_file)
    output_path = Path(output)

    # Check input exists (only in non-mock mode)
    if not input_path.exists() and not os.environ.get("GLTF_MOCK"):
        if JSON_MODE:
            json_out({"success": False, "error": f"Input file not found: {input_file}"})
        else:
            error(f"Input file not found: {input_file}")
        return

    # Determine conversion direction
    input_ext = input_path.suffix.lower()
    output_ext = output_path.suffix.lower()

    if input_ext == ".glb" and output_ext == ".gltf":
        result = gb.glb_to_gltf(input_file, output)
    elif input_ext in [".gltf", ""] and output_ext == ".glb":
        result = gb.gltf_to_glb(input_file, output)
    elif input_ext == ".gltf" and output_ext == ".gltf":
        error("Output must be .glb for glTF input")
        return
    elif input_ext == ".glb" and output_ext == ".glb":
        error("Output must be .gltf for GLB input")
        return
    else:
        error(f"Cannot convert {input_ext} to {output_ext}")
        return

    if JSON_MODE:
        json_out({
            "success": result.success,
            "output": result.output,
            "error": result.error,
            "returncode": result.returncode,
        })
    else:
        if result.success:
            success(f"Converted: {input_file} -> {output}")
        else:
            error(f"Conversion failed")
            if result.error:
                echo(f"  {result.error}")


# ==================================================================
# Entry point
# ==================================================================

def main():
    cli(obj={})


if __name__ == "__main__":
    main()
