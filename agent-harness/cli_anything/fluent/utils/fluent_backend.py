"""
fluent_backend.py - ANSYS Fluent CLI wrapper

Wraps real Fluent TUI commands for use by the cli-anything harness.

ANSYS Fluent is installed via:
  - Linux: standard ANSYS installation (/ansys_inc/vXXX/fluent/)
  - Container: pre-installed in cfd-openfoam

Principles:
  - MUST call real Fluent commands, not reimplement
  - Software is HARD dependency - error clearly if not found
  - All operations via journal files (.jou) executed with fluent command
"""

from __future__ import annotations

import os
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


# -------------------------------------------------------------------
# Installation detection
# -------------------------------------------------------------------

FLUENT_VERSION = "1.0.0"


def find_fluent() -> Path:
    """
    Locate Fluent binary.

    Returns Path to fluent executable.
    Raises RuntimeError if not found.
    """
    # Check common ANSYS installation paths
    ansys_root = os.environ.get("ANSYS_ROOT", "/ansys_inc")
    fluent_bin = os.environ.get("FLUENT_PATH")

    if not fluent_bin:
        # Try to find latest version
        if Path(ansys_root).exists():
            versions = sorted(Path(ansys_root).glob("v*"), reverse=True)
            for v in versions:
                candidate = v / "fluent" / "bin" / "fluent"
                if candidate.exists():
                    fluent_bin = str(candidate)
                    break

    if not fluent_bin:
        if os.environ.get("FLUENT_MOCK"):
            return Path("/usr/bin/true")
        raise RuntimeError(
            f"Fluent not found.\n"
            f"Set FLUENT_PATH env var or install ANSYS Fluent.\n"
            f"Container: use cfd-openfoam image with Fluent pre-installed"
        )

    bin_path = Path(fluent_bin)
    if not bin_path.exists():
        if os.environ.get("FLUENT_MOCK"):
            return Path("/usr/bin/true")
        raise RuntimeError(f"Fluent not found at {bin_path}")

    return bin_path


# -------------------------------------------------------------------
# Result dataclass
# -------------------------------------------------------------------

@dataclass
class CommandResult:
    """Result of a Fluent command execution."""
    success: bool
    output: str = ""
    error: str = ""
    returncode: int = 0
    duration_seconds: float = 0.0


# -------------------------------------------------------------------
# Core runner
# -------------------------------------------------------------------

CONTAINER_NAME = "cfd-openfoam"


def _run(
    cmd: list[str],
    journal_content: Optional[str] = None,
    cwd: Optional[Path] = None,
    timeout: Optional[int] = None,
    check: bool = True,
    container: Optional[str] = None,
) -> CommandResult:
    """
    Run fluent with optional journal file.

    Args:
        cmd: Command as list of strings (e.g. ["fluent", "3ddp", "-i", "journal.jou"])
        journal_content: Content of journal file to write and execute
        cwd: Working directory
        timeout: Max seconds (None = no limit)
        check: Raise on non-zero exit
        container: Docker container name

    Returns:
        CommandResult
    """
    fluent = find_fluent()

    journal_path = None
    if journal_content:
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jou", delete=False) as f:
            f.write(journal_content)
            f.flush()
            journal_path = Path(f.name)

    docker_cmd = None
    if container:
        jou_arg = f"-i {journal_path.name}" if journal_path else ""
        docker_cmd = [
            "docker", "exec", container,
            "/bin/bash", "-lc",
            f"source /opt/openfoam10/etc/bashrc 2>/dev/null || true; "
            f"cd {cwd or '/tmp'} && {fluent} {' '.join(cmd[1:])} {jou_arg}"
        ]

    start = time.time()
    try:
        if journal_path:
            # Write journal, then run with -i flag
            actual_cmd = [str(fluent)] + cmd[1:] + ["-i", str(journal_path)]
        else:
            actual_cmd = [str(fluent)] + cmd[1:]

        proc = subprocess.run(
            docker_cmd if container else actual_cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
        )
        duration = time.time() - start

        if journal_path:
            Path(journal_path).unlink(missing_ok=True)

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
            error=f"Command timed out after {timeout}s",
            returncode=-1,
            duration_seconds=timeout or 0,
        )
    except Exception as e:
        if journal_path:
            Path(journal_path).unlink(missing_ok=True)
        return CommandResult(
            success=False,
            output="",
            error=str(e),
            returncode=-99,
            duration_seconds=time.time() - start,
        )


# -------------------------------------------------------------------
# Case file operations
# -------------------------------------------------------------------

def case_new(
    case_name: str,
    dimension: int = 3,
    container: Optional[str] = None,
) -> CommandResult:
    """
    Create a new Fluent case.

    Args:
        case_name: Name of case file (.cas/.cas.gz)
        dimension: 2 or 3 (default 3)
        container: Docker container name

    Returns:
        CommandResult
    """
    journal = f"""; Fluent journal - new case
/newcase
{case_name}
"""
    dim_flag = "2d" if dimension == 2 else "3d"
    result = _run(
        [dim_flag],
        journal_content=journal,
        timeout=30,
        check=False,
        container=container,
    )
    return result


def case_open(
    case_file: str,
    container: Optional[str] = None,
) -> CommandResult:
    """
    Open an existing Fluent case file.

    Args:
        case_file: Path to case file (.cas/.cas.gz)
        container: Docker container name

    Returns:
        CommandResult
    """
    case_file = Path(case_file).resolve()
    journal = f"""; Fluent journal - open case
/file/read-case {case_file}
"""
    result = _run(
        [],
        journal_content=journal,
        timeout=60,
        check=False,
        container=container,
    )
    return result


def case_save(
    case_file: Optional[str] = None,
    container: Optional[str] = None,
) -> CommandResult:
    """
    Save the current Fluent case.

    Args:
        case_file: Optional path to save as (if None, saves to current)
        container: Docker container name

    Returns:
        CommandResult
    """
    if case_file:
        journal = f"""; Fluent journal - save case
/file/write-case {case_file}
"""
    else:
        journal = "; Fluent journal - save case\n/file/write-case\n"

    result = _run(
        [],
        journal_content=journal,
        timeout=60,
        check=False,
        container=container,
    )
    return result


# -------------------------------------------------------------------
# Mesh operations
# -------------------------------------------------------------------

def mesh_read(
    mesh_file: str,
    container: Optional[str] = None,
) -> CommandResult:
    """
    Read a mesh file into Fluent.

    Args:
        mesh_file: Path to mesh file (.msh, .msh.gz)
        container: Docker container name

    Returns:
        CommandResult
    """
    mesh_file = Path(mesh_file).resolve()
    journal = f"""; Fluent journal - read mesh
/file/read-mesh {mesh_file}
"""
    result = _run(
        [],
        journal_content=journal,
        timeout=120,
        check=False,
        container=container,
    )
    return result


# -------------------------------------------------------------------
# Solver setup
# -------------------------------------------------------------------

def setup_solver(
    solver_type: str = "pressure-based",
    container: Optional[str] = None,
) -> CommandResult:
    """
    Configure solver type.

    Args:
        solver_type: 'pressure-based' or 'density-based'
        container: Docker container name

    Returns:
        CommandResult
    """
    if solver_type == "density-based":
        solver_cmd = "/define/models/density-based? n"
    else:
        solver_cmd = "/define/models/pressure-based? n"

    journal = f"""; Fluent journal - setup solver
{solver_cmd}
"""
    result = _run(
        [],
        journal_content=journal,
        timeout=30,
        check=False,
        container=container,
    )
    return result


def setup_models(
    energy: bool = False,
    viscous: str = "k-epsilon",
    container: Optional[str] = None,
) -> CommandResult:
    """
    Configure physical models.

    Args:
        energy: Enable energy equation
        viscous: Viscous model ('k-epsilon', 'k-omega', 'SST', 'laminar')
        container: Docker container name

    Returns:
        CommandResult
    """
    viscous_map = {
        "k-epsilon": "/define/models/viscous/k-epsilon? n",
        "k-omega": "/define/models/viscous/k-omega? n",
        "SST": "/define/models/viscous/sst? n",
        "laminar": "/define/models/viscous/laminar? n",
    }
    vis_cmd = viscous_map.get(viscous, viscous_map["k-epsilon"])

    journal = f"""; Fluent journal - setup models
/define/models/energy? {'y' if energy else 'n'}
{vis_cmd}
"""
    result = _run(
        [],
        journal_content=journal,
        timeout=30,
        check=False,
        container=container,
    )
    return result


def setup_materials(
    fluid: str = "air",
    container: Optional[str] = None,
) -> CommandResult:
    """
    Set fluid material properties.

    Args:
        fluid: Fluid name ('air', 'water', 'water-liquid')
        container: Docker container name

    Returns:
        CommandResult
    """
    journal = f"""; Fluent journal - setup materials
/define/materials/create-or-copy-fluids
{fluid}
/define/materials/change-mater/fluid
{fluid}
/no
"""
    result = _run(
        [],
        journal_content=journal,
        timeout=30,
        check=False,
        container=container,
    )
    return result


# -------------------------------------------------------------------
# Boundary conditions
# -------------------------------------------------------------------

def bc_set(
    zone_name: str,
    bc_type: str,
    params: Optional[dict] = None,
    container: Optional[str] = None,
) -> CommandResult:
    """
    Set boundary condition for a zone.

    Args:
        zone_name: Name of the boundary zone
        bc_type: Type ('velocity-inlet', 'pressure-outlet', 'wall', 'symmetry')
        params: Dict of BC parameters (e.g. {"velocity": 10.0, "temperature": 300})
        container: Docker container name

    Returns:
        CommandResult
    """
    params = params or {}

    if bc_type == "velocity-inlet":
        vel = params.get("velocity", 10.0)
        temp = params.get("temperature", 300)
        journal = f"""; Fluent journal - set velocity inlet
/boundary/{zone_name}
velocity-inlet
yes {vel}
yes {temp}
no
"""
    elif bc_type == "pressure-outlet":
        p = params.get("pressure", 0)
        journal = f"""; Fluent journal - set pressure outlet
/boundary/{zone_name}
pressure-outlet
{ p}
/yes
"""
    elif bc_type == "wall":
        journal = f"""; Fluent journal - set wall
/boundary/{zone_name}
wall
"""
    elif bc_type == "symmetry":
        journal = f"""; Fluent journal - set symmetry
/boundary/{zone_name}
symmetry
"""
    else:
        return CommandResult(
            success=False,
            error=f"Unknown boundary condition type: {bc_type}",
            returncode=1,
        )

    result = _run(
        [],
        journal_content=journal,
        timeout=30,
        check=False,
        container=container,
    )
    return result


# -------------------------------------------------------------------
# Solution
# -------------------------------------------------------------------

def solve_init(
    container: Optional[str] = None,
) -> CommandResult:
    """
    Initialize solution.

    Returns:
        CommandResult
    """
    journal = """; Fluent journal - initialize
/solve/initialize/hyb-initialization
"""
    result = _run(
        [],
        journal_content=journal,
        timeout=30,
        check=False,
        container=container,
    )
    return result


def solve_iterate(
    n_iter: int,
    container: Optional[str] = None,
) -> CommandResult:
    """
    Run solution iterations.

    Args:
        n_iter: Number of iterations
        container: Docker container name

    Returns:
        CommandResult with iteration output
    """
    journal = f"""\
; Fluent journal - iterate
/solve/iterate
{n_iter}
"""
    result = _run(
        [],
        journal_content=journal,
        timeout=max(30, n_iter * 2),
        check=False,
        container=container,
    )
    return result


def solve_monitors(
    residual_enable: bool = True,
    residual_plot: bool = True,
    container: Optional[str] = None,
) -> CommandResult:
    """
    Configure solution monitors.

    Returns:
        CommandResult
    """
    journal = f"""\
; Fluent journal - setup monitors
/monitors/residual/set
{'y' if residual_enable else 'n'}
{'y' if residual_plot else 'n'}
"""
    result = _run(
        [],
        journal_content=journal,
        timeout=30,
        check=False,
        container=container,
    )
    return result


# -------------------------------------------------------------------
# Results
# -------------------------------------------------------------------

def report(
    report_type: str,
    field: str = "velocity-magnitude",
    surface: Optional[str] = None,
    container: Optional[str] = None,
) -> dict:
    """
    Generate a Fluent report.

    Args:
        report_type: 'surface' or 'flux'
        field: Field to report (e.g. 'velocity-magnitude', 'temperature', 'pressure')
        surface: Surface name for the report
        container: Docker container name

    Returns:
        dict with parsed report data
    """
    surf_arg = f"() {surface}" if surface else "()"
    journal = f"""\
; Fluent journal - report
/report/{report_type}/surface-fluxes{ surf_arg}
/report/{report_type}/surface-integrals{ surf_arg}
/exit
"""
    result = _run(
        [],
        journal_content=journal,
        timeout=60,
        check=False,
        container=container,
    )

    parsed = parse_report_output(result.output, field)
    parsed["success"] = result.success
    return parsed


def parse_report_output(output: str, field: str) -> dict:
    """
    Parse Fluent report output.

    Extracts flux or surface integral values.
    """
    data = {
        "field": field,
        "values": [],
        "summary": None,
    }

    lines = output.split("\n")
    for line in lines:
        line = line.strip()
        # Look for numeric values after field names
        m = re.search(r"([\w\s-]+)\s*:\s*([-\d.e+]+)", line)
        if m:
            name = m.group(1).strip()
            val = float(m.group(2))
            data["values"].append({"name": name, "value": val})

    return data


def export_results(
    file_path: str,
    surface: Optional[str] = None,
    container: Optional[str] = None,
) -> CommandResult:
    """
    Export solution data.

    Args:
        file_path: Output file path
        surface: Optional surface to export
        container: Docker container name

    Returns:
        CommandResult
    """
    surf_arg = f"() {surface}" if surface else "()"
    journal = f"""\
; Fluent journal - export
/file/export/transient-data
{file_path}
{ surf_arg}
/n
"""
    result = _run(
        [],
        journal_content=journal,
        timeout=120,
        check=False,
        container=container,
    )
    return result
