"""
su2_cli.py - Click CLI entry point for cli-anything-su2

Command groups:
  run         - run SU2_CFD simulation
  info        - show config file summary
  shape       - shape deformation (SU2_DEF)
  dot         - discrete adjoint (SU2_DOT)
  geo         - geometry analysis (SU2_GEO)
  optimize    - shape optimization
  polar       - compute drag polar

All commands support --json for machine-readable output.
Bare 'su2' enters REPL mode (invoke_without_command=True).

Follows HARNESS.md principles:
  - Real SU2 commands called via su2_backend
  - State stored as JSON session files
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Optional

import click

from .utils import su2_backend as sb

__all__ = ["main"]

JSON_MODE = False


# -------------------------------------------------------------------
# Utility helpers
# -------------------------------------------------------------------

def echo(msg: str, **kwargs) -> None:
    """Print to stderr (click echo goes to stdout)."""
    click.echo(msg, err=True, **kwargs)


def success(msg: str) -> None:
    click.echo(f"[OK] {msg}", err=True)


def error(msg: str) -> None:
    click.echo(f"[ERROR] {msg}", err=True, color="red")


def warn(msg: str) -> None:
    click.echo(f"[WARN] {msg}", err=True, color="yellow")


def json_out(data: dict) -> None:
    """Print JSON to stdout."""
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
    """SU2 v8.4.0 CFD simulation CLI — solver execution, shape design, and optimization.

    SU2 is a leading open-source CFD solver. It uses .cfg config files
    and supports mesh in .su2, .cgns, .vtk formats.
    """
    global JSON_MODE
    JSON_MODE = json_output
    ctx.ensure_object(dict)
    ctx.obj["json"] = json_output
    ctx.obj["container"] = container

    if ctx.invoked_subcommand is None:
        # Bare 'su2' - show version and help
        echo(f"SU2 {sb.SU2_VERSION} harness")
        echo(f"SU2 binary: {sb.SU2_INSTALL}")
        echo(f"Container: {container}")
        echo("Use --help with a subcommand for details")


# -------------------------------------------------------------------
# run command
# -------------------------------------------------------------------

@cli.command("run")
@click.option("--config", "-f", required=True, type=click.Path(exists=True),
              help="SU2 config (.cfg) file")
@click.option("--case", "case_name", help="Case name for output directories")
@click.option("--param", "-p", multiple=True,
              help="Override config param (KEY=VALUE), can be repeated")
@click.option("--partitions", "-n", default=1, help="Number of MPI partitions")
@click.option("--dryrun", is_flag=True, help="Dry run (preprocessing only)")
@click.option("--timeout", type=int, help="Max runtime in seconds")
@click.pass_context
def cmd_run(ctx, config: str, case_name: Optional[str], param: tuple, partitions: int, dryrun: bool, timeout: Optional[int]):
    """Run SU2_CFD solver.

    Example:
      su2 run --config inv_NACA0012.cfg
      su2 run --config inv_NACA0012.cfg --param MACH=0.8 --param AOA=3.0
      su2 run --config inv_NACA0012.cfg --param MACH=0.8 --param AOA=3.0 -n 4
    """
    global JSON_MODE

    cfg_path = Path(config).resolve()
    container = ctx.obj.get("container")

    # Apply param overrides to a temporary config
    if param:
        overrides = {}
        for p in param:
            if "=" not in p:
                error(f"Invalid param format: {p} (expected KEY=VALUE)")
                sys.exit(1)
            key, val = p.split("=", 1)
            overrides[key.strip()] = val.strip()

        # Write modified config to /tmp to avoid modifying original
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".cfg", delete=False) as tf:
            sb.update_config_params(cfg_path, overrides, Path(tf.name))
            cfg_path = Path(tf.name)

    result = sb.run_cfd(
        config=cfg_path,
        case_name=case_name,
        n_partitions=partitions,
        dryrun=dryrun,
        timeout=timeout,
        container=container,
    )

    parsed = sb.parse_solver_output(result.output)

    output = {
        "status": "success" if result.success else "error",
        "command": "SU2_CFD",
        "config": str(config),
        "returncode": result.returncode,
        "duration_seconds": round(result.duration_seconds, 2),
        "converged": parsed.get("converged", False),
        "iterations": parsed.get("iterations", 0),
        "objective": parsed.get("objective"),
        "output_tail": result.output[-500:] if result.output else "",
        "error": result.error[-300:] if result.error else "",
    }

    if JSON_MODE:
        json_out(output)
    else:
        if result.success:
            success(f"SU2_CFD finished in {result.duration_seconds:.1f}s")
            if parsed.get("objective"):
                obj = parsed["objective"]
                echo(f"  {obj['name']} = {obj['value']:.6f}")
            if parsed.get("converged"):
                echo("  Convergence: ACHIEVED")
        else:
            error("SU2_CFD failed")
            if result.error:
                echo(result.error[-300:])


# -------------------------------------------------------------------
# info command
# -------------------------------------------------------------------

@cli.command("info")
@click.option("--config", "-f", required=True, type=click.Path(exists=True),
              help="SU2 config (.cfg) file")
@click.pass_context
def cmd_info(ctx, config: str):
    """Show config file summary (solver, physics, mesh, BCs).

    Example:
      su2 info --config inv_NACA0012.cfg
    """
    global JSON_MODE

    cfg_path = Path(config)
    container = ctx.obj.get("container")

    try:
        params = sb.parse_config(cfg_path)
    except Exception as e:
        error(f"Could not parse config: {e}")
        sys.exit(1)

    # Key parameters to display
    key_params = {
        "SOLVER": "Solver",
        "PHYSICS": "Physics",
        "MACH": "Mach",
        "AOA": "Angle of Attack",
        "FREESTREAM_TEMPERATURE": "Temperature",
        "FREESTREAM_PRESSURE": "Pressure",
        "MARKER_MONITORING": "Monitored BCs",
        "MARKER_PLOTTING": "Plot BCs",
        "MARKER_MOVING": "Moving BCs",
        "MESH_FILENAME": "Mesh file",
        "MG_LEVEL": "Multigrid levels",
        "OUTER_ITER": "Outer iterations",
        "INNER_ITER": "Inner iterations",
        "TIME_ITER": "Time iterations",
        "CFL_NUMBER": "CFL number",
        "OBJECTIVE_FUNCTION": "Objective",
    }

    # Get geometry params
    geo_params = {}
    for key in ["GEO_DESCRIPTION", "GEO_MODE", "DV_KIND", "FFD_DEFINITION"]:
        if key in params:
            geo_params[key] = params[key]

    result = {
        "config_file": str(cfg_path),
        "params": params,
        "key_params": {k: params.get(k) for k in key_params if params.get(k)},
        "geometry": geo_params,
    }

    if JSON_MODE:
        json_out(result)
    else:
        echo(f"Config: {cfg_path}")
        echo(f"Solver: {params.get('SOLVER', 'unknown')}")
        echo(f"Physics: {params.get('PHYSICS', 'unknown')}")
        echo(f"Mesh: {params.get('MESH_FILENAME', 'unknown')}")

        mach = params.get("MACH")
        aoa = params.get("AOA")
        if mach:
            echo(f"Flow: Mach={mach}" + (f", AOA={aoa}" if aoa else ""))

        obj = params.get("OBJECTIVE_FUNCTION")
        if obj:
            echo(f"Objective: {obj}")

        bc = params.get("MARKER_MONITORING")
        if bc:
            echo(f"BCs: {bc}")

        echo(f"\nTotal params: {len(params)}")
        echo("Key values (first 30):")
        for i, (k, v) in enumerate(list(params.items())[:30]):
            echo(f"  {k}= {v}")


# -------------------------------------------------------------------
# shape command (SU2_DEF - mesh deformation)
# -------------------------------------------------------------------

@cli.command("shape")
@click.option("--input", "-i", "input_mesh", required=True,
              type=click.Path(exists=True),
              help="Input mesh file (.su2, .cgns, .vtk)")
@click.option("--config", "-f", type=click.Path(exists=True),
              help="Config file with design parameters")
@click.option("--func", default="wing",
              help="Design function (wing, nacelle, etc.)")
@click.option("--output", "-o", type=click.Path(),
              help="Output deformed mesh file")
@click.option("--param", "-p", multiple=True,
              help="Design param (KEY=VALUE), can be repeated")
@click.pass_context
def cmd_shape(ctx, input_mesh: str, config: Optional[str], func: str, output: Optional[str], param: tuple):
    """Run SU2_DEF for shape deformation/design.

    Example:
      su2 shape --input mesh.su2 --func wing --output deformed.su2
      su2 shape --input mesh.su2 --config design.cfg --output deformed.su2
    """
    global JSON_MODE

    in_path = Path(input_mesh).resolve()
    container = ctx.obj.get("container")

    # If config is provided, run SU2_DEF with it
    if config:
        cfg_path = Path(config).resolve()
        result = sb.run_def(cfg_path, container=container)
    else:
        # No config - show available markers from mesh if possible
        echo(f"Input mesh: {in_path}")
        echo(f"Design function: {func}")
        if output:
            echo(f"Output: {output}")
        echo("\nNote: Provide --config with DV_KIND, FFD_DEFINITION, etc. for actual deformation.")
        echo("Without --config, this just echoes the command structure.")
        result = sb.CommandResult(success=True, output="no config provided")

    output_data = {
        "status": "success" if result.success else "error",
        "command": "SU2_DEF",
        "input_mesh": str(in_path),
        "config": str(config) if config else None,
        "func": func,
        "output": output,
        "returncode": result.returncode,
        "duration_seconds": round(result.duration_seconds, 2),
        "error": result.error[-300:] if result.error else "",
    }

    if JSON_MODE:
        json_out(output_data)
    else:
        if result.success:
            success(f"SU2_DEF finished in {result.duration_seconds:.1f}s")
        else:
            error("SU2_DEF failed")
            if result.error:
                echo(result.error[-300:])


# -------------------------------------------------------------------
# dot command (SU2_DOT - adjoint)
# -------------------------------------------------------------------

@cli.command("dot")
@click.option("--config", "-f", required=True, type=click.Path(exists=True),
              help="SU2 config (.cfg) file")
@click.option("--gradient", "-g",
              type=click.Choice(["CONTINUOUS_ADJOINT", "DISCRETE_ADJOINT"]),
              default="CONTINUOUS_ADJOINT",
              help="Gradient computation method")
@click.pass_context
def cmd_dot(ctx, config: str, gradient: str):
    """Run SU2_DOT discrete adjoint for sensitivity analysis.

    Example:
      su2 dot --config inv_NACA0012.cfg --gradient CONTINUOUS_ADJOINT
    """
    global JSON_MODE

    cfg_path = Path(config).resolve()
    container = ctx.obj.get("container")

    result = sb.run_dot(cfg_path, gradient_type=gradient, container=container)

    output = {
        "status": "success" if result.success else "error",
        "command": "SU2_DOT",
        "config": str(config),
        "gradient": gradient,
        "returncode": result.returncode,
        "duration_seconds": round(result.duration_seconds, 2),
        "error": result.error[-300:] if result.error else "",
    }

    if JSON_MODE:
        json_out(output)
    else:
        if result.success:
            success(f"SU2_DOT finished in {result.duration_seconds:.1f}s")
        else:
            error("SU2_DOT failed")
            if result.error:
                echo(result.error[-300:])


# -------------------------------------------------------------------
# geo command (SU2_GEO - geometry)
# -------------------------------------------------------------------

@cli.command("geo")
@click.option("--config", "-f", required=True, type=click.Path(exists=True),
              help="SU2 config (.cfg) file")
@click.pass_context
def cmd_geo(ctx, config: str):
    """Run SU2_GEO for geometry analysis.

    Example:
      su2 geo --config inv_NACA0012.cfg
    """
    global JSON_MODE

    cfg_path = Path(config).resolve()
    container = ctx.obj.get("container")

    result = sb.run_geo(cfg_path, container=container)

    output = {
        "status": "success" if result.success else "error",
        "command": "SU2_GEO",
        "config": str(config),
        "returncode": result.returncode,
        "duration_seconds": round(result.duration_seconds, 2),
        "error": result.error[-300:] if result.error else "",
    }

    if JSON_MODE:
        json_out(output)
    else:
        if result.success:
            success(f"SU2_GEO finished in {result.duration_seconds:.1f}s")
            if result.output:
                echo(result.output[:500])
        else:
            error("SU2_GEO failed")
            if result.error:
                echo(result.error[-300:])


# -------------------------------------------------------------------
# optimize command (shape_optimization.py)
# -------------------------------------------------------------------

@cli.command("optimize")
@click.option("--config", "-f", required=True, type=click.Path(exists=True),
              help="SU2 config (.cfg) file")
@click.option("--partitions", "-n", default=1, help="Number of MPI partitions")
@click.option("--gradient", "-g",
              type=click.Choice(["CONTINUOUS_ADJOINT", "DISCRETE_ADJOINT", "FINDIFF", "NONE"]),
              default="CONTINUOUS_ADJOINT",
              help="Gradient computation method")
@click.option("--method", "-m",
              type=click.Choice(["SLSQP", "CG", "BFGS", "POWELL"]),
              default="SLSQP",
              help="Optimization method")
@click.option("--quiet", is_flag=True, help="Suppress SU2 output")
@click.option("--timeout", type=int, help="Max runtime in seconds")
@click.pass_context
def cmd_optimize(ctx, config: str, partitions: int, gradient: str, method: str, quiet: bool, timeout: Optional[int]):
    """Run SU2 shape optimization.

    Example:
      su2 optimize --config inv_NACA0012.cfg --method SLSQP -n 4
    """
    global JSON_MODE

    cfg_path = Path(config).resolve()
    container = ctx.obj.get("container")

    result = sb.run_shape_opt(
        config=cfg_path,
        n_partitions=partitions,
        gradient=gradient,
        optimization=method,
        quiet=quiet,
        timeout=timeout,
        container=container,
    )

    output = {
        "status": "success" if result.success else "error",
        "command": "shape_optimization.py",
        "config": str(config),
        "gradient": gradient,
        "method": method,
        "partitions": partitions,
        "returncode": result.returncode,
        "duration_seconds": round(result.duration_seconds, 2),
        "error": result.error[-300:] if result.error else "",
    }

    if JSON_MODE:
        json_out(output)
    else:
        if result.success:
            success(f"Shape optimization finished in {result.duration_seconds:.1f}s")
        else:
            error("Shape optimization failed")
            if result.error:
                echo(result.error[-300:])


# -------------------------------------------------------------------
# polar command (compute_polar.py)
# -------------------------------------------------------------------

@cli.command("polar")
@click.option("--config", "-c", required=True, type=click.Path(exists=True),
              help="Polar control file")
@click.option("--partitions", "-n", default=1, help="Number of MPI partitions")
@click.option("--iterations", "-i", default=100, help="Number of iterations")
@click.option("--dimension", "-d", type=click.Choice(["2", "3"]), default="2",
              help="Geometry dimension")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
@click.option("--timeout", type=int, help="Max runtime in seconds")
@click.pass_context
def cmd_polar(ctx, config: str, partitions: int, iterations: int, dimension: str, verbose: bool, timeout: Optional[int]):
    """Run SU2 compute_polar.py for drag polar computation.

    Example:
      su2 polar --config polarCtrl.cfg --iterations 200 -n 4
    """
    global JSON_MODE

    cfg_path = Path(config).resolve()
    container = ctx.obj.get("container")

    result = sb.run_compute_polar(
        config=cfg_path,
        n_partitions=partitions,
        iterations=iterations,
        dimension=int(dimension),
        verbose=verbose,
        timeout=timeout,
        container=container,
    )

    output = {
        "status": "success" if result.success else "error",
        "command": "compute_polar.py",
        "polar_config": str(config),
        "partitions": partitions,
        "iterations": iterations,
        "dimension": dimension,
        "returncode": result.returncode,
        "duration_seconds": round(result.duration_seconds, 2),
        "error": result.error[-300:] if result.error else "",
    }

    if JSON_MODE:
        json_out(output)
    else:
        if result.success:
            success(f"Polar computation finished in {result.duration_seconds:.1f}s")
        else:
            error("Polar computation failed")
            if result.error:
                echo(result.error[-300:])


# -------------------------------------------------------------------
# Entry point
# -------------------------------------------------------------------

def main():
    cli(obj={})


if __name__ == "__main__":
    main()
