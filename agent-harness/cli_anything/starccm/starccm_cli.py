"""
starccm_cli.py - Click CLI entry point for cli-anything-starccm

Command groups:
  case            - new, info, validate
  mesh            - generate, check
  solve           - run, status
  postprocess     - extract, fields

All commands support --json for machine-readable output.
Bare 'starccm' enters REPL mode (invoke_without_command=True).

Follows HARNESS.md principles:
  - Real Star-CCM+ commands called via starccm_backend
  - State stored as JSON session files
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

import click

from .utils import starccm_backend as sb

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
    """Star-CCM+ CFD simulation CLI — case management, meshing, solving, and postprocessing.

    Star-CCM+ is a commercial CFD solver with Java API for automation.
    Requires: starccm+ binary installed in the container.

    Examples:
      starccm case new --name motorBike --template external-aero
      starccm mesh generate --project ./motorBike
      starccm solve run --project ./motorBike --nproc 16
    """
    global JSON_MODE
    JSON_MODE = json_output
    ctx.ensure_object(dict)
    ctx.obj["json"] = json_output
    ctx.obj["container"] = container

    if ctx.invoked_subcommand is None:
        echo(f"Star-CCM+ harness (Phase 1)")
        echo(f"Container: {container}")
        try:
            version = sb.detect_version()
            echo(f"Version: {version}")
        except Exception:
            echo(f"Version: {sb.STARCCM_VERSION} (detection failed)")
        echo("Use --help with a subcommand for details")


# ==================================================================
# case group
# ==================================================================

@cli.group("case")
def case_group():
    """Case management: new, info, validate."""
    pass


@case_group.command("new")
@click.option("--name", required=True, help="Case name")
@click.option("--template", "-t",
              type=click.Choice(["external-aero", "internal-flow", "multi-phase",
                                  "heat-transfer", "steady-state", "transient"]),
              default="external-aero",
              help="Simulation template")
@click.option("--dir", "directory", type=click.Path(),
              help="Parent directory (default: current directory)")
@click.option("--project", "-p", "project_dir",
              type=click.Path(exists=True),
              help="Project directory (where .starccm_session.json lives)")
@click.pass_context
def cmd_case_new(ctx, name: str, template: str, directory: Optional[str], project_dir: Optional[str]):
    """Create a new Star-CCM+ case from template.

    Example:
      starccm case new --name motorBike --template external-aero
    """
    global JSON_MODE

    base_dir = Path(directory) if directory else (Path(project_dir) if project_dir else Path.cwd())
    container = ctx.obj.get("container")

    result = sb.case_new(
        case_name=name,
        template=template,
        directory=base_dir,
        container=container,
    )

    output = {
        "status": "success" if result.success else "error",
        "command": "case_new",
        "case_name": name,
        "template": template,
        "directory": str(base_dir / name),
        "returncode": result.returncode,
        "duration_seconds": round(result.duration_seconds, 2),
        "output": result.output,
        "error": result.error[-300:] if result.error else "",
    }

    if JSON_MODE:
        json_out(output)
    else:
        if result.success:
            success(f"Case '{name}' created from template '{template}'")
            echo(f"  Directory: {base_dir / name}")
        else:
            error(f"Failed to create case '{name}'")
            if result.error:
                echo(result.error[-300:])


@case_group.command("info")
@click.option("--project", "-p", "project_dir", required=True,
              type=click.Path(exists=True),
              help="Case directory")
@click.pass_context
def cmd_case_info(ctx, project_dir: str):
    """Show case information and physics models.

    Example:
      starccm case info --project ./motorBike
    """
    global JSON_MODE

    case_dir = Path(project_dir)
    container = ctx.obj.get("container")

    try:
        info = sb.case_info(case_dir, container=container)
    except Exception as e:
        error(f"Could not read case info: {e}")
        sys.exit(1)

    if JSON_MODE:
        json_out(info)
    else:
        echo(f"Case: {info.get('case_name', 'unknown')}")
        echo(f"Directory: {info.get('case_dir', case_dir)}")
        echo(f"Template: {info.get('template', 'unknown')}")
        echo(f"Sim file exists: {info.get('sim_exists', False)}")

        if info.get("physics_models"):
            echo(f"Physics models: {', '.join(info['physics_models'][:5])}")

        if info.get("solver"):
            echo(f"Solver: {info['solver']}")

        if info.get("last_run"):
            echo(f"Last run: {info['last_run']}")

        n_runs = len(info.get("runs", []))
        if n_runs:
            echo(f"Total runs: {n_runs}")


@case_group.command("validate")
@click.option("--project", "-p", "project_dir", required=True,
              type=click.Path(exists=True),
              help="Case directory")
@click.pass_context
def cmd_case_validate(ctx, project_dir: str):
    """Validate case structure and configuration.

    Example:
      starccm case validate --project ./motorBike
    """
    global JSON_MODE

    case_dir = Path(project_dir)
    container = ctx.obj.get("container")

    result = sb.case_validate(case_dir, container=container)

    if JSON_MODE:
        json_out(result)
    else:
        if result["valid"]:
            success(f"Case '{result['case_name']}' is valid")
        else:
            error(f"Case has {len(result['issues'])} issue(s):")
            for issue in result["issues"]:
                echo(f"  - {issue}")


# ==================================================================
# mesh group
# ==================================================================

@cli.group("mesh")
def mesh_group():
    """Mesh operations: generate, check."""
    pass


@mesh_group.command("generate")
@click.option("--project", "-p", "project_dir", required=True,
              type=click.Path(exists=True),
              help="Case directory")
@click.option("--method", "-m",
              type=click.Choice(["poly", "trim", "tetrahedral"]),
              default="poly",
              help="Mesh method")
@click.option("--size", "-s",
              type=click.Choice(["automatic", "coarse", "medium", "fine"]),
              default="automatic",
              help="Base mesh size")
@click.option("--dryrun", is_flag=True,
              help="Dry run (write macro only, do not execute)")
@click.pass_context
def cmd_mesh_generate(ctx, project_dir: str, method: str, size: str, dryrun: bool):
    """Generate mesh for a case.

    Example:
      starccm mesh generate --project ./motorBike --method poly
      starccm mesh generate --project ./motorBike --method trim --size fine
    """
    global JSON_MODE

    case_dir = Path(project_dir)
    container = ctx.obj.get("container")

    if dryrun:
        # Just write and show the macro
        session_file = case_dir / ".starccm_session.json"
        if not session_file.exists():
            error("Not a valid Star-CCM+ case")
            sys.exit(1)

        session = json.loads(session_file.read_text())
        sim_file = case_dir / session.get("sim_file", f"{session['case_name']}.sim")

        macro_content = f"""// Mesh generation macro (dry run)
import starccm.*;
import java.io.*;

public class mesh_gen {{
    public static void main(String[] args) {{
        Simulation sim = Simulation.load(new File("{sim_file}"));
        MeshPipelineModule meshGen = sim.get(MeshPipelineModule.class);
        meshGen.generateMeshes();
        sim.saveState(new File("{sim_file}"));
        System.out.println("Mesh generated");
    }}
}}
"""
        macro_file = case_dir / "mesh_gen.java"
        macro_file.write_text(macro_content)

        if JSON_MODE:
            json_out({"status": "dryrun", "macro_file": str(macro_file)})
        else:
            success(f"Dry run: macro written to {macro_file}")
        return

    result = sb.mesh_generate(
        case_dir=case_dir,
        method=method,
        size=size,
        container=container,
    )

    output = {
        "status": "success" if result.success else "error",
        "command": "mesh_generate",
        "method": method,
        "size": size,
        "returncode": result.returncode,
        "duration_seconds": round(result.duration_seconds, 2),
        "error": result.error[-300:] if result.error else "",
    }

    if JSON_MODE:
        json_out(output)
    else:
        if result.success:
            success(f"Mesh generated ({method}) in {result.duration_seconds:.1f}s")
        else:
            error("Mesh generation failed")
            if result.error:
                echo(result.error[-300:])


@mesh_group.command("check")
@click.option("--project", "-p", "project_dir", required=True,
              type=click.Path(exists=True),
              help="Case directory")
@click.pass_context
def cmd_mesh_check(ctx, project_dir: str):
    """Check mesh quality metrics.

    Example:
      starccm mesh check --project ./motorBike
    """
    global JSON_MODE

    case_dir = Path(project_dir)
    container = ctx.obj.get("container")

    quality = sb.mesh_check(case_dir, container=container)

    if JSON_MODE:
        json_out(quality)
    else:
        if quality.get("success"):
            success("Mesh check completed")
            cells = quality.get("cells", 0)
            faces = quality.get("faces", 0)
            points = quality.get("points", 0)
            echo(f"  Cells:  {cells:,}")
            echo(f"  Faces:  {faces:,}")
            echo(f"  Points: {points:,}")
            if "min_quality" in quality:
                echo(f"  Min quality: {quality['min_quality']:.4f}")
            if "max_aspect_ratio" in quality:
                echo(f"  Max aspect ratio: {quality['max_aspect_ratio']:.2f}")
        else:
            error("Mesh check failed")
            if quality.get("error"):
                echo(f"  {quality['error']}")


# ==================================================================
# setup group
# ==================================================================

@cli.group("setup")
def setup_group():
    """Setup: boundary conditions, physics models, numerical schemes."""
    pass


@setup_group.command("boundary")
@click.option("--project", "-p", "project_dir", required=True,
              type=click.Path(exists=True),
              help="Case directory")
@click.option("--patch", help="Patch/boundary name (e.g., inlet, wing, outlet)")
@click.option("--type", "-t",
              type=click.Choice(["velocity-inlet", "pressure-inlet", "pressure-outlet",
                                  "outflow", "wall", "symmetry", "farfield", "fixed-pressure"]),
              help="Boundary condition type")
@click.option("--value", help="BC value (e.g., '60 0 0' for velocity, '101325' for pressure)")
@click.option("--field", default="Velocity",
              help="Field name (Velocity, Pressure, Temperature)")
@click.option("--list", "do_list", is_flag=True,
              help="List all boundaries in the case")
@click.option("--file", "-f", "yaml_file", type=click.Path(exists=True),
              help="Apply BCs from YAML config file")
@click.pass_context
def cmd_setup_boundary(ctx, project_dir: str, patch: Optional[str], type: Optional[str],
                        value: Optional[str], field: str, do_list: bool, yaml_file: Optional[str]):
    """Set or list boundary conditions.

    Examples:
      starccm setup boundary --project ./turbine --patch inlet --type velocity-inlet --value "60 0 0"
      starccm setup boundary --project ./turbine --patch outlet --type pressure-outlet --value "101325"
      starccm setup boundary --project ./turbine --list
      starccm setup boundary --project ./turbine --file boundaries.yaml
    """
    global JSON_MODE

    case_dir = Path(project_dir)
    container = ctx.obj.get("container")

    # List boundaries
    if do_list:
        result = sb.list_boundaries(case_dir, container=container)
        if JSON_MODE:
            json_out(result)
        else:
            if result.get("boundaries"):
                success(f"Boundaries ({result['count']}):")
                for name, bc_type in result["boundaries"].items():
                    echo(f"  {name}: {bc_type}")
            else:
                echo("No boundaries found (mesh may not be generated yet)")
        return

    # Apply from YAML file
    if yaml_file:
        result = sb.setup_boundary_from_file(
            case_dir=case_dir,
            yaml_file=Path(yaml_file),
            container=container,
        )
        if JSON_MODE:
            json_out(result)
        else:
            if result.get("success"):
                success("Boundary conditions applied from YAML")
                for name, info in result.get("boundaries", {}).items():
                    status = "OK" if info["success"] else f"FAIL: {info['error']}"
                    echo(f"  {name} ({info['type']}): {status}")
            else:
                error("Failed to apply boundary conditions")
                if result.get("error"):
                    echo(f"  {result['error']}")
        return

    # Single boundary setup
    if not patch or not type:
        error("Both --patch and --type are required (or use --list / --file)")
        sys.exit(1)

    result = sb.setup_boundary(
        case_dir=case_dir,
        patch=patch,
        bc_type=type,
        value=value,
        field=field,
        container=container,
    )

    if JSON_MODE:
        json_out({
            "status": "success" if result.success else "error",
            "patch": patch,
            "type": type,
            "value": value,
            "duration_seconds": round(result.duration_seconds, 2),
            "error": result.error[-300:] if result.error else "",
        })
    else:
        if result.success:
            success(f"Boundary '{patch}' set to '{type}'" + (f" @ {value}" if value else ""))
        else:
            error(f"Failed to set boundary '{patch}'")
            if result.error:
                echo(result.error[-300:])


@setup_group.command("physics")
@click.option("--project", "-p", "project_dir",
              type=click.Path(exists=True),
              help="Case directory (required for --model, --info; optional for --list)")
@click.option("--model", "-m",
              type=click.Choice(["laminar", "kEpsilon", "kOmega", "spalartAllmaras",
                                  "realizableKE", "heatTransfer"]),
              help="Physics model preset")
@click.option("--speed", type=float, help="Free-stream velocity (m/s)")
@click.option("--re", "reynolds", type=float,
              help="Reynolds number (alternative to --speed, L_ref=1m)")
@click.option("--list", "do_list", is_flag=True,
              help="List available physics model presets")
@click.option("--info", is_flag=True,
              help="Show current physics models in the case")
@click.pass_context
def cmd_setup_physics(ctx, project_dir: Optional[str], model: Optional[str], speed: Optional[float],
                        reynolds: Optional[float], do_list: bool, info: bool):
    """Set or show physics models.

    Examples:
      starccm setup physics --project ./turbine --model kEpsilon --speed 60
      starccm setup physics --project ./turbine --model spalartAllmaras --re 3e6
      starccm setup physics --list
      starccm setup physics --project ./turbine --info
    """
    global JSON_MODE

    case_dir = Path(project_dir) if project_dir else None
    container = ctx.obj.get("container")

    # List presets
    if do_list:
        output = {"presets": sb.PHYSICS_PRESETS}
        if JSON_MODE:
            json_out(output)
        else:
            echo("Available physics model presets:")
            for name, preset in sb.PHYSICS_PRESETS.items():
                echo(f"  {name}: {preset['description']}")
                echo(f"    Models: {', '.join(preset['models'])}")
        return

    # Show current info - requires project
    if info:
        if not case_dir:
            error("--project is required for --info")
            sys.exit(1)
        result = sb.get_physics_info(case_dir, container=container)
        if JSON_MODE:
            json_out(result)
        else:
            if result.get("models"):
                success("Active physics models:")
                for m in result["models"]:
                    echo(f"  {m}")
            else:
                echo("No physics models set (or .sim file not yet created)")
        return

    # Set physics - requires both project and model
    if not case_dir:
        error("--project is required")
        sys.exit(1)
    if not model:
        error("--model is required")
        sys.exit(1)

    result = sb.setup_physics(
        case_dir=case_dir,
        model=model,
        speed=speed,
        reynolds_number=reynolds,
        container=container,
    )

    if JSON_MODE:
        json_out({
            "status": "success" if result.success else "error",
            "model": model,
            "speed": speed,
            "reynolds": reynolds,
            "duration_seconds": round(result.duration_seconds, 2),
            "error": result.error[-300:] if result.error else "",
        })
    else:
        if result.success:
            speed_str = f" @ {speed} m/s" if speed else ""
            re_str = f" @ Re={reynolds}" if reynolds else ""
            success(f"Physics model set: {model}{speed_str}{re_str}")
        else:
            error(f"Failed to set physics model '{model}'")
            if result.error:
                echo(result.error[-300:])


@setup_group.command("schemes")
@click.option("--project", "-p", "project_dir", required=True,
              type=click.Path(exists=True),
              help="Case directory")
@click.option("--convection", "-c",
              type=click.Choice(["firstOrder", "secondOrder", "bounded"]),
              default="bounded",
              help="Convection scheme (default: bounded)")
@click.pass_context
def cmd_setup_schemes(ctx, project_dir: str, convection: str):
    """Set numerical schemes (convection, pressure, etc.).

    Example:
      starccm setup schemes --project ./turbine --convection secondOrder
    """
    global JSON_MODE

    case_dir = Path(project_dir)
    container = ctx.obj.get("container")

    result = sb.setup_schemes(
        case_dir=case_dir,
        convection=convection,
        container=container,
    )

    if JSON_MODE:
        json_out({
            "status": "success" if result.success else "error",
            "convection": convection,
            "duration_seconds": round(result.duration_seconds, 2),
            "error": result.error[-300:] if result.error else "",
        })
    else:
        if result.success:
            success(f"Convection scheme set: {convection}")
        else:
            error("Failed to set numerical schemes")
            if result.error:
                echo(result.error[-300:])


# ==================================================================
# solve group
# ==================================================================

@cli.group("solve")
def solve_group():
    """Solver operations: run, status."""
    pass


@solve_group.command("run")
@click.option("--project", "-p", "project_dir", required=True,
              type=click.Path(exists=True),
              help="Case directory")
@click.option("--nproc", "-n", default=4,
              help="Number of MPI partitions (default: 4)")
@click.option("--end-time", type=float,
              help="End time for transient simulation")
@click.option("--iterations", "-i", "max_iterations", type=int,
              help="Max iterations for steady-state")
@click.option("--timeout", type=int,
              help="Max runtime in seconds")
@click.option("--dryrun", is_flag=True,
              help="Dry run (write macro only)")
@click.pass_context
def cmd_solve_run(ctx, project_dir: str, nproc: int, end_time: Optional[float],
                   max_iterations: Optional[int], timeout: Optional[int], dryrun: bool):
    """Run Star-CCM+ solver.

    Example:
      starccm solve run --project ./motorBike --nproc 16 --end-time 0.1
      starccm solve run --project ./motorBike --iterations 1000
    """
    global JSON_MODE

    case_dir = Path(project_dir)
    container = ctx.obj.get("container")

    if dryrun:
        session_file = case_dir / ".starccm_session.json"
        if not session_file.exists():
            error("Not a valid Star-CCM+ case")
            sys.exit(1)

        session = json.loads(session_file.read_text())
        sim_file = case_dir / session.get("sim_file", f"{session['case_name']}.sim")

        macro_content = f"""// Solver run macro (dry run)
import starccm.*;
import java.io.*;

public class solver_run {{
    public static void main(String[] args) {{
        Simulation sim = Simulation.load(new File("{sim_file}"));
        IterationSolver solver = (IterationSolver) sim.getSolver();
        solver.loop();
        sim.saveState(new File("{sim_file}"));
        System.out.println("Solver finished");
    }}
}}
"""
        macro_file = case_dir / "solver_run.java"
        macro_file.write_text(macro_content)

        if JSON_MODE:
            json_out({"status": "dryrun", "macro_file": str(macro_file),
                      "nproc": nproc, "end_time": end_time,
                      "max_iterations": max_iterations})
        else:
            success(f"Dry run: macro written to {macro_file}")
        return

    result = sb.solve_run(
        case_dir=case_dir,
        n_partitions=nproc,
        end_time=end_time,
        max_iterations=max_iterations,
        timeout=timeout,
        container=container,
    )

    parsed = sb.parse_solver_output(result.output)

    output = {
        "status": "success" if result.success else "error",
        "command": "solve_run",
        "n_partitions": nproc,
        "end_time": end_time,
        "max_iterations": max_iterations,
        "returncode": result.returncode,
        "duration_seconds": round(result.duration_seconds, 2),
        "converged": parsed.get("converged", False),
        "iterations": parsed.get("iterations", 0),
        "final_time": parsed.get("time", 0.0),
        "error": result.error[-300:] if result.error else "",
    }

    if JSON_MODE:
        json_out(output)
    else:
        if result.success:
            success(f"Solver finished in {result.duration_seconds:.1f}s (n={nproc})")
            if parsed.get("iterations"):
                echo(f"  Iterations: {parsed['iterations']}")
            if parsed.get("time"):
                echo(f"  Final time: {parsed['time']}")
            if parsed.get("converged"):
                echo("  Convergence: ACHIEVED")
        else:
            error("Solver failed")
            if result.error:
                echo(result.error[-300:])


@solve_group.command("status")
@click.option("--project", "-p", "project_dir", required=True,
              type=click.Path(exists=True),
              help="Case directory")
@click.pass_context
def cmd_solve_status(ctx, project_dir: str):
    """Show solver status and convergence history.

    Example:
      starccm solve status --project ./motorBike
    """
    global JSON_MODE

    case_dir = Path(project_dir)
    container = ctx.obj.get("container")

    status = sb.solve_status(case_dir, container=container)

    if JSON_MODE:
        json_out(status)
    else:
        echo(f"Case: {status.get('case_name', 'unknown')}")
        echo(f"Sim file: {'exists' if status.get('sim_exists') else 'MISSING'}")

        if status.get("last_run"):
            echo(f"Last run: {status['last_run']}")

        n_runs = len(status.get("runs", []))
        if n_runs:
            echo(f"Total runs: {n_runs}")

        if status.get("time_directories"):
            echo(f"Timesteps: {status['n_timesteps']}")
            echo(f"Current time: {status['current_time']}")

        if not status.get("last_run") and not status.get("time_directories"):
            echo("No runs yet")


# ==================================================================
# postprocess group
# ==================================================================

@cli.group("postprocess")
def postprocess_group():
    """Postprocessing: force coefficients, y+, field data, reports."""
    pass


@postprocess_group.command("force")
@click.option("--project", "-p", "project_dir", required=True,
              type=click.Path(exists=True),
              help="Case directory")
@click.option("--patch", "-i", "patches", multiple=True, required=True,
              help="Patch names to extract forces from (can repeat)")
@click.option("--direction", "-d",
              type=click.Choice(["all", "x", "y", "z"]),
              default="all",
              help="Force component direction (default: all)")
@click.option("--area", type=float,
              help="Reference area for Cd, Cl (m²)")
@click.option("--length", type=float,
              help="Reference length for Cm (m)")
@click.pass_context
def cmd_postprocess_force(ctx, project_dir: str, patches: tuple, direction: str,
                            area: Optional[float], length: Optional[float]):
    """Extract force and moment coefficients.

    Example:
      starccm postprocess force --project ./turbine --patch wing --patch endplate -d all
      starccm postprocess force --project ./turbine --patch wing -d x --area 0.5
    """
    global JSON_MODE

    case_dir = Path(project_dir)
    container = ctx.obj.get("container")

    result = sb.postprocess_force(
        case_dir=case_dir,
        patches=list(patches),
        direction=direction,
        reference_area=area,
        reference_length=length,
        container=container,
    )

    if JSON_MODE:
        json_out(result)
    else:
        if result.get("coefficient") is not None:
            success(f"Force coefficient ({direction}): {result['coefficient']:.6f}")
            echo(f"  Patches: {', '.join(patches)}")
            if result.get("force_x"):
                echo(f"  Fx: {result['force_x']:.4f} N")
            if result.get("force_y"):
                echo(f"  Fy: {result['force_y']:.4f} N")
            if result.get("force_z"):
                echo(f"  Fz: {result['force_z']:.4f} N")
        else:
            error("Could not extract force coefficients")
            if result.get("error"):
                echo(f"  {result['error']}")


@postprocess_group.command("yplus")
@click.option("--project", "-p", "project_dir", required=True,
              type=click.Path(exists=True),
              help="Case directory")
@click.option("--patch", "-i", required=True,
              help="Wall patch name")
@click.pass_context
def cmd_postprocess_yplus(ctx, project_dir: str, patch: str):
    """Extract y+ statistics on a wall patch.

    Example:
      starccm postprocess yplus --project ./turbine --patch wing
    """
    global JSON_MODE

    case_dir = Path(project_dir)
    container = ctx.obj.get("container")

    result = sb.postprocess_yplus(
        case_dir=case_dir,
        patch=patch,
        container=container,
    )

    if JSON_MODE:
        json_out(result)
    else:
        if "mean" in result:
            success(f"y+ on '{patch}':")
            echo(f"  Mean:  {result['mean']:.2f}")
            echo(f"  Min:   {result.get('min', 'N/A'):.2f}")
            echo(f"  Max:   {result.get('max', 'N/A'):.2f}")
        elif result.get("error"):
            error(f"y+ extraction failed: {result['error']}")
        else:
            error("Could not extract y+ values")


@postprocess_group.command("field")
@click.option("--project", "-p", "project_dir", required=True,
              type=click.Path(exists=True),
              help="Case directory")
@click.option("--field", "-f",
              type=click.Choice(["Velocity", "Pressure", "Temperature",
                                  "Density", "Turbulent kinetic energy", "Dissipation rate"]),
              default="Velocity",
              help="Field to extract (default: Velocity)")
@click.option("--patch", help="Patch name to sample (optional)")
@click.option("--time", help="Time step to extract (default: latest)")
@click.option("--format",
              type=click.Choice(["csv", "vtk"]),
              default="csv",
              help="Output format (default: csv)")
@click.pass_context
def cmd_postprocess_field(ctx, project_dir: str, field: str, patch: Optional[str],
                           time: Optional[str], format: str):
    """Extract field data (velocity, pressure, etc.).

    Example:
      starccm postprocess field --project ./turbine --field Pressure --format csv
    """
    global JSON_MODE

    case_dir = Path(project_dir)
    container = ctx.obj.get("container")

    result = sb.postprocess_field(
        case_dir=case_dir,
        field=field,
        patch=patch,
        time=time,
        format=format,
        container=container,
    )

    if JSON_MODE:
        json_out(result)
    else:
        if result.get("success"):
            success(f"Field '{field}' extraction queued")
            if result.get("output_file"):
                echo(f"  Output: {result['output_file']}")
        else:
            error("Field extraction failed")
            if result.get("error"):
                echo(f"  {result['error']}")


@postprocess_group.command("reports")
@click.option("--project", "-p", "project_dir", required=True,
              type=click.Path(exists=True),
              help="Case directory")
@click.pass_context
def cmd_postprocess_reports(ctx, project_dir: str):
    """List all available reports in the case.

    Example:
      starccm postprocess reports --project ./turbine
    """
    global JSON_MODE

    case_dir = Path(project_dir)
    container = ctx.obj.get("container")

    result = sb.get_available_reports(case_dir, container=container)

    if JSON_MODE:
        json_out(result)
    else:
        if result.get("reports"):
            success(f"Reports ({result['count']}):")
            for name, rtype in result["reports"].items():
                echo(f"  {name} ({rtype})")
        else:
            echo("No reports found (run the case first)")


# ==================================================================
# param group (parameter sweeps)
# ==================================================================

@cli.group("param")
def param_group():
    """Parameter sweep studies."""
    pass


@param_group.command("sweep")
@click.option("--project", "-p", "project_dir", required=True,
              type=click.Path(exists=True),
              help="Case directory")
@click.option("--file", "-f", "param_file",
              type=click.Path(exists=True),
              help="Parameter definition file (JSON or YAML)")
@click.option("--aoa", "aoa_values", multiple=True, type=float,
              help="Angle of attack values (degrees) - e.g., --aoa 0 --aoa 5 --aoa 10")
@click.option("--speed", "speed_values", multiple=True, type=float,
              help="Free-stream velocity values (m/s)")
@click.option("--output", "-o", type=click.Path(),
              help="Output CSV file for results")
@click.pass_context
def cmd_param_sweep(ctx, project_dir: str, param_file: Optional[str],
                     aoa_values: tuple, speed_values: tuple, output: Optional[str]):
    """Run a parameter sweep study.

    Parameters can be specified via:
      - A parameter file (--file): JSON/YAML with named parameter ranges
      - Inline values: --aoa 0 5 10 --speed 30 60 90

    Example:
      starccm param sweep --project ./turbine --aoa 0 5 10 --speed 30 60
      starccm param sweep --project ./turbine --file params.json --output results.csv
    """
    global JSON_MODE

    case_dir = Path(project_dir)
    container = ctx.obj.get("container")

    # Build params dict from inline args
    params = {}
    if aoa_values:
        params["AOA"] = list(aoa_values)
    if speed_values:
        params["speed"] = list(speed_values)

    if not param_file and not params:
        error("Either --file or at least one parameter range (--aoa, --speed) is required")
        sys.exit(1)

    result = sb.param_sweep(
        case_dir=case_dir,
        param_file=Path(param_file) if param_file else None,
        params=params if params else None,
        container=container,
    )

    if JSON_MODE:
        json_out(result)
        return

    if result.get("success"):
        sweep_info = result.get("sweep", {})
        success(f"Sweep complete: {sweep_info.get('n_converged', 0)}/{sweep_info.get('n_runs', 0)} converged")

        # Print table
        if result.get("results"):
            echo("\nResults:")
            echo(f"{'Run':<10} {'AOA':>8} {'Speed':>8} {'Converged':>10} {'Cd':>12} {'Cl':>12}")
            echo("-" * 64)
            for r in result["results"]:
                p = r.get("params", {})
                force = r.get("force", {})
                aoa = p.get("AOA", "-")
                spd = p.get("speed", "-")
                conv = "yes" if r.get("converged") else "no"
                cd = f"{force.get('coefficient', 0):.6f}" if force.get('coefficient') is not None else "-"
                cl = f"{force.get('force_y', 0):.6f}" if force.get('force_y') is not None else "-"
                echo(f"{r['run']:<10} {str(aoa):>8} {str(spd):>8} {conv:>10} {cd:>12} {cl:>12}")

        # Write CSV if requested
        if output:
            csv = sb.extract_results_table(result, Path(output))
            success(f"CSV written to: {output}")
    else:
        error("Sweep failed")
        if result.get("error"):
            echo(f"  {result['error']}")


# ==================================================================
# Entry point
# ==================================================================

def main():
    cli(obj={})


if __name__ == "__main__":
    main()
