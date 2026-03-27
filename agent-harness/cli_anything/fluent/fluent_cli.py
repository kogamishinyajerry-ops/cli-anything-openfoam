"""
fluent_cli.py - Click CLI entry point for cli-anything-fluent

Command groups:
  case       - Case file operations (new/open/save)
  mesh       - Mesh operations (read)
  setup      - Solver and model setup
  solve      - Solution initialization and iteration
  report     - Generate reports and export results

All commands support --json for machine-readable output.
Bare 'fluent' enters REPL mode.

Follows HARNESS.md principles:
  - Real Fluent TUI commands via fluent_backend
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

import click

from .utils import fluent_backend as fb

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
    """ANSYS Fluent aerodynamic/CFD analysis CLI — case setup, solve, and postprocess.

    Fluent is a general-purpose CFD solver with pressure-based and density-based
    solvers. Supports steady/unsteady, compressible/incompressible flows.

    Examples:
      fluent case new --name mycase.cas --dim 3
      fluent mesh read --file mesh.msh
      fluent solve iterate --n 500
    """
    global JSON_MODE
    JSON_MODE = json_output
    ctx.ensure_object(dict)
    ctx.obj["json"] = json_output
    ctx.obj["container"] = container

    if ctx.invoked_subcommand is None:
        echo(f"Fluent harness (CLI wrapper)")
        echo(f"Container: {container}")
        try:
            fb.find_fluent()
            echo("Fluent: found")
        except RuntimeError as e:
            echo(f"Fluent: not found ({fb.FLUENT_VERSION})")
        echo("Use --help with a subcommand for details")


# ==================================================================
# case command
# ==================================================================

@cli.group("case")
def cmd_case():
    """Case file operations."""
    pass


@cmd_case.command("new")
@click.option("--name", "-n", required=True, help="Case file name (.cas)")
@click.option("--dim", "-d", type=int, default=3, help="Dimension: 2 or 3 (default: 3)")
@click.pass_context
def cmd_case_new(ctx, name: str, dim: int):
    """Create a new Fluent case."""
    global JSON_MODE
    container = ctx.obj.get("container")

    result = fb.case_new(name, dimension=dim, container=container)

    if JSON_MODE:
        json_out({"success": result.success, "case": name, "dimension": dim})
    else:
        if result.success:
            success(f"Case created: {name}")
        else:
            error(f"Failed to create case")
            echo(f"  {result.error[:200]}")


@cmd_case.command("open")
@click.option("--file", "-f", required=True, help="Case file path (.cas/.cas.gz)")
@click.pass_context
def cmd_case_open(ctx, file: str):
    """Open an existing Fluent case file."""
    global JSON_MODE
    container = ctx.obj.get("container")

    result = fb.case_open(file, container=container)

    if JSON_MODE:
        json_out({"success": result.success, "file": file})
    else:
        if result.success:
            success(f"Case opened: {file}")
        else:
            error(f"Failed to open case")
            echo(f"  {result.error[:200]}")


@cmd_case.command("save")
@click.option("--file", "-f", help="Save as path (optional)")
@click.pass_context
def cmd_case_save(ctx, file: Optional[str]):
    """Save the current Fluent case."""
    global JSON_MODE
    container = ctx.obj.get("container")

    result = fb.case_save(case_file=file, container=container)

    if JSON_MODE:
        json_out({"success": result.success, "file": file or "(current)"})
    else:
        if result.success:
            success(f"Case saved: {file or '(current)'}")
        else:
            error(f"Failed to save case")
            echo(f"  {result.error[:200]}")


# ==================================================================
# mesh command
# ==================================================================

@cli.command("mesh")
@click.option("--file", "-f", required=True, help="Mesh file path (.msh)")
@click.pass_context
def cmd_mesh(ctx, file: str):
    """Read a mesh file into Fluent."""
    global JSON_MODE
    container = ctx.obj.get("container")

    result = fb.mesh_read(file, container=container)

    if JSON_MODE:
        json_out({"success": result.success, "mesh_file": file})
    else:
        if result.success:
            success(f"Mesh read: {file}")
        else:
            error(f"Failed to read mesh")
            echo(f"  {result.error[:200]}")


# ==================================================================
# setup command
# ==================================================================

@cli.group("setup")
def cmd_setup():
    """Solver and model setup."""
    pass


@cmd_setup.command("solver")
@click.option("--type", "-t", type=click.Choice(["pressure-based", "density-based"]),
              default="pressure-based", help="Solver type")
@click.pass_context
def cmd_setup_solver(ctx, type: str):
    """Set the solver type."""
    global JSON_MODE
    container = ctx.obj.get("container")

    result = fb.setup_solver(solver_type=type, container=container)

    if JSON_MODE:
        json_out({"success": result.success, "solver": type})
    else:
        if result.success:
            success(f"Solver set: {type}")
        else:
            error(f"Failed to set solver")
            echo(f"  {result.error[:200]}")


@cmd_setup.command("models")
@click.option("--energy/--no-energy", default=False, help="Enable energy equation")
@click.option("--viscous", type=click.Choice(["k-epsilon", "k-omega", "SST", "laminar"]),
              default="k-epsilon", help="Viscous model")
@click.pass_context
def cmd_setup_models(ctx, energy: bool, viscous: str):
    """Configure physical models."""
    global JSON_MODE
    container = ctx.obj.get("container")

    result = fb.setup_models(energy=energy, viscous=viscous, container=container)

    if JSON_MODE:
        json_out({"success": result.success, "energy": energy, "viscous": viscous})
    else:
        if result.success:
            success(f"Models configured")
            echo(f"  Energy: {'on' if energy else 'off'}")
            echo(f"  Viscous: {viscous}")
        else:
            error(f"Failed to configure models")
            echo(f"  {result.error[:200]}")


@cmd_setup.command("materials")
@click.option("--fluid", default="air", help="Fluid material")
@click.pass_context
def cmd_setup_materials(ctx, fluid: str):
    """Set fluid material properties."""
    global JSON_MODE
    container = ctx.obj.get("container")

    result = fb.setup_materials(fluid=fluid, container=container)

    if JSON_MODE:
        json_out({"success": result.success, "fluid": fluid})
    else:
        if result.success:
            success(f"Material set: {fluid}")
        else:
            error(f"Failed to set material")
            echo(f"  {result.error[:200]}")


@cmd_setup.command("bc")
@click.option("--zone", "-z", required=True, help="Boundary zone name")
@click.option("--type", "-t", type=click.Choice(["velocity-inlet", "pressure-outlet", "wall", "symmetry"]),
              required=True, help="Boundary condition type")
@click.option("--velocity", type=float, help="Velocity magnitude (m/s)")
@click.option("--temperature", type=float, help="Temperature (K)")
@click.option("--pressure", type=float, help="Pressure (Pa)")
@click.pass_context
def cmd_setup_bc(ctx, zone: str, type: str, velocity: Optional[float], temperature: Optional[float], pressure: Optional[float]):
    """Set boundary condition for a zone."""
    global JSON_MODE
    container = ctx.obj.get("container")

    params = {}
    if velocity is not None:
        params["velocity"] = velocity
    if temperature is not None:
        params["temperature"] = temperature
    if pressure is not None:
        params["pressure"] = pressure

    result = fb.bc_set(zone, type, params=params, container=container)

    if JSON_MODE:
        json_out({"success": result.success, "zone": zone, "type": type, "params": params})
    else:
        if result.success:
            success(f"BC set: {zone} = {type}")
        else:
            error(f"Failed to set BC")
            echo(f"  {result.error[:200]}")


# ==================================================================
# solve command
# ==================================================================

@cli.group("solve")
def cmd_solve():
    """Solution initialization and iteration."""
    pass


@cmd_solve.command("init")
@click.pass_context
def cmd_solve_init(ctx):
    """Initialize the solution."""
    global JSON_MODE
    container = ctx.obj.get("container")

    result = fb.solve_init(container=container)

    if JSON_MODE:
        json_out({"success": result.success})
    else:
        if result.success:
            success("Solution initialized")
        else:
            error(f"Failed to initialize")
            echo(f"  {result.error[:200]}")


@cmd_solve.command("iterate")
@click.option("--n", "-n", "n_iter", type=int, required=True, help="Number of iterations")
@click.pass_context
def cmd_solve_iterate(ctx, n_iter: int):
    """Run solution iterations."""
    global JSON_MODE
    container = ctx.obj.get("container")

    result = fb.solve_iterate(n_iter=n_iter, container=container)

    if JSON_MODE:
        json_out({
            "success": result.success,
            "n_iter": n_iter,
            "output": result.output[-500:],
        })
    else:
        if result.success:
            success(f"Iteration complete: {n_iter} steps")
        else:
            error(f"Iteration failed")
            echo(f"  {result.error[:200]}")


@cmd_solve.command("monitors")
@click.option("--residual/--no-residual", default=True, help="Enable residual monitoring")
@click.option("--plot/--no-plot", default=True, help="Plot residuals during solve")
@click.pass_context
def cmd_solve_monitors(ctx, residual: bool, plot: bool):
    """Configure solution monitors."""
    global JSON_MODE
    container = ctx.obj.get("container")

    result = fb.solve_monitors(residual_enable=residual, residual_plot=plot, container=container)

    if JSON_MODE:
        json_out({"success": result.success, "residual": residual, "plot": plot})
    else:
        if result.success:
            success("Monitors configured")
        else:
            error(f"Failed to configure monitors")
            echo(f"  {result.error[:200]}")


# ==================================================================
# report command
# ==================================================================

@cli.command("report")
@click.option("--type", "-t", type=click.Choice(["flux", "surface"]), default="flux",
              help="Report type")
@click.option("--field", "-f", default="velocity-magnitude",
              help="Field to report (velocity-magnitude, temperature, pressure)")
@click.option("--surface", "-s", help="Surface name for report")
@click.pass_context
def cmd_report(ctx, type: str, field: str, surface: Optional[str]):
    """Generate a Fluent report."""
    global JSON_MODE
    container = ctx.obj.get("container")

    data = fb.report(report_type=type, field=field, surface=surface, container=container)

    if JSON_MODE:
        json_out(data)
    else:
        if data.get("values"):
            success(f"Report generated: {field}")
            for v in data["values"]:
                echo(f"  {v['name']}: {v['value']:.6f}")
        else:
            error(f"Failed to generate report")
            echo(f"  {data.get('error', '')[:200]}")


@cli.command("export")
@click.option("--file", "-f", required=True, help="Output file path")
@click.option("--surface", "-s", help="Surface to export")
@click.pass_context
def cmd_export(ctx, file: str, surface: Optional[str]):
    """Export solution data."""
    global JSON_MODE
    container = ctx.obj.get("container")

    result = fb.export_results(file_path=file, surface=surface, container=container)

    if JSON_MODE:
        json_out({"success": result.success, "file": file})
    else:
        if result.success:
            success(f"Exported: {file}")
        else:
            error(f"Export failed")
            echo(f"  {result.error[:200]}")


# ==================================================================
# Entry point
# ==================================================================

def main():
    cli(obj={})


if __name__ == "__main__":
    main()
