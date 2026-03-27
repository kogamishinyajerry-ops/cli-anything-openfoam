"""
visit_cli.py - Click CLI entry point for cli-anything-visit

Command groups:
  open        - Open databases
  plot        - Add plots and configure
  export      - Save images and data
  query       - Query min/max, volume, integrals
  layout      - Window layouts
  animate     - Time slider control
  macro       - Run Python scripts

All commands support --json for machine-readable output.

Follows HARNESS.md principles:
  - Real VisIt commands via visit_backend Python API
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

import click

from .utils import visit_backend as vb

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
    """VisIt parallel visualization CLI — open, plot, query, and export CFD data.

    VisIt is an open-source visualization and analysis tool for scientific data.
    Supports Silo, VTK, NETCDF, CGNS, and many more formats.

    Examples:
      visit open --file case.silo
      visit plot pseudocolor --var Temperature
      visit export image --file output.png
    """
    global JSON_MODE
    JSON_MODE = json_output
    ctx.ensure_object(dict)
    ctx.obj["json"] = json_output
    ctx.obj["container"] = container

    if ctx.invoked_subcommand is None:
        echo(f"VisIt harness (CLI wrapper)")
        echo(f"Container: {container}")
        try:
            vb.find_visit()
            echo("VisIt: found")
        except RuntimeError as e:
            echo(f"VisIt: not found ({vb.VISIT_VERSION})")
        echo("Use --help with a subcommand for details")


# ==================================================================
# open command
# ==================================================================

@cli.group("open")
def cmd_open():
    """Open databases."""
    pass


@cmd_open.command("database")
@click.option("--file", "-f", required=True, help="Database file path (.silo, .vtk, .h5, .visit)")
@click.option("--timestep", "-t", type=int, help="Timestep/cycle to read")
@click.pass_context
def cmd_open_database(ctx, file: str, timestep: Optional[int]):
    """Open a database in VisIt."""
    global JSON_MODE
    container = ctx.obj.get("container")

    result = vb.open_database(file, timestep=timestep, container=container)

    if JSON_MODE:
        json_out({"success": result.success, "file": file, "timestep": timestep})
    else:
        if result.success:
            success(f"Database opened: {file}")
        else:
            error(f"Failed to open database")
            echo(f"  {result.error[:200]}")


# ==================================================================
# plot command
# ==================================================================

@cli.group("plot")
def cmd_plot():
    """Add plots and configure visualization."""
    pass


@cmd_plot.command("add")
@click.option("--type", "-t", type=click.Choice(["Pseudocolor", "Volume", "Mesh", "Vector", "Contour", "Slice", "Surface"]),
              default="Pseudocolor", help="Plot type")
@click.option("--var", "-v", required=True, help="Variable name to plot")
@click.pass_context
def cmd_plot_add(ctx, type: str, var: str):
    """Add a plot to the current window."""
    global JSON_MODE
    container = ctx.obj.get("container")

    result = vb.add_plot(type, var, container=container)

    if JSON_MODE:
        json_out({"success": result.success, "type": type, "var": var})
    else:
        if result.success:
            success(f"Plot added: {type} of {var}")
        else:
            error(f"Failed to add plot")
            echo(f"  {result.error[:200]}")


@cmd_plot.command("draw")
@click.pass_context
def cmd_plot_draw(ctx):
    """Draw all plots in the current window."""
    global JSON_MODE
    container = ctx.obj.get("container")

    result = vb.draw_plots(container=container)

    if JSON_MODE:
        json_out({"success": result.success})
    else:
        if result.success:
            success("Plots drawn")
        else:
            error(f"Failed to draw plots")
            echo(f"  {result.error[:200]}")


@cmd_plot.command("delete")
@click.pass_context
def cmd_plot_delete(ctx):
    """Delete all plots."""
    global JSON_MODE
    container = ctx.obj.get("container")

    result = vb.delete_all_plots(container=container)

    if JSON_MODE:
        json_out({"success": result.success})
    else:
        if result.success:
            success("All plots deleted")
        else:
            error(f"Failed to delete plots")
            echo(f"  {result.error[:200]}")


@cmd_plot.command("range")
@click.option("--var", "-v", required=True, help="Variable name")
@click.option("--min", type=float, required=True, help="Minimum value")
@click.option("--max", type=float, required=True, help="Maximum value")
@click.pass_context
def cmd_plot_range(ctx, var: str, min: float, max: float):
    """Set the color range for a plot."""
    global JSON_MODE
    container = ctx.obj.get("container")

    result = vb.set_plot_range(var, min, max, container=container)

    if JSON_MODE:
        json_out({"success": result.success, "var": var, "range": [min, max]})
    else:
        if result.success:
            success(f"Range set: {var} = [{min}, {max}]")
        else:
            error(f"Failed to set range")
            echo(f"  {result.error[:200]}")


# ==================================================================
# operator command
# ==================================================================

@cli.group("operator")
def cmd_operator():
    """Apply operators to plots."""
    pass


@cmd_operator.command("add")
@click.option("--type", "-t", type=click.Choice(["Slice", "Threshold", "Clip", "Reflect", "Smooth", "Volume"]),
              required=True, help="Operator type")
@click.pass_context
def cmd_operator_add(ctx, type: str):
    """Add an operator to selected plots."""
    global JSON_MODE
    container = ctx.obj.get("container")

    result = vb.add_operator(type, container=container)

    if JSON_MODE:
        json_out({"success": result.success, "type": type})
    else:
        if result.success:
            success(f"Operator added: {type}")
        else:
            error(f"Failed to add operator")
            echo(f"  {result.error[:200]}")


@cmd_operator.command("slice")
@click.option("--axis", "-a", type=click.Choice(["x", "y", "z"]), default="z", help="Slice axis")
@click.option("--value", type=float, default=0.0, help="Position along axis")
@click.pass_context
def cmd_operator_slice(ctx, axis: str, value: float):
    """Configure slice plane position."""
    global JSON_MODE
    container = ctx.obj.get("container")

    result = vb.set_slice_plane(axis=axis, value=value, container=container)

    if JSON_MODE:
        json_out({"success": result.success, "axis": axis, "value": value})
    else:
        if result.success:
            success(f"Slice set: {axis} = {value}")
        else:
            error(f"Failed to set slice")
            echo(f"  {result.error[:200]}")


# ==================================================================
# export command
# ==================================================================

@cli.command("export")
@click.option("--image", "-i", help="Output image path")
@click.option("--data", "-d", help="Output database directory")
@click.option("--width", type=int, default=1920, help="Image width (px)")
@click.option("--height", type=int, default=1080, help="Image height (px)")
@click.option("--format", "-f", type=click.Choice(["png", "jpg", "bmp", "eps", "svg"]), default="png",
              help="Image format")
@click.pass_context
def cmd_export(ctx, image: Optional[str], data: Optional[str], width: int, height: int, format: str):
    """Export current view as image or database."""
    global JSON_MODE
    container = ctx.obj.get("container")

    results = {}

    if image:
        result = vb.save_window(image, width=width, height=height, format=format, container=container)
        results["image"] = {"success": result.success, "file": image}
        if not JSON_MODE:
            if result.success:
                success(f"Image saved: {image}")
            else:
                error(f"Failed to save image")

    if data:
        result = vb.export_database(data, container=container)
        results["data"] = {"success": result.success, "dir": data}
        if not JSON_MODE:
            if result.success:
                success(f"Database exported: {data}")
            else:
                error(f"Failed to export database")

    if JSON_MODE:
        json_out(results)


# ==================================================================
# query command
# ==================================================================

@cli.group("query")
def cmd_query():
    """Query data values."""
    pass


@cmd_query.command("minmax")
@click.option("--var", "-v", required=True, help="Variable name")
@click.pass_context
def cmd_query_minmax(ctx, var: str):
    """Query min/max values of a variable."""
    global JSON_MODE
    container = ctx.obj.get("container")

    data = vb.query_minmax(var, container=container)

    if JSON_MODE:
        json_out(data)
    else:
        if data.get("values"):
            success(f"Min/Max query: {var}")
            for v in data["values"]:
                echo(f"  {v['name']}: {v['value']}")
        else:
            error(f"Failed to query min/max")
            echo(f"  {data.get('error', '')[:200]}")


@cmd_query.command("volume")
@click.pass_context
def cmd_query_volume(ctx):
    """Query volume of selected region."""
    global JSON_MODE
    container = ctx.obj.get("container")

    data = vb.query_volume(container=container)

    if JSON_MODE:
        json_out(data)
    else:
        if data.get("values"):
            success("Volume query")
            for v in data["values"]:
                echo(f"  {v['name']}: {v['value']}")
        else:
            error(f"Failed to query volume")
            echo(f"  {data.get('error', '')[:200]}")


@cmd_query.command("integral")
@click.option("--var", "-v", required=True, help="Variable name")
@click.pass_context
def cmd_query_integral(ctx, var: str):
    """Compute integral of a variable."""
    global JSON_MODE
    container = ctx.obj.get("container")

    data = vb.query_integral(var, container=container)

    if JSON_MODE:
        json_out(data)
    else:
        if data.get("values"):
            success(f"Integral query: {var}")
            for v in data["values"]:
                echo(f"  {v['name']}: {v['value']}")
        else:
            error(f"Failed to compute integral")
            echo(f"  {data.get('error', '')[:200]}")


# ==================================================================
# layout command
# ==================================================================

@cli.group("layout")
def cmd_layout():
    """Configure window layouts."""
    pass


@cmd_layout.command("set")
@click.option("--layout", "-l", type=click.Choice(["1", "2", "3", "4"]), default="1",
              help="Layout: 1=1x1, 2=2x2, 3=3x3, 4=4x4")
@click.pass_context
def cmd_layout_set(ctx, layout: str):
    """Set the window layout."""
    global JSON_MODE
    container = ctx.obj.get("container")

    result = vb.set_window_layout(int(layout), container=container)

    if JSON_MODE:
        json_out({"success": result.success, "layout": layout})
    else:
        if result.success:
            success(f"Layout set: {layout}x{layout}")
        else:
            error(f"Failed to set layout")
            echo(f"  {result.error[:200]}")


# ==================================================================
# animate command
# ==================================================================

@cli.group("animate")
def cmd_animate():
    """Control time slider and animation."""
    pass


@cmd_animate.command(" timestep")
@click.option("--index", "-i", type=int, required=True, help="Timestep index")
@click.pass_context
def cmd_animate_timestep(ctx, index: int):
    """Set the current time slider to a timestep."""
    global JSON_MODE
    container = ctx.obj.get("container")

    result = vb.set_time_slider(index, container=container)

    if JSON_MODE:
        json_out({"success": result.success, "timestep": index})
    else:
        if result.success:
            success(f"Time slider set to: {index}")
        else:
            error(f"Failed to set timestep")
            echo(f"  {result.error[:200]}")


# ==================================================================
# annotation command
# ==================================================================

@cli.group("annotate")
def cmd_annotate():
    """Configure plot annotations."""
    pass


@cmd_annotate.command("title")
@click.option("--text", "-t", required=True, help="Title text")
@click.pass_context
def cmd_annotate_title(ctx, text: str):
    """Set the plot title."""
    global JSON_MODE
    container = ctx.obj.get("container")

    result = vb.set_title(text, container=container)

    if JSON_MODE:
        json_out({"success": result.success, "title": text})
    else:
        if result.success:
            success(f"Title set: {text}")
        else:
            error(f"Failed to set title")
            echo(f"  {result.error[:200]}")


@cmd_annotate.command("hide")
@click.pass_context
def cmd_annotate_hide(ctx):
    """Hide all annotations."""
    global JSON_MODE
    container = ctx.obj.get("container")

    result = vb.hide_annotation(container=container)

    if JSON_MODE:
        json_out({"success": result.success})
    else:
        if result.success:
            success("Annotations hidden")
        else:
            error(f"Failed to hide annotations")
            echo(f"  {result.error[:200]}")


# ==================================================================
# macro command
# ==================================================================

@cli.group("macro")
def cmd_macro():
    """Run VisIt Python scripts."""
    pass


@cmd_macro.command("run")
@click.option("--file", "-f", required=True, help="Python script path (.py)")
@click.pass_context
def cmd_macro_run(ctx, file: str):
    """Execute a VisIt Python script."""
    global JSON_MODE
    container = ctx.obj.get("container")

    result = vb.run_script(file, container=container)

    if JSON_MODE:
        json_out({"success": result.success, "file": file})
    else:
        if result.success:
            success(f"Script executed: {file}")
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
