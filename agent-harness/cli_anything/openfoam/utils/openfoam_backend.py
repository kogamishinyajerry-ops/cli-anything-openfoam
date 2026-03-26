from __future__ import annotations
"""
openfoam_backend.py — OpenFOAM CLI wrapper

Wraps real OpenFOAM commands (blockMesh, snappyHexMesh, simpleFoam, etc.)
for use by the cli-anything-openfoam harness.

Principles (from HARNESS.md):
- MUST call the real OpenFOAM commands, not reimplement
- Software is a HARD dependency — error clearly if not found
- Always verify output (not just exit 0)
"""

import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


# -------------------------------------------------------------------
# Version detection
# -------------------------------------------------------------------

@dataclass
class OpenFOAMInstall:
    """OpenFOAM installation info"""
    root: Path          # e.g. /opt/openfoam10
    version: str        # e.g. "v2312", "v2406", "v10"
    arch: str           # e.g. "linux64Gcc"
    appbin: Path        # $FOAM_APPBIN
    libbin: Path        # $FOAM_LIBBIN
    user: Path          # $FOAM_USER
    mpirun: Optional[Path]  # mpirun path (None if MPI not found)


def find_openfoam() -> OpenFOAMInstall:
    """
    Locate OpenFOAM installation from environment.

    Returns OpenFOAMInstall with paths.
    Raises RuntimeError if OpenFOAM is not found.
    """
    foam_dir = os.environ.get("WM_PROJECT_DIR") or os.environ.get("OpenFOAM_DIR")
    if not foam_dir:
        # Try common locations
        for candidate in ["/opt/openfoam10", "/opt/OpenFOAM-10",
                          Path.home() / "OpenFOAM" / "OpenFOAM-10"]:
            if Path(candidate).exists():
                foam_dir = str(candidate)
                break

    if not foam_dir or not Path(foam_dir).exists():
        raise RuntimeError(
            "OpenFOAM is not installed or $WM_PROJECT_DIR is not set.\n"
            "Install OpenFOAM:\n"
            "  Ubuntu/Debian: sudo apt install openfoam\n"
            "  Or download from: https://openfoam.org/download/"
        )

    root = Path(foam_dir).resolve()

    # Detect version from version file
    version_file = root / "etc" / "version"
    version = "unknown"
    if version_file.exists():
        version = version_file.read_text().strip()
    else:
        # Fallback: infer from path
        m = re.search(r'OpenFOAM[-]?(\d+[\d.]*)', str(root))
        if m:
            major = m.group(1)
            version = f"v{major}" if len(major.split('.')) > 1 else f"v{major[0]}.{major[1:]}"

    appbin = Path(os.environ.get("FOAM_APPBIN", str(root / "platforms" / "linux64Gcc" / "bin")))
    libbin = Path(os.environ.get("FOAM_LIBBIN", str(root / "platforms" / "linux64Gcc" / "lib")))
    user_dir = Path(os.environ.get("FOAM_USER_DIR", str(Path.home() / "OpenFOAM" / f"{Path(os.environ.get('WM_PROJECT_USER_DIR', str(root)).split('/')[-1])}-10" / "platforms" / "linux64Gcc")))

    # Detect MPI
    mpirun = shutil.which("mpirun")

    return OpenFOAMInstall(
        root=root,
        version=version,
        arch="linux64Gcc",
        appbin=appbin,
        libbin=libbin,
        user=user_dir,
        mpirun=Path(mpirun) if mpirun else None,
    )


def get_foam_version() -> str:
    """Convenience: return version string only."""
    return find_openfoam().version


# -------------------------------------------------------------------
# Command discovery
# -------------------------------------------------------------------

SOLVER_COMMANDS = {
    "simpleFoam", "icoFoam", "pisoFoam", "pimpleFoam",
    "rhoSimpleFoam", "rhoCentralFoam", "buoyantFoam",
    "chtMultiRegionFoam", "lagrangian", "sprayFoam",
    "electricalFoam", "fuelFoam", "barotropicFoam",
}

MESH_COMMANDS = {
    "blockMesh", "snappyHexMesh", "cfMesh", "foamyHexMesh",
    "autoDualMesh", "checkMesh", "transformPoints",
    "createPatch", "stitchMesh", "mergeMeshes",
}

POST_COMMANDS = {
    "postProcess", "reconstructPar", "decomposePar",
    "foamDictionary", "foamCalc", "patchAverage",
    "patchIntegrate", "wallShearStress", "sample",
    "streamFunction", "vorticity", "grad",
    "div", "laplacian", "surfaceFeatures",
}

ALL_COMMANDS = SOLVER_COMMANDS | MESH_COMMANDS | POST_COMMANDS


def find_command(name: str, foam: Optional[OpenFOAMInstall] = None) -> Path:
    """
    Find an OpenFOAM command in PATH or FOAM_APPBIN.
    Returns Path to the executable.
    Raises RuntimeError if not found.
    """
    path = shutil.which(name)
    if path:
        return Path(path)

    if foam is None:
        foam = find_openfoam()

    candidate = foam.appbin / name
    if candidate.exists():
        return candidate

    raise RuntimeError(
        f"OpenFOAM command '{name}' not found.\n"
        f"Check that OpenFOAM is sourced correctly: 'source /opt/openfoam10/etc/bashrc'\n"
        f"Searched in PATH and {foam.appbin}"
    )


# -------------------------------------------------------------------
# Output parsers
# -------------------------------------------------------------------

def parse_residuals(log_text: str) -> dict[str, float]:
    """Parse solver residual lines. Matches both 'Initial residual' and 'Final residual'."""
    residuals: dict[str, float] = {}
    for line in log_text.splitlines():
        # Try Final residual first (converged value), fall back to Initial
        m = re.search(r'Solving for (\w+).*?Final residual\s*=\s*([0-9.eE+-]+)', line)
        if not m:
            m = re.search(r'Solving for (\w+).*?Initial residual\s*=\s*([0-9.eE+-]+)', line)
        if m:
            residuals[m.group(1)] = float(m.group(2))
    return residuals


def parse_final_time(log_text: str) -> float:
    """Extract final time from solver log."""
    times = [float(m.group(1)) for m in re.finditer(r'^Time\s*=\s*([0-9.eE+-]+)', log_text, re.MULTILINE)]
    return times[-1] if times else 0.0


def parse_checkmesh_quality(log_text: str) -> dict:
    """
    Parse checkMesh output for mesh quality metrics.
    """
    cells = points = faces = 0
    max_aspect = 0.0

    m = re.search(r'\bcells:\s+(\d+)', log_text)
    if m: cells = int(m.group(1))
    m = re.search(r'\bpoints:\s+(\d+)', log_text)
    if m: points = int(m.group(1))
    m = re.search(r'\bfaces:\s+(\d+)', log_text)
    if m: faces = int(m.group(1))
    m = re.search(r'Max aspect ratio\s+=\s+([0-9.eE+-]+)', log_text)
    if m: max_aspect = float(m.group(1))

    return {
        "cells": cells,
        "points": points,
        "faces": faces,
        "max_aspect_ratio": max_aspect,
    }


def parse_patch_average_output(text: str, field: str) -> float:
    """Parse 'Average of <field> = <value>' from patchAverage output."""
    m = re.search(r'Average of\s+\w+\s+=\s+([0-9.eE+-]+)', text)
    if m:
        return float(m.group(1))
    raise ValueError(f"Could not parse patch average from: {text[:200]}")


# -------------------------------------------------------------------
# Core runner
# -------------------------------------------------------------------

@dataclass
class CommandResult:
    success: bool
    output: str
    error: str = ""
    returncode: int = 0
    duration_seconds: float = 0.0


def _run(
    cmd: list[str],
    cwd: Optional[Path] = None,
    env_extra: Optional[dict] = None,
    timeout: Optional[int] = None,
    check: bool = True,
    container: Optional[str] = None,
) -> CommandResult:
    """Run a command, source OpenFOAM bashrc first if needed.

    Args:
        container: If set, run inside this Docker container name/ID.
    """
    import time
    start = time.monotonic()

    env = os.environ.copy()
    if env_extra:
        env.update(env_extra)

    if container:
        # Run inside Docker container
        quoted_cmd = " ".join(f'"{c}"' if " " in str(c) else str(c) for c in cmd)
        docker_cmd = [
            "docker", "exec", "-w", str(cwd) if cwd else "/tmp",
            container,
            "bash", "-c",
            f"source /opt/openfoam10/etc/bashrc && {quoted_cmd}"
        ]
        exec_cwd = None  # cwd already embedded in docker_cmd
        exec_env = env
    else:
        # Run locally with OpenFOAM sourced
        foam = find_openfoam()
        bashrc = foam.root / "etc" / "bashrc"
        quoted_cmd = " ".join(str(c) for c in cmd)
        docker_cmd = ["/bin/bash", "-c", f"source {bashrc} && {quoted_cmd}"]
        exec_cwd = str(cwd) if cwd else None
        exec_env = env

    try:
        result = subprocess.run(
            docker_cmd,
            cwd=exec_cwd,
            env=exec_env,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=check,
        )
        duration = time.monotonic() - start
        return CommandResult(
            success=result.returncode == 0,
            output=result.stdout,
            error=result.stderr,
            returncode=result.returncode,
            duration_seconds=duration,
        )
    except subprocess.TimeoutExpired as e:
        duration = time.monotonic() - start
        return CommandResult(
            success=False,
            output=e.stdout.decode() if e.stdout else "",
            error=f"Timeout after {timeout}s",
            returncode=-1,
            duration_seconds=duration,
        )
    except subprocess.CalledProcessError as e:
        duration = time.monotonic() - start
        return CommandResult(
            success=False,
            output=e.stdout or "",
            error=e.stderr or "",
            returncode=e.returncode,
            duration_seconds=duration,
        )


# -------------------------------------------------------------------
# Mesh commands
# -------------------------------------------------------------------

def run_blockmesh(case_path: Path, dict_path: Optional[Path] = None,
                  container: Optional[str] = None) -> CommandResult:
    """
    Run blockMesh on a case directory.

    Args:
        case_path: Path to the case directory (must contain system/blockMeshDict)
        dict_path: Optional path to blockMeshDict (if not in system/)
        container: Docker container name to run inside
    """
    cmd = ["blockMesh"]
    if dict_path:
        cmd += [f"-dict={dict_path}"]
    result = _run(cmd, cwd=case_path, container=container)
    return result


def run_checkmesh(case_path: Path, time: str = "latestTime",
                  container: Optional[str] = None) -> CommandResult:
    """Run checkMesh on a case directory."""
    result = _run(["checkMesh", "-latestTime"], cwd=case_path, container=container)
    return result


def run_snappyhexmesh(
    case_path: Path,
    stl_name: str,
    castellated: bool = True,
    snap: bool = True,
    add_layers: bool = True,
    parallel: bool = False,
    n_processors: int = 1,
    container: Optional[str] = None,
) -> CommandResult:
    """
    Run snappyHexMesh on a case directory.

    Args:
        case_path: Path to the case directory
        stl_name: Name of STL file in constant/triSurface/
        castellated: Run castellated mesh phase
        snap: Run snap phase
        add_layers: Run add layers phase
        parallel: Run in parallel
        n_processors: Number of processors for parallel run
        container: Docker container name to run inside
    """
    cmd = ["snappyHexMesh"]

    if not castellated and not snap and not add_layers:
        castellated = True  # at least one must be true

    if not castellated: cmd.append("-noCastellatedMesh")
    if not snap: cmd.append("-noSnap")
    if not add_layers: cmd.append("-noLayers")

    if parallel:
        cmd = ["mpirun", "-np", str(n_processors), "-parallel"] + cmd

    result = _run(cmd, cwd=case_path, container=container)
    return result


# -------------------------------------------------------------------
# Solver commands
# -------------------------------------------------------------------

def run_solver(
    case_path: Path,
    solver: str,
    parallel: bool = False,
    n_processors: int = 1,
    end_time: Optional[float] = None,
    delta_t: Optional[float] = None,
    start_time: Optional[float] = None,
    write_interval: Optional[float] = None,
    run_number: Optional[int] = None,
    timeout: Optional[int] = None,
    detach: bool = False,
    container: Optional[str] = None,
) -> CommandResult:
    """
    Run an OpenFOAM solver.

    Args:
        case_path: Path to the case directory
        solver: Solver name (e.g. 'simpleFoam', 'icoFoam', 'pimpleFoam')
        parallel: Run in parallel
        n_processors: Number of processors for parallel run
        end_time: Override endTime in controlDict
        delta_t: Override deltaT in controlDict
        start_time: Override startTime in controlDict
        write_interval: Override writeInterval in controlDict
        run_number: Pass -runNumber option
        timeout: Max seconds to run (None = no limit)
        detach: If True, run in background and return immediately
        container: Docker container name to run inside
    """
    cmd = [solver]

    if run_number is not None:
        cmd += ["-runNumber", str(run_number)]

    if parallel:
        cmd = ["mpirun", "-np", str(n_processors), "-parallel"] + cmd

    if detach:
        env_extra = {"WM_NPROCS": str(n_processors)} if parallel else {}
        if container:
            quoted = " ".join(str(c) for c in cmd)
            full = f"source /opt/openfoam10/etc/bashrc && {quoted}"
            proc = subprocess.Popen(
                ["docker", "exec", "-d", container, "bash", "-c", full],
                cwd=str(case_path), env=os.environ,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
        else:
            foam = find_openfoam()
            proc = subprocess.Popen(
                ["/bin/bash", "-c", f"source {foam.root}/etc/bashrc && " + " ".join(str(c) for c in cmd)],
                cwd=str(case_path), env=os.environ,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
        return CommandResult(success=True, output=f"Started in background (pid={proc.pid})", returncode=0)

    result = _run(cmd, cwd=case_path, timeout=timeout, container=container)
    return result


# -------------------------------------------------------------------
# Post-processing
# -------------------------------------------------------------------

def run_postprocess(
    case_path: Path,
    func: str,
    time: str = "latestTime",
    parallel: bool = False,
    container: Optional[str] = None,
) -> CommandResult:
    """
    Run postProcess with a functionObject.

    Args:
        case_path: Path to the case directory
        func: FunctionObject name (e.g. 'div(U)', 'grad(p)', 'vorticity')
        time: Time directory ('latestTime', '0', '1000', etc.)
        parallel: Whether case was run in parallel
        container: Docker container name to run inside
    """
    cmd = ["postProcess", "-func", func, "-time", time]
    if parallel:
        cmd.append("-parallel")
    result = _run(cmd, cwd=case_path, container=container)
    return result


def extract_patch_average(case_path: Path, field: str, patch: str, time: str = "latestTime",
                         container: Optional[str] = None) -> float:
    """Extract average of a field on a patch."""
    result = run_postprocess(case_path, f'patchAverage({field},{patch})', time=time, container=container)
    if not result.success:
        raise RuntimeError(f"patchAverage failed: {result.error}")
    return parse_patch_average_output(result.output, field)


def run_foam_calc(case_path: Path, expression: str,
                  container: Optional[str] = None) -> CommandResult:
    """Run foamCalc with an expression."""
    result = _run(["foamCalc", expression], cwd=case_path, container=container)
    return result


# -------------------------------------------------------------------
# Case info helpers
# -------------------------------------------------------------------

def get_latest_time(case_path: Path) -> float:
    """
    Get the latest time directory in a case.
    Returns float parsed from directory name.
    """
    time_dirs = []
    for item in case_path.iterdir():
        if item.is_dir():
            try:
                t = float(item.name)
                time_dirs.append((t, item))
            except ValueError:
                continue
    if not time_dirs:
        raise RuntimeError(f"No time directories found in {case_path}")
    time_dirs.sort(key=lambda x: x[0])
    return time_dirs[-1][0]


def get_time_dirs(case_path: Path) -> list[float]:
    """Return all time directories sorted."""
    times = []
    for item in case_path.iterdir():
        if item.is_dir():
            try:
                times.append(float(item.name))
            except ValueError:
                continue
    return sorted(times)


def check_solver_converged(log_text: str, tolerance: float = 1e-5) -> bool:
    """Check if solver appears to have converged based on residuals."""
    residuals = parse_residuals(log_text)
    if not residuals:
        return False
    return all(r < tolerance for r in residuals.values())
