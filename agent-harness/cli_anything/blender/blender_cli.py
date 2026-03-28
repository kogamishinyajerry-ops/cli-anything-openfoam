"""
blender_cli.py - Click CLI for cli-anything-blender

Commands:
  render       - Render images and animations
  import       - Import 3D models
  export       - Export 3D models
  object       - Object operations (list, info, modifier, material)
  scene        - Scene operations (stats)
  batch        - Batch convert files
  info         - Version info

All commands support --json for machine-readable output.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import click

from .utils import blender_backend as bb

__all__ = ["main"]

JSON_MODE = False


def echo(msg: str, **kwargs) -> None:
    click.echo(msg, err=True, **kwargs)


def success(msg: str) -> None:
    click.echo("[OK] {}".format(msg), err=True)


def error(msg: str) -> None:
    click.echo("[ERROR] {}".format(msg), err=True, color="red")


def json_out(data: dict) -> None:
    click.echo(json.dumps(data, indent=2))


# -------------------------------------------------------------------
# Main
# -------------------------------------------------------------------

@click.group(invoke_without_command=True)
@click.option("--json", "json_output", is_flag=True, help="JSON output mode")
@click.pass_context
def cli(ctx, json_output: bool):
    """Blender 3D Suite — batch render, convert, and process 3D assets from CLI.

    Blender is a professional 3D creation suite with powerful CLI capabilities.
    Use --background mode for headless rendering and batch processing.

    Examples:
      blender render image --input scene.blend --output render.png
      blender import model --path model.obj
      blender object list
      blender batch convert --input ./models --output ./glb --format glb
    """
    global JSON_MODE
    JSON_MODE = json_output
    ctx.ensure_object(dict)
    ctx.obj["json"] = json_output

    if ctx.invoked_subcommand is None:
        echo("Blender harness (CLI wrapper)")
        v = bb.get_version()
        if v.get("success"):
            echo("Version: {}".format(v["version"]))
        else:
            echo("Blender: not found")


# ==================================================================
# info command
# ==================================================================

@cli.group("info")
def cmd_info():
    """Version and information."""
    pass


@cmd_info.command("version")
def cmd_version():
    """Show Blender version."""
    global JSON_MODE
    v = bb.get_version()
    if JSON_MODE:
        json_out(v)
    else:
        if v.get("success"):
            echo("Blender {}".format(v["version"]))
        else:
            error("Failed to get version")
            echo("  {}".format(v.get("error", "")))


# ==================================================================
# render command
# ==================================================================

@cli.group("render")
def cmd_render():
    """Render operations."""
    pass


@cmd_render.command("image")
@click.option("--input", "-i", "input_path", required=True, help="Input .blend file")
@click.option("--output", "-o", required=True, help="Output image path")
@click.option("--frame", "-f", type=int, default=1, help="Frame number")
@click.option("--res", "-r", nargs=2, type=int, default=[1920, 1080], help="Resolution W H")
@click.option("--engine", "-e", type=click.Choice(["CYCLES", "EEVEE", "WORKBENCH"]),
              default="CYCLES", help="Render engine")
@click.option("--samples", "-s", type=int, default=128, help="Sample count (Cycles)")
@click.option("--gpu", is_flag=True, help="Use GPU rendering")
def cmd_render_image(
    input_path: str,
    output: str,
    frame: int,
    res: list,
    engine: str,
    samples: int,
    gpu: bool,
):
    """Render a single frame."""
    global JSON_MODE

    result = bb.render_image(
        blend_path=input_path,
        output_path=output,
        frame=frame,
        resolution_x=res[0],
        resolution_y=res[1],
        engine=engine,
        samples=samples,
        gpu=gpu,
    )

    if JSON_MODE:
        json_out({"success": result.success, "output": result.output, "error": result.error})
    else:
        if result.success:
            success("Rendered: {}".format(output))
        else:
            error("Render failed")
            echo("  {}".format(result.error[:200]))


@cmd_render.command("animation")
@click.option("--input", "-i", "input_path", required=True, help="Input .blend file")
@click.option("--output", "-o", required=True, help="Output directory")
@click.option("--start", type=int, default=1, help="Start frame")
@click.option("--end", type=int, default=250, help="End frame")
@click.option("--res", "-r", nargs=2, type=int, default=[1920, 1080], help="Resolution W H")
@click.option("--engine", "-e", type=click.Choice(["CYCLES", "EEVEE", "WORKBENCH"]),
              default="CYCLES", help="Render engine")
def cmd_render_animation(
    input_path: str,
    output: str,
    start: int,
    end: int,
    res: list,
    engine: str,
):
    """Render animation sequence."""
    global JSON_MODE

    result = bb.render_animation(
        blend_path=input_path,
        output_dir=output,
        start_frame=start,
        end_frame=end,
        resolution_x=res[0],
        resolution_y=res[1],
        engine=engine,
    )

    if JSON_MODE:
        json_out({"success": result.success, "output": result.output, "error": result.error})
    else:
        if result.success:
            success("Animation rendered: frames {}-{}".format(start, end))
            echo("  Output: {}".format(output))
        else:
            error("Animation render failed")
            echo("  {}".format(result.error[:200]))


# ==================================================================
# import command
# ==================================================================

@cli.group("import")
def cmd_import():
    """Import operations."""
    pass


@cmd_import.command("model")
@click.option("--path", "-p", required=True, help="Model file path")
@click.option("--type", "-t", help="Import type (auto-detected from extension)")
def cmd_import_model(path: str, type: Optional[str]):
    """Import a 3D model file."""
    global JSON_MODE

    result = bb.import_model(path, import_type=type)

    if JSON_MODE:
        json_out({"success": result.success, "output": result.output, "error": result.error})
    else:
        if result.success:
            success("Imported: {}".format(path))
        else:
            error("Import failed")
            echo("  {}".format(result.error[:200]))


# ==================================================================
# export command
# ==================================================================

@cli.group("export")
def cmd_export():
    """Export operations."""
    pass


@cmd_export.command("model")
@click.option("--input", "-i", required=True, help="Blend file or object to export")
@click.option("--output", "-o", required=True, help="Output file path")
@click.option("--type", "-t", help="Export type (auto-detected from extension)")
def cmd_export_model(input: str, output: str, type: Optional[str]):
    """Export a model."""
    global JSON_MODE

    result = bb.export_model(input, output, export_type=type)

    if JSON_MODE:
        json_out({"success": result.success, "output": result.output, "error": result.error})
    else:
        if result.success:
            success("Exported: {}".format(output))
        else:
            error("Export failed")
            echo("  {}".format(result.error[:200]))


# ==================================================================
# object command
# ==================================================================

@cli.group("object")
def cmd_object():
    """Object operations."""
    pass


@cmd_object.command("list")
@click.option("--input", "-i", help="Blend file (uses current scene if None)")
def cmd_object_list(input: Optional[str]):
    """List objects in scene."""
    global JSON_MODE

    info = bb.list_objects(blend_path=input)

    if JSON_MODE:
        json_out(info)
    else:
        if info.get("success"):
            echo("Objects ({}):".format(len(info.get("objects", []))))
            for obj in info.get("objects", []):
                echo("  {} [{}]".format(obj["name"], obj["type"]))
        else:
            error("Failed to list objects")
            echo("  {}".format(info.get("error", "")))


@cmd_object.command("info")
@click.option("--name", "-n", required=True, help="Object name")
@click.option("--input", "-i", help="Blend file")
def cmd_object_info(name: str, input: Optional[str]):
    """Get object info."""
    global JSON_MODE

    info = bb.get_object_info(name, blend_path=input)

    if JSON_MODE:
        json_out(info)
    else:
        if info.get("success"):
            echo("Object: {}".format(info.get("name")))
            echo("  Type:     {}".format(info.get("type")))
            echo("  Location: {}".format(info.get("location")))
            echo("  Rotation: {}".format(info.get("rotation")))
            echo("  Scale:    {}".format(info.get("scale")))
        else:
            error("Object not found: {}".format(name))


@cmd_object.command("modifier")
@click.option("--name", "-n", required=True, help="Object name")
@click.option("--type", "-t", required=True,
              type=click.Choice(["SUBSURF", "MIRROR", "ARRAY", "BEVEL", "SOLIDIFY", "DECIMATE"]),
              help="Modifier type")
@click.option("--input", "-i", help="Blend file")
def cmd_object_modifier(name: str, type: str, input: Optional[str]):
    """Add modifier to object."""
    global JSON_MODE

    result = bb.add_modifier(name, type, blend_path=input)

    if JSON_MODE:
        json_out({"success": result.success, "output": result.output, "error": result.error})
    else:
        if result.success:
            success("Added {} modifier to {}".format(type, name))
        else:
            error("Failed to add modifier")
            echo("  {}".format(result.error[:200]))


@cmd_object.command("material")
@click.option("--name", "-n", required=True, help="Object name")
@click.option("--material", "-m", required=True, help="Material name")
@click.option("--input", "-i", help="Blend file")
def cmd_object_material(name: str, material: str, input: Optional[str]):
    """Add material to object."""
    global JSON_MODE

    result = bb.add_material(material, name, blend_path=input)

    if JSON_MODE:
        json_out({"success": result.success, "output": result.output, "error": result.error})
    else:
        if result.success:
            success("Added material {} to {}".format(material, name))
        else:
            error("Failed to add material")
            echo("  {}".format(result.error[:200]))


# ==================================================================
# scene command
# ==================================================================

@cli.group("scene")
def cmd_scene():
    """Scene operations."""
    pass


@cmd_scene.command("stats")
@click.option("--input", "-i", help="Blend file")
def cmd_scene_stats(input: Optional[str]):
    """Get scene statistics."""
    global JSON_MODE

    info = bb.get_scene_stats(blend_path=input)

    if JSON_MODE:
        json_out(info)
    else:
        if info.get("success"):
            echo("Scene Statistics")
            echo("=================")
            echo("  Objects:   {}".format(info.get("objects", 0)))
            echo("  Meshes:    {}".format(info.get("meshes", 0)))
            echo("  Materials: {}".format(info.get("materials", 0)))
            echo("  Lights:    {}".format(info.get("lights", 0)))
            echo("  Cameras:   {}".format(info.get("cameras", 0)))
        else:
            error("Failed to get stats")
            echo("  {}".format(info.get("error", "")))


# ==================================================================
# batch command
# ==================================================================

@cli.group("batch")
def cmd_batch():
    """Batch operations."""
    pass


@cmd_batch.command("convert")
@click.option("--input", "-i", required=True, help="Input directory")
@click.option("--output", "-o", required=True, help="Output directory")
@click.option("--format", "-f", required=True,
              type=click.Choice(["obj", "fbx", "gltf", "glb", "stl", "ply"]),
              help="Output format")
def cmd_batch_convert(input: str, output: str, format: str):
    """Batch convert files to another format."""
    global JSON_MODE

    # Detect input format from first file
    input_path = Path(input)
    if not input_path.exists():
        error("Input directory not found: {}".format(input))
        return

    # Find first supported file to detect format
    exts = [".obj", ".fbx", ".gltf", ".glb", ".stl", ".ply"]
    input_format = None
    for f in input_path.iterdir():
        if f.suffix.lower() in exts:
            input_format = f.suffix.lower()[1:]
            break

    if not input_format:
        error("No supported model files found in {}".format(input))
        return

    result = bb.batch_convert(input, output, input_format=input_format, output_format=format)

    if JSON_MODE:
        json_out({"success": result.success, "output": result.output, "error": result.error})
    else:
        if result.success:
            success("Converted {}/{} to {}".format(input, input_format, output))
        else:
            error("Batch conversion failed")
            echo("  {}".format(result.error[:200]))


# ==================================================================
# Entry point
# ==================================================================

def main():
    cli(obj={})


if __name__ == "__main__":
    main()
