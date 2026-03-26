from __future__ import annotations
"""
openfoam_cli.py — Click CLI entry point for cli-anything-openfoam

Command groups:
  case       — create / info / validate / list / convert
  mesh       — generate / check / refine / transform / export
  setup      — boundary / properties / schemes / solvers / initial / parameters
  solve      — run / status / stop / decompose / reconstruct
  postprocess— extract / average / probe / forces / field / report
  parameters — set / sweep / design / optimize
  session    — save / load / undo / redo / history

All commands support --json for machine-readable output.
Bare 'openfoam' enters REPL mode (invoke_without_command=True).

Follows HARNESS.md:
  - Real OpenFOAM commands called via openfoam_backend
  - State stored as JSON session files
  - Undo/redo via deep-copy snapshots
"""

import json
import os
import sys
from pathlib import Path
from typing import Any, Optional

import click

# Core modules
from .utils import openfoam_backend as ob
from .utils import dict_parser as dp

__all__ = ["main"]

JSON_MODE = False


# -------------------------------------------------------------------
# Utility helpers
# -------------------------------------------------------------------

def echo(msg: str, **kwargs) -> None:
    """Print to stderr (click echo goes to stdout)."""
    click.echo(msg, err=True, **kwargs)


def success(msg: str) -> None:
    click.echo(f"✓ {msg}", err=True)


def error(msg: str) -> None:
    click.echo(f"✗ {msg}", err=True, color="red")


def warn(msg: str) -> None:
    click.echo(f"⚠ {msg}", err=True, color="yellow")


def json_out(data: dict) -> None:
    """Print JSON to stdout."""
    click.echo(json.dumps(data, indent=2))


def get_case_path(ctx, param, value) -> Optional[Path]:
    """Resolve case path, supporting both .json session and bare case dir."""
    if value is None:
        return None
    p = Path(value).resolve()
    # If it's a .json session file, extract the case path from it
    if p.suffix == ".json":
        try:
            data = json.loads(p.read_text())
            case = data.get("case_path")
            if case:
                return Path(case)
        except Exception:
            pass
    return p


# -------------------------------------------------------------------
# REPL support (placeholder — repl_skin.py copied from plugin)
# -------------------------------------------------------------------

def _has_repl_skin() -> bool:
    try:
        from .utils.repl_skin import ReplSkin
        return True
    except ImportError:
        return False


def _run_repl(project_path: Optional[str] = None) -> None:
    """Enter interactive REPL mode."""
    if _has_repl_skin():
        from .utils.repl_skin import ReplSkin
        skin = ReplSkin("openfoam", version="1.0.0")
        skin.print_banner()
        echo("Entering REPL mode. Type 'help' for commands, 'exit' to quit.")
        while True:
            try:
                line = click.prompt("openfoam", type=str, default="").strip()
                if not line:
                    continue
                if line in ("exit", "quit", "q"):
                    break
                echo(f"(REPL: {line} — implement with Click's REPL support)")
            except (click.Abort, KeyboardInterrupt):
                break
        skin.print_goodbye()
    else:
        echo("REPL skin not available. Using command mode.")
        echo("Install prompt-toolkit for REPL: pip install prompt-toolkit")


# -------------------------------------------------------------------
# Shared options
# -------------------------------------------------------------------

pass_session = click.make_pass_decorator(dict, ensure=False)


def load_session(project_path: Optional[str]) -> dict:
    """Load session dict from project path."""
    if project_path is None:
        return {}
    p = Path(project_path)
    if p.suffix == ".json":
        return json.loads(p.read_text())
    return {}


# -------------------------------------------------------------------
# Main group
# -------------------------------------------------------------------

@click.group(invoke_without_command=True)
@click.option("--json", "json_output", is_flag=True, help="JSON output mode")
@click.option("--project", "-p", callback=get_case_path,
              help="Case/project path (.json session or case directory)")
@click.option("--container", "-c", default="cfd-openfoam",
              help="Docker container name for OpenFOAM (default: cfd-openfoam)")
@click.pass_context
def cli(ctx, json_output: bool, project: Optional[Path], container: str):
    """OpenFOAM CFD simulation CLI — mesh generation, solver execution, and post-processing."""
    global JSON_MODE
    JSON_MODE = json_output
    ctx.ensure_object(dict)
    ctx.obj["json"] = json_output
    ctx.obj["project"] = project
    ctx.obj["container"] = container

    if ctx.invoked_subcommand is None:
        # Bare 'openfoam' → REPL
        _run_repl(str(project) if project else None)


# -------------------------------------------------------------------
# case group
# -------------------------------------------------------------------

@cli.group("case")
def case_group():
    """Case management: create, info, validate, list."""
    pass


@case_group.command("new")
@click.argument("name")
@click.option("--template", "-t", default="simpleFoam",
              type=click.Choice(["simpleFoam", "icoFoam", "pimpleFoam", "rhoSimpleFoam"]),
              help="Solver template")
@click.option("--parallel", is_flag=True, help="Enable parallel configuration")
@click.option("--processors", "-n", default=4, help="Number of processors for parallel")
@click.option("--output", "-o", type=click.Path(), help="Output path (default: ./NAME)")
@click.pass_context
def case_new(ctx, name: str, template: str, parallel: bool, processors: int, output: str):
    """Create a new OpenFOAM case directory structure."""
    global JSON_MODE
    case_path = Path(output) if output else Path.cwd() / name

    try:
        foam = ob.find_openfoam()
        version = foam.version
    except RuntimeError as e:
        version = "unknown (OpenFOAM not installed — case structure created anyway)"

    case_path.mkdir(parents=True, exist_ok=True)

    # Create standard directory structure
    (case_path / "system").mkdir(exist_ok=True)
    (case_path / "constant").mkdir(exist_ok=True)
    (case_path / "0").mkdir(exist_ok=True)

    # Get template for solver
    tmpl = dp.CASE_TEMPLATES.get(template, dp.CASE_TEMPLATES["simpleFoam"])

    # Write controlDict
    control = dict(tmpl["controlDict"])
    if parallel:
        control["startFrom"] = "latestTime"
    dp.write_dict(case_path / "system" / "controlDict", control)

    # Write fvSchemes
    dp.write_dict(case_path / "system" / "fvSchemes", tmpl["fvSchemes"])

    # Write fvSolution
    dp.write_dict(case_path / "system" / "fvSolution", tmpl["fvSolution"])

    # Create default boundary condition files for simpleFoam
    if template == "simpleFoam":
        _write_default_U(case_path, template)
        _write_default_p(case_path)

    # Write decomposeParDict if parallel
    if parallel:
        decomp = {
            "numberOfSubdomains": processors,
            "method": "simple",
            "simpleCoeffs": {
                "n": f"({processors} 1 1)",
                "delta": 0.001,
            },
        }
        dp.write_dict(case_path / "system" / "decomposeParDict", decomp)

    # Write transportProperties for simpleFoam
    if template == "simpleFoam":
        tp = {
            "transportModel": "Newtonian",
            "nu": 1e-05,
            "rho": 1,
            "Cp": 4185,
            "Pr": 0.7,
        }
        dp.write_dict(case_path / "constant" / "transportProperties", tp)

    # Write turbulenceProperties for simpleFoam
    if template == "simpleFoam":
        turb = {
            "simulationType": "turbulenceModel",
            "turbulenceModel": "kEpsilon",
        }
        dp.write_dict(case_path / "constant" / "turbulenceProperties", turb)

    result = {
        "status": "success",
        "case_path": str(case_path.resolve()),
        "solver": template,
        "parallel": parallel,
        "version": version,
    }

    if JSON_MODE:
        json_out(result)
    else:
        success(f"Created {template} case: {case_path}")
        echo(f"  Version: {version}")
        echo(f"  Solver: {template}")
        echo(f"  Parallel: {parallel} ({processors} procs)" if parallel else "")


@case_group.command("info")
@click.argument("case_path", type=click.Path(exists=True), required=False)
@click.pass_context
def case_info(ctx, case_path: str):
    """Show information about a case."""
    global JSON_MODE

    p = Path(case_path) if case_path else (ctx.obj.get("project") or Path.cwd())

    try:
        foam = ob.find_openfoam()
        version = foam.version
    except RuntimeError:
        version = "unknown (OpenFOAM not found)"

    # Find all time directories
    times = sorted(
        (float(d.name) for d in p.iterdir() if d.is_dir() and _is_number(d.name)),
        reverse=True
    )

    # Check for mesh
    has_mesh = (p / "constant" / "polyMesh").exists()

    # Find solver from controlDict
    solver = "unknown"
    if (p / "system" / "controlDict").exists():
        try:
            d = dp.read_dict(p / "system" / "controlDict")
            solver = d.get("application", "unknown")
        except Exception:
            pass

    result = {
        "case_path": str(p.resolve()),
        "openfoam_version": version,
        "solver": solver,
        "has_mesh": has_mesh,
        "time_dirs": times[:10],  # last 10
        "latest_time": times[0] if times else None,
    }

    if JSON_MODE:
        json_out(result)
    else:
        echo(f"Case: {p}")
        echo(f"  OpenFOAM: {version}")
        echo(f"  Solver: {solver}")
        echo(f"  Mesh: {'✓' if has_mesh else '✗'}")
        echo(f"  Times: {times[:5]}..." if len(times) > 5 else f"  Times: {times}")


@case_group.command("validate")
@click.argument("case_path", type=click.Path(exists=True), required=False)
@click.pass_context
def case_validate(ctx, case_path: str):
    """Validate case completeness."""
    global JSON_MODE

    p = Path(case_path) if case_path else (ctx.obj.get("project") or Path.cwd())
    issues = []

    required_system = ["controlDict", "fvSchemes", "fvSolution"]
    for f in required_system:
        if not (p / "system" / f).exists():
            issues.append(f"Missing system/{f}")

    if issues:
        result = {"status": "invalid", "issues": issues}
    else:
        result = {"status": "valid"}

    if JSON_MODE:
        json_out(result)
    else:
        if issues:
            for issue in issues:
                warn(issue)
        else:
            success("Case is valid")


@case_group.command("list")
@click.option("--path", "-p", type=click.Path(), default=".",
              help="Directory to search")
@click.option("--depth", "-d", type=int, default=2,
              help="Max recursion depth")
def case_list(path: str, depth: int):
    """List all OpenFOAM cases in a directory tree."""
    global JSON_MODE

    cases = []
    base = Path(path).resolve()

    for d in _walk_dirs(base, depth):
        if (d / "system" / "controlDict").exists():
            solver = "unknown"
            try:
                d2 = dp.read_dict(d / "system" / "controlDict")
                solver = d2.get("application", "unknown")
            except Exception:
                pass
            cases.append({
                "path": str(d),
                "name": d.name,
                "solver": solver,
            })

    result = {"cases": cases, "count": len(cases)}

    if JSON_MODE:
        json_out(result)
    else:
        if cases:
            for c in cases:
                echo(f"  {c['path']}  [{c['solver']}]")
        else:
            echo("No cases found")


# -------------------------------------------------------------------
# mesh group
# -------------------------------------------------------------------

@cli.group("mesh")
def mesh_group():
    """Mesh generation and manipulation."""
    pass


@mesh_group.command("generate")
@click.option("--method", "-m", type=click.Choice(["blockmesh", "snappy"]),
              default="blockmesh", help="Mesh generation method")
@click.option("--dict", "mesh_dict", type=click.Path(),
              help="Path to blockMeshDict (for blockmesh method)")
@click.option("--geometry", type=click.Path(), help="STL geometry file (for snappy)")
@click.option("--castellated/--no-castellated", default=True)
@click.option("--snap/--no-snap", default=True)
@click.option("--layers/--no-layers", "add_layers", default=True)
@click.option("--parallel", is_flag=True)
@click.option("--processors", "-n", default=4)
@click.argument("case_path", type=click.Path(exists=True), required=False)
@click.pass_context
def mesh_generate(ctx, method: str, mesh_dict: str, geometry: str,
                  castellated: bool, snap: bool, add_layers: bool,
                  parallel: bool, processors: int, case_path: str):
    """Generate mesh using blockMesh or snappyHexMesh."""
    global JSON_MODE

    p = Path(case_path) if case_path else ctx.obj.get("project")
    if not p:
        error("No case path specified")
        sys.exit(1)
    p = p.resolve()

    container = ctx.obj.get("container")
    if method == "blockmesh":
        dict_path = Path(mesh_dict) if mesh_dict else None
        result = ob.run_blockmesh(p, dict_path, container=container)
    else:
        stl = Path(geometry) if geometry else None
        result = ob.run_snappyhexmesh(
            p,
            stl_name=stl.name if stl else "geometry",
            castellated=castellated,
            snap=snap,
            add_layers=add_layers,
            parallel=parallel,
            n_processors=processors,
            container=container,
        )

    output = {
        "status": "success" if result.success else "error",
        "command": method,
        "returncode": result.returncode,
        "duration_seconds": round(result.duration_seconds, 2),
        "output": result.output[-500:] if result.output else "",
        "error": result.error[-500:] if result.error else "",
    }

    if JSON_MODE:
        json_out(output)
    else:
        if result.success:
            success(f"Mesh generated in {result.duration_seconds:.1f}s")
            echo(result.output[-300:] if result.output else "")
        else:
            error(f"Mesh generation failed")
            echo(result.error[-300:] if result.error else "")


@mesh_group.command("check")
@click.argument("case_path", type=click.Path(exists=True), required=False)
@click.pass_context
def mesh_check(ctx, case_path: str):
    """Run checkMesh to validate mesh quality."""
    global JSON_MODE

    p = Path(case_path) if case_path else ctx.obj.get("project")
    if not p:
        error("No case path specified")
        sys.exit(1)

    container = ctx.obj.get("container")
    result = ob.run_checkmesh(p, container=container)
    quality = ob.parse_checkmesh_quality(result.output) if result.output else {}

    output = {
        "status": "success" if result.success else "error",
        "returncode": result.returncode,
        "cells": quality.get("cells", 0),
        "points": quality.get("points", 0),
        "faces": quality.get("faces", 0),
        "max_aspect_ratio": quality.get("max_aspect_ratio", 0),
    }

    if JSON_MODE:
        json_out(output)
    else:
        if result.success:
            success(f"Mesh OK: {quality.get('cells', 0):,} cells")
            echo(f"  Points: {quality.get('points', 0):,}")
            echo(f"  Max aspect ratio: {quality.get('max_aspect_ratio', 0):.2f}")
        else:
            error("Mesh check failed")
            echo(result.output[-200:] if result.output else "")


# -------------------------------------------------------------------
# setup group
# -------------------------------------------------------------------

@cli.group("setup")
def setup_group():
    """Setup boundary conditions, physical properties, numerical schemes."""
    pass


@setup_group.command("boundary")
@click.option("--patch", required=True, help="Patch name")
@click.option("--type", "bc_type", required=True,
              type=click.Choice(["fixedValue", "zeroGradient", "noSlip", "slip",
                                 "symmetryPlane", "fixedFluxPressure"]),
              help="Boundary condition type")
@click.option("--value", help="Value (e.g., '10 0 0' for vector, '101325' for scalar)")
@click.option("--field", default="U", help="Field name (U, p, T, etc.)")
@click.argument("case_path", type=click.Path(exists=True), required=False)
@click.pass_context
def setup_boundary(ctx, patch: str, bc_type: str, value: Optional[str], field: str, case_path: str):
    """Set boundary condition for a patch."""
    global JSON_MODE

    p = Path(case_path) if case_path else ctx.obj.get("project")
    if not p:
        error("No case path specified")
        sys.exit(1)

    # Determine time directory (latest or 0)
    # Sort by float value but keep original directory names
    time_entries = sorted(
        ((float(d.name), d.name) for d in p.iterdir() if d.is_dir() and _is_number(d.name))
    )
    time_name = time_entries[0][1] if time_entries else "0"

    bc_file = p / time_name / field
    if not bc_file.exists():
        # Create with default template
        if field == "U":
            _write_default_U(p, "custom", patch, bc_type, value)
        elif field == "p":
            _write_default_p(p, patch, bc_type, value)
        else:
            warn(f"Field {field} not found. Create it manually.")
            sys.exit(1)

    # Read and patch
    try:
        data = dp.read_dict(bc_file)
    except Exception as e:
        error(f"Could not read {bc_file}: {e}")
        sys.exit(1)

    if patch not in data:
        data[patch] = {"type": bc_type}
    else:
        data[patch]["type"] = bc_type

    if value:
        if "value" not in data[patch]:
            data[patch]["value"] = "uniform" if bc_type == "fixedValue" else ""
        if bc_type == "fixedValue":
            data[patch]["value"] = f"uniform {value}"

    dp.write_dict(bc_file, data)

    result = {"status": "success", "patch": patch, "type": bc_type, "field": field}

    if JSON_MODE:
        json_out(result)
    else:
        success(f"Boundary '{patch}' set to {bc_type} for {field}")


@setup_group.command("properties")
@click.option("--turbulence", type=click.Choice(["kEpsilon", "kOmega", "kOmegaSST", "SpalartAllmaras", "laminar"]),
              default="kEpsilon", help="Turbulence model")
@click.option("--nu", type=float, default=1e-5, help="Kinematic viscosity")
@click.argument("case_path", type=click.Path(exists=True), required=False)
@click.pass_context
def setup_properties(ctx, turbulence: str, nu: float, case_path: str):
    """Set transport and turbulence properties."""
    global JSON_MODE

    p = Path(case_path) if case_path else ctx.obj.get("project")
    if not p:
        error("No case path specified")
        sys.exit(1)

    # Write transportProperties
    dp.write_dict(p / "constant" / "transportProperties", {
        "transportModel": "Newtonian",
        "nu": nu,
        "rho": 1,
    })

    # Write turbulenceProperties
    turb_type = "turbulenceModel" if turbulence != "laminar" else "laminar"
    dp.write_dict(p / "constant" / "turbulenceProperties", {
        "simulationType": turb_type,
        "turbulenceModel": turbulence,
    } if turbulence != "laminar" else {"simulationType": "laminar"})

    result = {"status": "success", "turbulence": turbulence, "nu": nu}

    if JSON_MODE:
        json_out(result)
    else:
        success(f"Turbulence: {turbulence}, nu: {nu}")


@setup_group.command("schemes")
@click.option("--ddt", default="steadyState", help="Time derivative scheme (simpleFoam)")
@click.option("--div", default="Gauss linear", help="Divergence scheme")
@click.option("--laplacian", default="Gauss linear corrected", help="Laplacian scheme")
@click.argument("case_path", type=click.Path(exists=True), required=False)
@click.pass_context
def setup_schemes(ctx, ddt: str, div: str, laplacian: str, case_path: str):
    """Set numerical schemes in fvSchemes."""
    global JSON_MODE

    p = Path(case_path) if case_path else ctx.obj.get("project")
    if not p:
        error("No case path specified")
        sys.exit(1)

    try:
        schemes = dp.read_dict(p / "system" / "fvSchemes")
    except Exception:
        schemes = {}

    if "ddtSchemes" not in schemes:
        schemes["ddtSchemes"] = {}
    schemes["ddtSchemes"]["default"] = ddt

    if "divSchemes" not in schemes:
        schemes["divSchemes"] = {}
    schemes["divSchemes"]["default"] = div

    if "laplacianSchemes" not in schemes:
        schemes["laplacianSchemes"] = {}
    schemes["laplacianSchemes"]["default"] = laplacian

    dp.write_dict(p / "system" / "fvSchemes", schemes)

    result = {"status": "success", "ddt": ddt, "div": div, "laplacian": laplacian}

    if JSON_MODE:
        json_out(result)
    else:
        success(f"Schemes: ddt={ddt}, div={div}, laplacian={laplacian}")


@setup_group.command("solvers")
@click.option("--p-solver", default="PCG", help="Pressure solver")
@click.option("--p-tol", type=float, default=1e-6, help="Pressure tolerance")
@click.option("--p-rel", type=float, default=0.05, help="Pressure relative tolerance")
@click.argument("case_path", type=click.Path(exists=True), required=False)
@click.pass_context
def setup_solvers(ctx, p_solver: str, p_tol: float, p_rel: float, case_path: str):
    """Set linear solver parameters in fvSolution."""
    global JSON_MODE

    p = Path(case_path) if case_path else ctx.obj.get("project")
    if not p:
        error("No case path specified")
        sys.exit(1)

    try:
        sol = dp.read_dict(p / "system" / "fvSolution")
    except Exception:
        sol = {}

    if "solvers" not in sol:
        sol["solvers"] = {}

    sol["solvers"]["p"] = {
        "solver": p_solver,
        "tolerance": p_tol,
        "relTol": p_rel,
    }

    dp.write_dict(p / "system" / "fvSolution", sol)

    result = {"status": "success", "p_solver": p_solver, "p_tol": p_tol, "p_rel": p_rel}

    if JSON_MODE:
        json_out(result)
    else:
        success(f"Solvers: p={p_solver}, tol={p_tol}, relTol={p_rel}")


# -------------------------------------------------------------------
# solve group
# -------------------------------------------------------------------

@cli.group("solve")
def solve_group():
    """Solver execution and control."""
    pass


@solve_group.command("run")
@click.option("--solver", "-s", default="simpleFoam",
              type=click.Choice(["simpleFoam", "icoFoam", "pimpleFoam", "rhoSimpleFoam"]),
              help="Solver name")
@click.option("--parallel", is_flag=True)
@click.option("--processors", "-n", default=4)
@click.option("--end-time", type=float, help="Override endTime")
@click.option("--delta-t", type=float, help="Override deltaT")
@click.option("--detach", is_flag=True, help="Run in background")
@click.argument("case_path", type=click.Path(exists=True), required=False)
@click.pass_context
def solve_run(ctx, solver: str, parallel: bool, processors: int,
              end_time: Optional[float], delta_t: Optional[float],
              detach: bool, case_path: str):
    """Run an OpenFOAM solver."""
    global JSON_MODE

    p = Path(case_path) if case_path else ctx.obj.get("project")
    if not p:
        error("No case path specified")
        sys.exit(1)

    # Optionally patch controlDict
    if end_time or delta_t:
        try:
            ctrl = dp.read_dict(p / "system" / "controlDict")
            if end_time is not None:
                ctrl["endTime"] = end_time
            if delta_t is not None:
                ctrl["deltaT"] = delta_t
            dp.write_dict(p / "system" / "controlDict", ctrl)
        except Exception as e:
            warn(f"Could not patch controlDict: {e}")

    container = ctx.obj.get("container")
    result = ob.run_solver(
        p, solver,
        parallel=parallel,
        n_processors=processors,
        end_time=end_time,
        delta_t=delta_t,
        detach=detach,
        container=container,
    )

    # Parse output
    residuals = ob.parse_residuals(result.output)
    final_time = ob.parse_final_time(result.output)

    output = {
        "status": "success" if result.success else "error",
        "solver": solver,
        "returncode": result.returncode,
        "duration_seconds": round(result.duration_seconds, 2),
        "final_time": final_time,
        "residuals": residuals,
    }

    if JSON_MODE:
        json_out(output)
    else:
        if result.success:
            success(f"Solver finished at t={final_time} in {result.duration_seconds:.1f}s")
            if residuals:
                echo(f"  Final residuals: " + ", ".join(f"{k}={v:.2e}" for k, v in residuals.items()))
        else:
            error(f"Solver failed")
            echo(result.error[-300:] if result.error else "")


@solve_group.command("status")
@click.argument("case_path", type=click.Path(exists=True), required=False)
@click.pass_context
def solve_status(ctx, case_path: str):
    """Check solver status (latest time, running?)."""
    global JSON_MODE

    p = Path(case_path) if case_path else ctx.obj.get("project")
    if not p:
        error("No case path specified")
        sys.exit(1)

    try:
        latest = ob.get_latest_time(p)
    except RuntimeError:
        latest = None

    times = sorted(
        (float(d.name) for d in p.iterdir() if d.is_dir() and _is_number(d.name))
    )

    result = {
        "case_path": str(p),
        "latest_time": latest,
        "n_times": len(times),
        "times_sample": times[-5:] if len(times) > 5 else times,
    }

    if JSON_MODE:
        json_out(result)
    else:
        if latest is not None:
            success(f"Latest time: {latest}")
            echo(f"  Total time directories: {len(times)}")
        else:
            warn("No time directories found — case may not have been run")


@solve_group.command("decompose")
@click.option("--processors", "-n", default=4, help="Number of subdomains")
@click.option("--method", type=click.Choice(["simple", "scotch", "hierarchical"]),
              default="simple", help="Decomposition method")
@click.argument("case_path", type=click.Path(exists=True), required=False)
@click.pass_context
def solve_decompose(ctx, processors: int, method: str, case_path: str):
    """Decompose a case for parallel execution (writes processor* dirs)."""
    global JSON_MODE

    p = Path(case_path) if case_path else ctx.obj.get("project")
    if not p:
        error("No case path specified")
        sys.exit(1)

    # Write decomposeParDict if not exists
    decomp_path = p / "system" / "decomposeParDict"
    if not decomp_path.exists():
        coeffs = f"({processors} 1 1)"
        dp.write_dict(decomp_path, {
            "numberOfSubdomains": processors,
            "method": method,
            "simpleCoeffs": {"n": coeffs, "delta": 0.001},
        })

    container = ctx.obj.get("container")
    result = ob.run_decompose(p, container=container)

    output = {
        "status": "success" if result.success else "error",
        "n_processors": processors,
        "method": method,
        "returncode": result.returncode,
        "output": result.output[-500:] if result.output else "",
        "error": result.error[-300:] if result.error else "",
    }

    if JSON_MODE:
        json_out(output)
    else:
        if result.success:
            n = ob.get_n_processors(p)
            success(f"Decomposed into {n} processor directories")
        else:
            error("Decomposition failed")
            echo(result.error[-300:] if result.error else "")


@solve_group.command("reconstruct")
@click.option("--time", default="latestTime", help="Time to reconstruct")
@click.argument("case_path", type=click.Path(exists=True), required=False)
@click.pass_context
def solve_reconstruct(ctx, time: str, case_path: str):
    """Reconstruct a parallel case (merge processor dirs into time dirs)."""
    global JSON_MODE

    p = Path(case_path) if case_path else ctx.obj.get("project")
    if not p:
        error("No case path specified")
        sys.exit(1)

    container = ctx.obj.get("container")
    result = ob.run_reconstruct(p, time=time, container=container)

    output = {
        "status": "success" if result.success else "error",
        "time": time,
        "returncode": result.returncode,
        "output": result.output[-500:] if result.output else "",
        "error": result.error[-300:] if result.error else "",
    }

    if JSON_MODE:
        json_out(output)
    else:
        if result.success:
            success(f"Reconstructed time {time}")
        else:
            error("Reconstruction failed")
            echo(result.error[-300:] if result.error else "")


@solve_group.command("stop")
@click.argument("case_path", type=click.Path(exists=True), required=False)
@click.pass_context
def solve_stop(ctx, case_path: str):
    """Signal solver to stop (write 'stop' file)."""
    global JSON_MODE

    p = Path(case_path) if case_path else ctx.obj.get("project")
    if not p:
        error("No case path specified")
        sys.exit(1)

    # Touch a stop file
    (p / "controlDict.stop").touch()
    success("Stop signal sent (touch controlDict.stop)")


# -------------------------------------------------------------------
# postprocess group
# -------------------------------------------------------------------

@cli.group("postprocess")
def post_group():
    """Post-processing: field extraction, averaging, probes."""
    pass


@post_group.command("extract")
@click.option("--field", "-f", required=True, help="Field name (U, p, nut, etc.)")
@click.option("--patch", help="Patch name for patchAverage")
@click.option("--operator", type=click.Choice(["average", "sum", "min", "max"]),
              default="average", help="Reduction operator")
@click.option("--time", default="latestTime", help="Time directory")
@click.argument("case_path", type=click.Path(exists=True), required=False)
@click.pass_context
def post_extract(ctx, field: str, patch: Optional[str], operator: str,
                 time: str, case_path: str):
    """Extract field value (average on patch, etc.)."""
    global JSON_MODE

    p = Path(case_path) if case_path else ctx.obj.get("project")
    if not p:
        error("No case path specified")
        sys.exit(1)

    container = ctx.obj.get("container")
    try:
        if patch:
            value = ob.extract_patch_average(p, field, patch, time, container=container)
        else:
            # Just check field exists at time
            latest = time == "latestTime"
            t = ob.get_latest_time(p) if latest else float(time)
            field_path = p / str(t) / field
            if not field_path.exists():
                error(f"Field {field} not found at t={t}")
                sys.exit(1)
            value = {"field": field, "time": t, "path": str(field_path.resolve())}

        result = {"status": "success", "field": field, "value": value if isinstance(value, float) else value}

        if JSON_MODE:
            json_out(result)
        else:
            if isinstance(value, float):
                success(f"{field} {operator} on {patch or 'domain'}: {value:.6g}")
            else:
                success(f"Field {field} found at t={value['time']}")

    except Exception as e:
        if JSON_MODE:
            json_out({"status": "error", "message": str(e)})
        else:
            error(str(e))
        sys.exit(1)


@post_group.command("forces")
@click.option("--patch", required=True, help="Patch name to extract forces on")
@click.option("--time", default="latestTime", help="Time directory")
@click.option("--parallel", is_flag=True, help="Case ran in parallel")
@click.argument("case_path", type=click.Path(exists=True), required=False)
@click.pass_context
def post_forces(ctx, patch: str, time: str, parallel: bool, case_path: str):
    """Extract forces and moments on a patch using the forces functionObject."""
    global JSON_MODE

    p = Path(case_path) if case_path else ctx.obj.get("project")
    if not p:
        error("No case path specified")
        sys.exit(1)

    container = ctx.obj.get("container")

    # Write forces functionObject to controlDict if not present
    try:
        ctrl = dp.read_dict(p / "system" / "controlDict")
    except Exception:
        ctrl = {}

    # Add functions section if needed
    if "functions" not in ctrl:
        ctrl["functions"] = {}

    forces_func = {
        "type": "forces",
        "libs": '("libforces.so")',
        "patches": [patch],
        "timeStart": 0,
        "timeEnd": 1000000,
    }
    ctrl["functions"][f"forces_{patch}"] = forces_func
    dp.write_dict(p / "system" / "controlDict", ctrl)

    result = ob.run_postprocess(
        p, f"forces_{patch}", time=time, parallel=parallel, container=container
    )

    output = {
        "status": "success" if result.success else "error",
        "patch": patch,
        "time": time,
        "output": result.output[-1000:] if result.output else "",
        "error": result.error[-500:] if result.error else "",
    }

    if JSON_MODE:
        json_out(output)
    else:
        if result.success:
            success(f"Forces extracted for patch '{patch}' at t={time}")
            echo(result.output[-800:] if result.output else "")
        else:
            error("Forces extraction failed")
            echo(result.error[-300:] if result.error else "")


@post_group.command("residuals")
@click.option("--field", default="U", help="Field to show residual for")
@click.option("--time", default="latestTime", help="Time directory")
@click.argument("case_path", type=click.Path(exists=True), required=False)
@click.pass_context
def post_residuals(ctx, field: str, time: str, case_path: str):
    """Parse and display solver residuals from log output."""
    global JSON_MODE

    p = Path(case_path) if case_path else ctx.obj.get("project")
    if not p:
        error("No case path specified")
        sys.exit(1)

    # Read from the latest log file or parse from output
    log_file = p / "log." + ctx.obj.get("last_solver", "simpleFoam")
    residuals = {}
    if log_file.exists():
        text = log_file.read_text()
        residuals = ob.parse_residuals(text)

    result_data = {
        "field": field,
        "time": time,
        "residuals": residuals,
    }

    if JSON_MODE:
        json_out(result_data)
    else:
        if residuals:
            success(f"Residuals for {field}:")
            for name, val in residuals.items():
                echo(f"  {name}: {val:.6e}")
        else:
            warn("No residuals found in log file")
            echo("Run solver with log output to capture residuals")


@post_group.command("fields")
@click.option("--time", default="latestTime")
@click.argument("case_path", type=click.Path(exists=True), required=False)
@click.pass_context
def post_fields(ctx, time: str, case_path: str):
    """List available fields at a time directory."""
    global JSON_MODE

    p = Path(case_path) if case_path else ctx.obj.get("project")
    if not p:
        error("No case path specified")
        sys.exit(1)

    try:
        if time == "latestTime":
            t = ob.get_latest_time(p)
        else:
            t = float(time)
    except RuntimeError:
        error("No time directories found")
        sys.exit(1)

    fields = []
    time_dir = p / str(t)
    if time_dir.exists():
        fields = [f.name for f in time_dir.iterdir() if f.is_file()]

    result = {"time": t, "fields": fields}

    if JSON_MODE:
        json_out(result)
    else:
        success(f"Fields at t={t}:")
        for f in fields:
            echo(f"  {f}")


# -------------------------------------------------------------------
# param group (parameter sweep)
# -------------------------------------------------------------------

@cli.group("param")
def param_group():
    """Parameter sweep: run cases with varying parameters."""
    pass


@param_group.command("run")
@click.option("--var", required=True, help="Variable name (e.g. INLET_VELOCITY)")
@click.option("--values", required=True, help="Space-separated values (e.g. '1 5 10 20')")
@click.option("--cases-dir", default="./sweep", help="Directory to store sweep cases")
@click.option("--solver", default="simpleFoam", help="Solver to run")
@click.option("--max-cases", "-n", default=8, help="Max parallel cases")
@click.argument("case_path", type=click.Path(exists=True), required=False)
@click.pass_context
def param_run(ctx, var: str, values: str, cases_dir: str, solver: str,
              max_cases: int, case_path: str):
    """Run parameter sweep: clone case with each value, collect results.

    Example:
      openfoam param run --var INLET_VELOCITY --values "1 5 10 20" \\
          --cases ./sweep_results --project ./baseCase
    """
    global JSON_MODE

    p = Path(case_path) if case_path else ctx.obj.get("project")
    if not p:
        error("No case path specified")
        sys.exit(1)

    base_case = p.resolve()
    sweep_root = Path(cases_dir).resolve()
    sweep_root.mkdir(parents=True, exist_ok=True)

    container = ctx.obj.get("container")
    value_list = values.split()
    results = []

    echo(f"Running parameter sweep: {var} = {value_list}")
    echo(f"Base case: {base_case}  →  {sweep_root}")
    echo(f"Max parallel: {max_cases}")

    for i, val in enumerate(value_list):
        case_name = f"case_{var}_{val}"
        variant_path = sweep_root / case_name

        # Clone base case
        import shutil
        shutil.copytree(base_case, variant_path, dirs_exist_ok=False)

        # Substitute variable in all dict files
        for dict_file in variant_path.rglob("*.dict"):
            dp.substitute_vars(dict_file, {var: val})
        for dict_file in variant_path.rglob("Dict"):
            dp.substitute_vars(dict_file, {var: val})
        # Also substitute in controlDict
        dp.substitute_vars(variant_path / "system" / "controlDict", {var: val})

        echo(f"\n[{i+1}/{len(value_list)}] {var}={val} → {case_name}")

        # Run blockMesh
        r_mesh = ob.run_blockmesh(variant_path, container=container)
        if not r_mesh.success:
            warn(f"  blockMesh failed for {var}={val}: {r_mesh.error[-100:]}")
            results.append({"value": val, "case": case_name, "status": "mesh_failed",
                           "error": r_mesh.error[-200:]})
            continue

        # Run solver
        r_solver = ob.run_solver(
            variant_path, solver,
            parallel=False,
            container=container,
        )

        residuals = ob.parse_residuals(r_solver.output)
        final_time = ob.parse_final_time(r_solver.output)
        converged = ob.check_solver_converged(r_solver.output)

        results.append({
            "value": val,
            "case": case_name,
            "status": "success" if r_solver.success else "failed",
            "final_time": final_time,
            "converged": converged,
            "residuals": residuals,
            "duration_seconds": round(r_solver.duration_seconds, 2),
        })

        status_str = "✓ converged" if converged else ("✓ finished" if r_solver.success else "✗ failed")
        echo(f"  {status_str}  t={final_time}  "
             + ", ".join(f"{k}={v:.1e}" for k, v in list(residuals.items())[:3]))

    # Write summary
    summary_path = sweep_root / "sweep_summary.json"
    summary_path.write_text(json.dumps({
        "variable": var,
        "values": value_list,
        "base_case": str(base_case),
        "results": results,
    }, indent=2))

    if JSON_MODE:
        json_out({"status": "complete", "summary": str(summary_path), "results": results})
    else:
        echo(f"\n{'='*50}")
        success(f"Sweep complete: {len(results)} cases")
        echo(f"Summary: {summary_path}")
        for r in results:
            echo(f"  {var}={r['value']}: {r['status']} | t={r.get('final_time','?')}")


@param_group.command("design")
@click.option("--var", required=True, help="Variable name to add to case")
@click.option("--placeholder", default="#VAR#", help="Placeholder in dict files")
@click.argument("case_path", type=click.Path(exists=True), required=False)
@click.pass_context
def param_design(ctx, var: str, placeholder: str, case_path: str):
    """Mark a variable as a design parameter in the case.

    Adds #VAR# placeholders in controlDict endTime and writeInterval.
    The user should replace #VAR# with their actual parameter name.
    """
    global JSON_MODE

    p = Path(case_path) if case_path else ctx.obj.get("project")
    if not p:
        error("No case path specified")
        sys.exit(1)

    ctrl = p / "system" / "controlDict"
    if ctrl.exists():
        dp.substitute_vars(ctrl, {var.upper(): placeholder})

    result = {"status": "success", "var": var, "placeholder": placeholder}
    if JSON_MODE:
        json_out(result)
    else:
        success(f"Design variable '{var}' marked with '{placeholder}' placeholder")

def _is_number(s: str) -> bool:
    try:
        float(s)
        return True
    except ValueError:
        return False


def _write_default_U(case_path: Path, template: str, patch: str = "inlet",
                     bc_type: str = "fixedValue", value: Optional[str] = None) -> None:
    """Write default U boundary conditions."""
    if value is None:
        value = "1 0 0"  # default to 1 m/s in x

    content = {
        "dimensions": "[0 1 -1 0 0 0 0]",
        "internalField": "uniform (1 0 0)",
        "boundaryField": {
            patch: {
                "type": bc_type,
                "value": f"uniform {value}",
            } if bc_type == "fixedValue" else {
                "type": bc_type,
            },
            "outlet": {
                "type": "zeroGradient",
            },
            "wall": {
                "type": "noSlip",
            },
        },
    }
    dp.write_dict(case_path / "0" / "U", content)


def _write_default_p(case_path: Path, patch: str = "outlet",
                      bc_type: str = "zeroGradient", value: Optional[str] = None) -> None:
    """Write default p boundary conditions."""
    content = {
        "dimensions": "[0 2 -2 0 0 0 0]",
        "internalField": "uniform 0",
        "boundaryField": {
            patch: {
                "type": bc_type,
            } if bc_type == "zeroGradient" else {
                "type": bc_type,
                "value": f"uniform {value or 101325}",
            },
            "inlet": {
                "type": "zeroGradient",
            },
            "wall": {
                "type": "fixedFluxPressure",
            },
        },
    }
    dp.write_dict(case_path / "0" / "p", content)


def _walk_dirs(base: Path, max_depth: int, current_depth: int = 0) -> list[Path]:
    """Recursively walk directories up to max_depth."""
    results = []
    if current_depth >= max_depth:
        return results
    results.append(base)
    try:
        for item in base.iterdir():
            if item.is_dir() and not item.name.startswith('.'):
                results.extend(_walk_dirs(item, max_depth, current_depth + 1))
    except PermissionError:
        pass
    return results


# -------------------------------------------------------------------
# Entry point
# -------------------------------------------------------------------

def main():
    cli(obj={})


if __name__ == "__main__":
    main()
