"""
assimp_cli.py - Assimp CLI harness

Usage:
  assimp info <model>           Show model information
  assimp convert <in> <out>    Convert between formats
  assimp batch <indir> <outdir> --ifmt <fmt> --ofmt <fmt>
  assimp validate <model>      Validate a model file
  assimp formats               List supported formats
"""

from __future__ import annotations

import click
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from cli_anything.assimp.utils import assimp_backend as ab


@click.group()
@click.version_option(version=ab.ASSIMP_VERSION, prog_name="assimp")
def cli():
    """Assimp 3D model conversion and inspection CLI."""
    pass


# ------------------------------------------------------------------
# Info
# ------------------------------------------------------------------

@cli.group("info")
def info_group():
    """Model information commands."""
    pass


@info_group.command("model")
@click.argument("model_path", type=click.Path(exists=True))
def info_model(model_path: str):
    """Show detailed information about a 3D model."""
    result = ab.get_model_info(model_path)
    if result.get("success"):
        click.echo(json.dumps(result, indent=2))
    else:
        click.echo("Error: " + result.get("error", "Unknown error"), err=True)
        sys.exit(1)


@info_group.command("formats")
def info_formats():
    """List all supported import/export formats."""
    formats = ab.SUPPORTED_FORMATS
    click.echo("Supported formats:")
    for fmt, desc in sorted(formats.items()):
        click.echo("  {:8s} - {}".format(fmt, desc))


# ------------------------------------------------------------------
# Convert
# ------------------------------------------------------------------

@cli.group("convert")
def convert_group():
    """Format conversion commands."""
    pass


@convert_group.command("single")
@click.argument("input_path", type=click.Path(exists=True))
@click.argument("output_path", type=click.Path())
@click.option("--matrix", help="4x4 transformation matrix (comma-separated)")
@click.option("--flip-normals", is_flag=True, help="Flip normal vectors")
@click.option("--flip-uvs", is_flag=True, help="Flip UV coordinates")
@click.option("--no-process", is_flag=True, help="Skip processing steps")
def convert_single(
    input_path: str,
    output_path: str,
    matrix: str | None,
    flip_normals: bool,
    flip_uvs: bool,
    no_process: bool,
):
    """Convert a single 3D model to another format."""
    result = ab.convert(
        input_path=input_path,
        output_path=output_path,
        matrix=matrix,
        flip_normals=flip_normals,
        flip_uvs=flip_uvs,
        process_all=not no_process,
    )
    if result.success:
        click.echo("Success: {}".format(result.output))
    else:
        click.echo("Error: {}".format(result.error), err=True)
        sys.exit(1)


@convert_group.command("batch")
@click.argument("input_dir", type=click.Path(exists=True, file_okay=False))
@click.argument("output_dir", type=click.Path())
@click.option("--ifmt", "input_format", required=True, help="Input format (e.g. stl, obj)")
@click.option("--ofmt", "output_format", required=True, help="Output format (e.g. gltf, fbx)")
@click.option("--recursive", is_flag=True, help="Search subdirectories")
def convert_batch(
    input_dir: str,
    output_dir: str,
    input_format: str,
    output_format: str,
    recursive: bool,
):
    """Batch convert all files of a given format in a directory."""
    result = ab.convert_batch(
        input_dir=input_dir,
        output_dir=output_dir,
        input_format=input_format,
        output_format=output_format,
        recursive=recursive,
    )
    if result.success:
        click.echo("Success: {}".format(result.output))
    else:
        click.echo("Error: {}".format(result.output), err=True)
        sys.exit(1)


# ------------------------------------------------------------------
# Validate
# ------------------------------------------------------------------

@cli.command("validate")
@click.argument("model_path", type=click.Path(exists=True))
@click.option("--json", "use_json", is_flag=True, help="Output as JSON")
def validate_cmd(model_path: str, use_json: bool):
    """Validate a 3D model file."""
    result = ab.validate(model_path)
    if use_json:
        click.echo(json.dumps(result, indent=2))
        return

    if result.get("valid"):
        click.echo("[OK] Model is valid: {}".format(model_path))
    else:
        click.echo("[FAIL] Model has issues:", err=True)

    if result.get("issues"):
        for issue in result["issues"]:
            click.echo("  ERROR: {}".format(issue), err=True)
    if result.get("warnings"):
        for warn in result["warnings"]:
            click.echo("  WARN: {}".format(warn))

    if not result.get("valid"):
        sys.exit(1)


# ------------------------------------------------------------------
# Version
# ------------------------------------------------------------------

@cli.command("version")
def version_cmd():
    """Show Assimp version."""
    info = ab.get_version()
    if info.get("success"):
        click.echo("Assimp version: {}".format(info.get("version")))
    else:
        click.echo("Assimp: not found (set ASSIMP_PATH or install ASSIMP)", err=True)
        sys.exit(1)


def main():
    cli()


if __name__ == "__main__":
    main()
