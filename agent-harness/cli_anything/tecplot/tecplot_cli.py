"""
tecplot_cli.py - Click CLI entry point for cli-anything-tecplot

Command groups:
  load        - Load data files, layouts
  plot        - Configure plot type, contours, slices
  export      - Export images and data
  layout      - Layout operations
  macro       - Run macros and Python scripts

All commands support --json for machine-readable output.

Follows HARNESS.md principles:
  - Real Tecplot commands via tecplot_backend Python API
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

import click

from .utils import tecplot_backend as tb

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
@click.option("--container", "-c", default="cfd-openfoam",
              help="Docker container name (default: cfd-openfoam)")
@click.pass_context
def cli(ctx, json_output: bool, container: str):
    """Tecplot 360 professional CFD postprocessing CLI — visualization and data export.

    Tecplot 360 is a professional CFD visualization and analysis tool.
    Supports Fluent, OpenFOAM, CGNS, NETCDF, and native .plt/.dat formats.

    Examples:
      tecplot load data --file case.dat
      tecplot plot contour --var Pressure --levels 20
      tecplot export image --file output.png --width 1920
    """
    global JSON_MODE
    JSON_MODE = json_output
    ctx.ensure_object(dict)
    ctx.obj["json"] = json_output
    ctx.obj["container"] = container

    if ctx.invoked_subcommand is None:
        echo(f"Tecplot harness (CLI wrapper)")
        echo(f"Container: {container}")
        try:
            tb.find_tecplot()
            echo("Tecplot: found")
        except RuntimeError as e:
            echo(f"Tecplot: not found ({tb.TECPLOT_VERSION})")
        echo("Use --help with a subcommand for details")


# ==================================================================
# load command
# ==================================================================

@cli.group("load")
def cmd_load():
    """Load data files and layouts."""
    pass


@cmd_load.command("data")
@click.option("--file", "-f", required=True, help="Data file path (.dat, .plt, .cas, .h5)")
@click.pass_context
def cmd_load_data(ctx, file: str):
    """Load a data file into Tecplot."""
    global JSON_MODE
    container = ctx.obj.get("container")

    result = tb.load_data(file, container=container)

    if JSON_MODE:
        json_out({"success": result.success, "file": file})
    else:
        if result.success:
            success(f"Data loaded: {file}")
        else:
            error(f"Failed to load data")
            echo(f"  {result.error[:200]}")


@cmd_load.command("layout")
@click.option("--file", "-f", required=True, help="Layout file path (.lay)")
@click.pass_context
def cmd_load_layout(ctx, file: str):
    """Load a Tecplot layout file."""
    global JSON_MODE
    container = ctx.obj.get("container")

    result = tb.load_layout(file, container=container)

    if JSON_MODE:
        json_out({"success": result.success, "file": file})
    else:
        if result.success:
            success(f"Layout loaded: {file}")
        else:
            error(f"Failed to load layout")
            echo(f"  {result.error[:200]}")


# ==================================================================
# plot command
# ==================================================================

@cli.group("plot")
def cmd_plot():
    """Configure plot type, contours, slices."""
    pass


@cmd_plot.command("type")
@click.option("--type", "-t", type=click.Choice(["cartesian", "polar", "XYLine", "Sketch"]),
              default="cartesian", help="Plot type")
@click.pass_context
def cmd_plot_type(ctx, type: str):
    """Set the plot type."""
    global JSON_MODE
    container = ctx.obj.get("container")

    result = tb.set_plot_type(type, container=container)

    if JSON_MODE:
        json_out({"success": result.success, "type": type})
    else:
        if result.success:
            success(f"Plot type set: {type}")
        else:
            error(f"Failed to set plot type")
            echo(f"  {result.error[:200]}")


@cmd_plot.command("contour")
@click.option("--var", "-v", required=True, help="Variable name for contour")
@click.option("--levels", type=int, default=20, help="Number of contour levels")
@click.pass_context
def cmd_plot_contour(ctx, var: str, levels: int):
    """Configure contour plot."""
    global JSON_MODE
    container = ctx.obj.get("container")

    # Generate default levels
    contour_levels = [float(i) / levels for i in range(levels)]
    result = tb.contour_levels(var, levels=contour_levels, container=container)

    if JSON_MODE:
        json_out({"success": result.success, "var": var, "n_levels": levels})
    else:
        if result.success:
            success(f"Contour configured: {var} ({levels} levels)")
        else:
            error(f"Failed to configure contour")
            echo(f"  {result.error[:200]}")


@cmd_plot.command("range")
@click.option("--var", "-v", required=True, help="Variable name")
@click.option("--min", type=float, required=True, help="Minimum value")
@click.option("--max", type=float, required=True, help="Maximum value")
@click.pass_context
def cmd_plot_range(ctx, var: str, min: float, max: float):
    """Set axis range for a variable."""
    global JSON_MODE
    container = ctx.obj.get("container")

    result = tb.set_variable_range(var, min, max, container=container)

    if JSON_MODE:
        json_out({"success": result.success, "var": var, "range": [min, max]})
    else:
        if result.success:
            success(f"Range set: {var} = [{min}, {max}]")
        else:
            error(f"Failed to set range")
            echo(f"  {result.error[:200]}")


# ==================================================================
# slice command
# ==================================================================

@cli.group("slice")
def cmd_slice():
    """Create slice planes through data."""
    pass


@cmd_slice.command("plane")
@click.option("--type", "-t", type=click.Choice(["zone slices", "multiple", "i-slice", "j-slice", "k-slice"]),
              default="zone slices", help="Slice type")
@click.pass_context
def cmd_slice_plane(ctx, type: str):
    """Create a slice plane."""
    global JSON_MODE
    container = ctx.obj.get("container")

    result = tb.create_slice_plane(type, container=container)

    if JSON_MODE:
        json_out({"success": result.success, "type": type})
    else:
        if result.success:
            success(f"Slice plane created: {type}")
        else:
            error(f"Failed to create slice")
            echo(f"  {result.error[:200]}")


@cmd_slice.command("iso")
@click.option("--var", "-v", required=True, help="Variable name")
@click.option("--value", type=float, required=True, help="Iso-value")
@click.pass_context
def cmd_slice_iso(ctx, var: str, value: float):
    """Create an iso-surface."""
    global JSON_MODE
    container = ctx.obj.get("container")

    result = tb.create_iso_surface(var, value, container=container)

    if JSON_MODE:
        json_out({"success": result.success, "var": var, "value": value})
    else:
        if result.success:
            success(f"Iso-surface created: {var} = {value}")
        else:
            error(f"Failed to create iso-surface")
            echo(f"  {result.error[:200]}")


@cmd_slice.command("stream")
@click.pass_context
def cmd_slice_stream(ctx):
    """Create streamtraces."""
    global JSON_MODE
    container = ctx.obj.get("container")

    result = tb.create_streamtrace(container=container)

    if JSON_MODE:
        json_out({"success": result.success})
    else:
        if result.success:
            success("Streamtraces created")
        else:
            error(f"Failed to create streamtraces")
            echo(f"  {result.error[:200]}")


# ==================================================================
# export command
# ==================================================================

@cli.command("export")
@click.option("--image", "-i", help="Output image path (.png, .jpg, .eps, .svg, .pdf)")
@click.option("--data", "-d", help="Output data file path")
@click.option("--width", type=int, default=1920, help="Image width (px)")
@click.option("--height", type=int, default=1080, help="Image height (px)")
@click.option("--zone", "-z", help="Zone to export (for data export)")
@click.pass_context
def cmd_export(ctx, image: Optional[str], data: Optional[str], width: int, height: int, zone: Optional[str]):
    """Export plot as image and/or data to file."""
    global JSON_MODE
    container = ctx.obj.get("container")

    results = {}

    if image:
        result = tb.export_image(image, width=width, height=height, container=container)
        results["image"] = {"success": result.success, "file": image}
        if not JSON_MODE:
            if result.success:
                success(f"Image exported: {image}")
            else:
                error(f"Failed to export image")

    if data:
        result = tb.export_data(data, zone_name=zone, container=container)
        results["data"] = {"success": result.success, "file": data}
        if not JSON_MODE:
            if result.success:
                success(f"Data exported: {data}")
            else:
                error(f"Failed to export data")

    if JSON_MODE:
        json_out(results)


# ==================================================================
# layout command
# ==================================================================

@cli.group("layout")
def cmd_layout():
    """Layout file operations."""
    pass


@cmd_layout.command("new")
@click.option("--name", "-n", required=True, help="Layout name")
@click.pass_context
def cmd_layout_new(ctx, name: str):
    """Create a new layout."""
    global JSON_MODE
    container = ctx.obj.get("container")

    result = tb.new_layout(name, container=container)

    if JSON_MODE:
        json_out({"success": result.success, "name": name})
    else:
        if result.success:
            success(f"Layout created: {name}")
        else:
            error(f"Failed to create layout")
            echo(f"  {result.error[:200]}")


@cmd_layout.command("save")
@click.option("--file", "-f", required=True, help="Layout file path (.lay)")
@click.pass_context
def cmd_layout_save(ctx, file: str):
    """Save current layout."""
    global JSON_MODE
    container = ctx.obj.get("container")

    result = tb.save_layout(file, container=container)

    if JSON_MODE:
        json_out({"success": result.success, "file": file})
    else:
        if result.success:
            success(f"Layout saved: {file}")
        else:
            error(f"Failed to save layout")
            echo(f"  {result.error[:200]}")


# ==================================================================
# macro command
# ==================================================================

@cli.group("macro")
def cmd_macro():
    """Run Tecplot macros and Python scripts."""
    pass


@cmd_macro.command("run")
@click.option("--file", "-f", required=True, help="Macro file path (.mac)")
@click.pass_context
def cmd_macro_run(ctx, file: str):
    """Execute a Tecplot macro file."""
    global JSON_MODE
    container = ctx.obj.get("container")

    result = tb.run_macro(file, container=container)

    if JSON_MODE:
        json_out({"success": result.success, "file": file})
    else:
        if result.success:
            success(f"Macro executed: {file}")
        else:
            error(f"Failed to run macro")
            echo(f"  {result.error[:200]}")


@cmd_macro.command("python")
@click.option("--file", "-f", required=True, help="Python script path (.py)")
@click.pass_context
def cmd_macro_python(ctx, file: str):
    """Execute a Tecplot Python script."""
    global JSON_MODE
    container = ctx.obj.get("container")

    result = tb.run_python_script(file, container=container)

    if JSON_MODE:
        json_out({"success": result.success, "file": file})
    else:
        if result.success:
            success(f"Python script executed: {file}")
        else:
            error(f"Failed to run script")
            echo(f"  {result.error[:200]}")


# ==================================================================
# Entry point
# ==================================================================

def main():
    cli(obj={})


if __name__ == "__main__":
    main()
