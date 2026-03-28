"""
usd_cli.py - Universal Scene Description (USD) CLI harness

Usage:
  usd info <file>           Show USD stage info (prims, layers)
  usd validate <file>      Validate USD file with usdchecker
  usd convert <in> <out>   Convert USD to another format (usda/usdc/usdz)
  usd layers <file>        List layers in a USD file
  usd version              Show USD version
"""

from __future__ import annotations

import click
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from cli_anything.usd.utils import usd_backend as ub


@click.group()
@click.version_option(version=ub.USD_VERSION, prog_name="usd")
def cli():
    """Universal Scene Description (USD) CLI."""
    pass


# ------------------------------------------------------------------
# Info
# ------------------------------------------------------------------

@cli.command("info")
@click.argument("usd_file", type=click.Path(exists=True))
@click.option("--json", "use_json", is_flag=True, help="Output as JSON")
def info_cmd(usd_file: str, use_json: bool):
    """Show USD stage info (prims, layers)."""
    result = ub.usd_info(usd_file)
    if result.get("success"):
        if use_json:
            click.echo(json.dumps(result, indent=2))
        else:
            click.echo("File: {}".format(result.get("filename")))
            click.echo("Stage: {}".format(result.get("stage", "N/A")))
            click.echo("Prim count: {}".format(result.get("prim_count", 0)))
            click.echo("Layer count: {}".format(result.get("layer_count", 0)))
            if result.get("prims"):
                click.echo("\nPrims:")
                for prim in result.get("prims", []):
                    click.echo("  - {}".format(prim))
            if result.get("layers"):
                click.echo("\nLayers:")
                for layer in result.get("layers", []):
                    click.echo("  - {}".format(layer))
    else:
        click.echo("Error: " + result.get("error", "Unknown error"), err=True)
        sys.exit(1)


# ------------------------------------------------------------------
# Validate
# ------------------------------------------------------------------

@cli.command("validate")
@click.argument("usd_file", type=click.Path(exists=True))
@click.option("--json", "use_json", is_flag=True, help="Output as JSON")
def validate_cmd(usd_file: str, use_json: bool):
    """Validate USD file with usdchecker."""
    result = ub.validate_usd(usd_file)
    if use_json:
        output = {
            "success": result.success,
            "output": result.output,
            "error": result.error,
            "returncode": result.returncode,
        }
        click.echo(json.dumps(output, indent=2))
        return

    if result.success:
        click.echo("[OK] {} is valid".format(Path(usd_file).name))
    else:
        click.echo("[FAIL] Validation failed: {}".format(result.error), err=True)
        sys.exit(1)


# ------------------------------------------------------------------
# Convert
# ------------------------------------------------------------------

@cli.command("convert")
@click.argument("input_file", type=click.Path(exists=True))
@click.argument("output_file", type=click.Path())
@click.option(
    "--format",
    "-f",
    type=click.Choice(["usda", "usdc", "usdz"]),
    default="usda",
    help="Output format (default: usda)",
)
def convert_cmd(input_file: str, output_file: str, format: str):
    """Convert USD to another format (usda -> usdc, usdc -> usda, etc.)."""
    result = ub.convert_usd(input_file, output_file, format)
    if result.success:
        click.echo("Success: {}".format(result.output))
    else:
        click.echo("Error: {}".format(result.error), err=True)
        sys.exit(1)


# ------------------------------------------------------------------
# Layers
# ------------------------------------------------------------------

@cli.command("layers")
@click.argument("usd_file", type=click.Path(exists=True))
@click.option("--json", "use_json", is_flag=True, help="Output as JSON")
def layers_cmd(usd_file: str, use_json: bool):
    """List layers in a USD file."""
    result = ub.list_layers(usd_file)
    if result.get("success"):
        if use_json:
            click.echo(json.dumps(result, indent=2))
        else:
            click.echo("File: {}".format(result.get("filename")))
            click.echo("Layer count: {}".format(result.get("layer_count", 0)))
            if result.get("layers"):
                click.echo("\nLayers:")
                for layer in result.get("layers", []):
                    click.echo("  - {}".format(layer.get("name", layer.get("path", "N/A"))))
    else:
        click.echo("Error: " + result.get("error", "Unknown error"), err=True)
        sys.exit(1)


# ------------------------------------------------------------------
# Version
# ------------------------------------------------------------------

@cli.command("version")
def version_cmd():
    """Show USD version."""
    info = ub.get_version()
    if info.get("success"):
        click.echo("USD version: {}".format(info.get("version")))
    else:
        click.echo("USD: not found (set USD_BIN_PATH or install USD)", err=True)
        sys.exit(1)


def main():
    cli()


if __name__ == "__main__":
    main()
