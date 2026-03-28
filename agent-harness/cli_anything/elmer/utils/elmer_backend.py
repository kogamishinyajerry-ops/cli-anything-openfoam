"""
elmer_backend.py - Elmer FEM Solver CLI wrapper

Elmer is an open-source multiphysics simulation software.
Key commands:
  - ElmerSolver <case.sif>     Run simulation
  - ElmerGrid                  Mesh operations
  - ElmerPost                   Post-processing

Install:
  - Linux: sudo apt install elmerfem
  - macOS: brew install elmer
  - Source: https://github.com/ElmerCSC/elmerfem

Principles:
  - MUST call real Elmer commands, not reimplement
  - ElmerSolver requires .sif (Solver Input File) format
  - Output: .result files, .vtu for ParaView
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


# -------------------------------------------------------------------
# Version
# -------------------------------------------------------------------

ELMER_VERSION = "1.0.0"


# -------------------------------------------------------------------
# Installation detection
# -------------------------------------------------------------------

ELMER_SOLVER_PATHS = [
    "/usr/bin/ElmerSolver",
    "/usr/local/bin/ElmerSolver",
    Path.home() / "elmer/bin/ElmerSolver",
]


def find_elmer_solver() -> Path:
    """Locate ElmerSolver binary."""
    if os.environ.get("ELMER_MOCK"):
        return Path("/usr/bin/true")

    path = os.environ.get("ELMER_SOLVER_PATH")
    if path:
        p = Path(path)
        if p.exists():
            return p

    for candidate in ELMER_SOLVER_PATHS:
        p = Path(candidate)
        if p.exists():
            return p

    try:
        result = subprocess.run(
            ["which", "ElmerSolver"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            return Path(result.stdout.strip())
    except Exception:
        pass

    raise RuntimeError(
        "ElmerSolver not found.\n"
        "Set ELMER_SOLVER_PATH env var or install Elmer.\n"
        "Linux: sudo apt install elmerfem\n"
        "macOS: brew install elmer\n"
        "Set ELMER_MOCK=1 for testing."
    )


def find_elmer_grid() -> Path:
    """Locate ElmerGrid binary."""
    if os.environ.get("ELMER_MOCK"):
        return Path("/usr/bin/true")

    path = os.environ.get("ELMER_GRID_PATH")
    if path:
        p = Path(path)
        if p.exists():
            return p

    for candidate in ["/usr/bin/ElmerGrid", "/usr/local/bin/ElmerGrid"]:
        p = Path(candidate)
        if p.exists():
            return p

    try:
        result = subprocess.run(["which", "ElmerGrid"], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            return Path(result.stdout.strip())
    except Exception:
        pass

    raise RuntimeError("ElmerGrid not found. Set ELMER_GRID_PATH or install elmerfem.")


# -------------------------------------------------------------------
# Result dataclass
# -------------------------------------------------------------------

@dataclass
class CommandResult:
    """Result of an Elmer command execution."""
    success: bool
    output: str = ""
    error: str = ""
    returncode: int = 0
    duration_seconds: float = 0.0


# -------------------------------------------------------------------
# Core runner
# -------------------------------------------------------------------

def _run(cmd: list, timeout: int = 600, check: bool = True) -> CommandResult:
    """Run an Elmer command."""
    start = time.time()
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
        )
        duration = time.time() - start

        if check and proc.returncode != 0:
            return CommandResult(
                success=False,
                output=proc.stdout,
                error=proc.stderr,
                returncode=proc.returncode,
                duration_seconds=duration,
            )

        return CommandResult(
            success=proc.returncode == 0,
            output=proc.stdout,
            error=proc.stderr,
            returncode=proc.returncode,
            duration_seconds=duration,
        )
    except subprocess.TimeoutExpired:
        return CommandResult(
            success=False,
            output="",
            error="Command timed out after {}s".format(timeout),
            returncode=-1,
            duration_seconds=timeout,
        )
    except Exception as e:
        return CommandResult(
            success=False,
            output="",
            error=str(e),
            returncode=-99,
            duration_seconds=time.time() - start,
        )


# -------------------------------------------------------------------
# Version / Info
# -------------------------------------------------------------------

def get_version() -> dict:
    """Get Elmer version."""
    if os.environ.get("ELMER_MOCK"):
        return {"success": True, "version": "9.0", "solver": "ElmerSolver", "grid": "ElmerGrid"}

    try:
        solver = find_elmer_solver()
        result = subprocess.run(
            [str(solver), "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return {"success": True, "version": result.stdout.strip()}
    except Exception:
        pass

    return {"success": False, "error": "Failed to get Elmer version"}


# -------------------------------------------------------------------
# Mesh operations (ElmerGrid)
# -------------------------------------------------------------------

def import_mesh(
    mesh_format: str,
    input_file: str,
    output_dir: str,
) -> CommandResult:
    """
    Import mesh from various formats to ElmerMesh format.

    Args:
        mesh_format: Input format (e.g. 'gmsh', 'ansys', 'abaqus', 'stl')
        input_file: Input mesh file
        output_dir: Output directory for Elmer mesh

    Returns:
        CommandResult
    """
    inp = Path(input_file)
    if not inp.exists():
        return CommandResult(success=False, error="Input file not found: {}".format(inp), returncode=1)

    if os.environ.get("ELMER_MOCK"):
        return CommandResult(success=True, output="Mesh imported: ElmerMesh format", returncode=0)

    grid = find_elmer_grid()
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    cmd = [str(grid), "-import", mesh_format, str(inp), "-out", str(out_dir)]
    return _run(cmd, timeout=120, check=False)


def mesh_info(mesh_dir: str) -> dict:
    """
    Get information about an Elmer mesh.

    Returns dict with mesh statistics.
    """
    mesh_path = Path(mesh_dir)

    if os.environ.get("ELMER_MOCK"):
        return {
            "success": True,
            "mesh_dir": str(mesh_path),
            "nodes": 12500,
            "elements": 8200,
            "element_types": ["tetra10", "tri6"],
            "boundaries": 6,
        }

    if not mesh_path.exists():
        return {"success": False, "error": "Mesh directory not found: {}".format(mesh_path)}

    grid = find_elmer_grid()
    result = _run([str(grid), "-info", str(mesh_path)], timeout=30, check=False)
    if result.success:
        return {"success": True, "output": result.output}
    return {"success": False, "error": result.error}


# -------------------------------------------------------------------
# Simulation (ElmerSolver)
# -------------------------------------------------------------------

def run_simulation(
    sif_file: str,
    mesh_dir: str,
    output_dir: Optional[str] = None,
    case_name: Optional[str] = None,
) -> CommandResult:
    """
    Run ElmerSolver simulation.

    Args:
        sif_file: Path to .sif (Solver Input File)
        mesh_dir: Path to mesh directory
        output_dir: Output directory
        case_name: Case name for output files

    Returns:
        CommandResult
    """
    sif = Path(sif_file)
    if not sif.exists():
        return CommandResult(success=False, error="SIF file not found: {}".format(sif), returncode=1)

    mesh = Path(mesh_dir)
    if not mesh.exists():
        return CommandResult(success=False, error="Mesh directory not found: {}".format(mesh), returncode=1)

    if os.environ.get("ELMER_MOCK"):
        return CommandResult(
            success=True,
            output="ElmerSolver: simulation complete\n"
                    "  Iterations: 150\n"
                    "  Final residual: 1.2e-8\n"
                    "  CPU time: 45.3s",
            returncode=0,
        )

    solver = find_elmer_solver()
    cmd = [str(solver), str(sif_file), "-mesh", str(mesh_dir)]
    if output_dir:
        cmd.extend(["-out", str(output_dir)])
    if case_name:
        cmd.extend(["-name", case_name])

    return _run(cmd, timeout=3600, check=False)


def create_static_sif(
    output_path: str,
    title: str = "Elmer Static Analysis",
    body_force: float = 0.0,
    pressure: float = 0.0,
    youngs_modulus: float = 210000.0,
    poissons_ratio: float = 0.3,
) -> CommandResult:
    """
    Create a basic static analysis .sif file.

    Args:
        output_path: Output .sif file path
        title: Analysis title
        body_force: Body force magnitude
        pressure: Applied pressure
        youngs_modulus: Young's modulus (Pa)
        poissons_ratio: Poisson's ratio

    Returns:
        CommandResult
    """
    path = Path(output_path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)

    sif_content = """! ElmerSolver input file: {title}
Header
  mesh = "<mesh_dir>"
  Output File = "results.ep"
  Post File = "results.vtu"
End

Simulation
  Max Output Level = 3
  Coordinate System = Cartesian
  Coordinate Mapping(3) = 1 2 3
  Simulation Type = Steady state
  Steady State Max Iterations = 100
End

Body 1
  Target Bodies = All
  Equation = 1
  Material = 1
End

Equation 1
  Name = "Elasticity"
  Active Solvers(1) = 1
End

Solver 1
  Equation = Elasticina
  Procedure = "ElasticSolve" "ElasticSolver"
  Variable = -dofs 3 Displacement
  Exec Solver = Always
  Stabilize = True
  Bubble = True
  Optimize Bandwidth = True
End

Material 1
  Name = Steel
  Poisson ratio = {poisson}
  Youngs modulus = {young}
  Density = 7850
End

Boundary Condition 1
  Target Boundaries = 1
  Displacement 1 = 0
  Displacement 2 = 0
  Displacement 3 = 0
End

Boundary Condition 2
  Target Boundaries = 2
  Pressure = {pressure}
End
""".format(title=title, poisson=poissons_ratio, young=youngs_modulus, pressure=pressure)

    path.write_text(sif_content)
    return CommandResult(
        success=True,
        output="Created SIF file: {}".format(path),
        returncode=0,
    )
