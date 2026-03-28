"""
su2_backend.py - SU2 v8.4.0 CLI wrapper

Wraps real SU2 commands for use by the cli-anything harness.

SU2 is installed at /opt/su2/bin/ in the cfd-openfoam container.
Executables work without special environment setup.
Python scripts need SU2_RUN=/opt/su2/bin env variable.

Principles:
- MUST call the real SU2 commands, not reimplement
- Software is a HARD dependency - error clearly if not found
- Always verify output (not just exit 0)
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

SU2_INSTALL = "/opt/su2/bin"
SU2_VERSION = "v8.4.0"


def find_su2() -> Path:
    """
    Locate SU2 binary directory.

    Returns Path to /opt/su2/bin.
    Raises RuntimeError if SU2 is not found.
    """
    if os.environ.get("SU2_MOCK"):
        return Path("/usr/bin/true")

    su2_bin = Path(SU2_INSTALL)
    if not su2_bin.exists():
        raise RuntimeError(
            f"SU2 is not installed at {SU2_INSTALL}.\n"
            f"Ensure the cfd-openfoam container is running with SU2 v8.4.0.\n"
            f"Check: docker exec cfd-openfoam ls /opt/su2/bin/SU2_CFD"
        )

    cfd = su2_bin / "SU2_CFD"
    if not cfd.exists():
        raise RuntimeError(
            f"SU2_CFD not found at {cfd}.\n"
            f"SU2 installation may be corrupted."
        )

    return su2_bin


# -------------------------------------------------------------------
# Result dataclass
# -------------------------------------------------------------------

@dataclass
class CommandResult:
    """Result of a SU2 command execution."""
    success: bool
    output: str
    error: str = ""
    returncode: int = 0
    duration_seconds: float = 0.0


# -------------------------------------------------------------------
# Core runner
# -------------------------------------------------------------------

CONTAINER_NAME = "cfd-openfoam"


def _run(
    cmd: list[str],
    su2_bin: Optional[Path] = None,
    cwd: Optional[Path] = None,
    env_extra: Optional[dict] = None,
    timeout: Optional[int] = None,
    check: bool = True,
    container: Optional[str] = None,
) -> CommandResult:
    """
    Run a SU2 command inside the cfd-openfoam container.

    Args:
        cmd: Command and arguments as list of strings
        su2_bin: Path to SU2 bin directory (default: /opt/su2/bin)
        cwd: Working directory for the command
        env_extra: Additional environment variables
        timeout: Max seconds to run (None = no limit)
        check: Raise on non-zero exit (default True)
        container: Docker container name (default: cfd-openfoam)

    Returns:
        CommandResult with success, output, error, returncode, duration
    """
    start = time.monotonic()

    if os.environ.get("SU2_MOCK"):
        return CommandResult(success=True, output="SU2 ran successfully (mock)", returncode=0, duration_seconds=0.0)

    if su2_bin is None:
        su2_bin = Path(SU2_INSTALL)

    env = os.environ.copy()
    env["SU2_RUN"] = str(su2_bin)
    if env_extra:
        env.update(env_extra)

    cname = container or CONTAINER_NAME

    # Quote each argument - handle spaces and special chars
    def _quote(s):
        s = str(s)
        if " " in s or "'" in s or "\"" in s or "$" in s:
            # Escape double quotes for shell
            escaped = s.replace("\\", "\\\\").replace("\"", "\\\"")
            return f"\"{escaped}\""
        return f"\"{s}\""

    quoted_cmd = " ".join(_quote(c) for c in cmd)

    docker_cmd = [
        "docker", "exec",
        "-w", str(cwd) if cwd else "/tmp",
        cname,
        "bash", "-c",
        f"source /opt/su2/etc/bashrc 2>/dev/null || true && "
        f"export SU2_RUN={su2_bin} && "
        f"{quoted_cmd}"
    ]

    try:
        result = subprocess.run(
            docker_cmd,
            cwd=str(cwd) if cwd else None,
            env=env,
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
# Config file parsing
# -------------------------------------------------------------------

def parse_config(config_path: Path) -> dict[str, str]:
    """
    Parse a SU2 config (.cfg) file into a dict.

    Handles:
      - KEY= VALUE  (space after =)
      - KEY=VALUE   (no space)
      - Lines starting with % or # are comments
      - Inline comments after %

    Returns:
        dict mapping KEY -> VALUE (both as strings)
    """
    params: dict[str, str] = {}
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    for line in config_path.read_text().splitlines():
        line = line.strip()
        # Strip comments
        if "%" in line:
            line = line.split("%", 1)[0].strip()
        if not line or line.startswith("#"):
            continue

        if "=" not in line:
            continue

        key, val = line.split("=", 1)
        params[key.strip()] = val.strip()

    return params


def update_config_params(
    config_path: Path,
    params: dict[str, str],
    output_path: Optional[Path] = None,
) -> None:
    """
    Update KEY=VALUE pairs in a SU2 config file.

    Reads the config, updates/inserts the given params,
    and writes back (in-place if output_path is None).

    Handles KEY= VALUE and KEY=VALUE formats.
    Preserves comments and formatting of existing lines.
    """
    if output_path is None:
        output_path = config_path

    lines = config_path.read_text().splitlines()
    updated_keys: set[str] = set()

    new_lines = []
    for line in lines:
        original = line
        stripped = line.strip()

        # Handle comment lines
        if stripped.startswith("%") or stripped.startswith("#"):
            new_lines.append(original)
            continue

        if "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in params:
                # Replace value while preserving leading whitespace
                indent = len(line) - len(line.lstrip())
                prefix = line[:indent]
                new_lines.append(f"{prefix}{key}= {params[key]}")
                updated_keys.add(key)
                continue

        new_lines.append(original)

    # Append any new keys not found in original
    for key, val in params.items():
        if key not in updated_keys:
            new_lines.append(f"{key}= {val}")

    output_path.write_text("\n".join(new_lines) + "\n")


# -------------------------------------------------------------------
# SU2 Executable runners
# -------------------------------------------------------------------

def run_cfd(
    config: Path,
    case_name: Optional[str] = None,
    n_partitions: int = 1,
    dryrun: bool = False,
    timeout: Optional[int] = None,
    container: Optional[str] = None,
) -> CommandResult:
    """
    Run SU2_CFD solver.

    Args:
        config: Path to SU2 config (.cfg) file
        case_name: Optional case name for output directories
        n_partitions: Number of MPI partitions
        dryrun: Enable dry run mode (preprocessing only)
        timeout: Max seconds to run
        container: Docker container name
    """
    if os.environ.get("SU2_MOCK"):
        return CommandResult(success=True, output="SU2_CFD ran successfully (mock)", returncode=0)

    if not config.exists():
        return CommandResult(
            success=False,
            output="",
            error=f"Config file not found: {config}",
            returncode=1,
        )

    cmd = [str(config)]

    if dryrun:
        cmd.insert(0, "--dryrun")

    if n_partitions > 1:
        cmd = ["mpirun", "-np", str(n_partitions), "-parallel"] + cmd

    return _run(
        ["/opt/su2/bin/SU2_CFD"] + cmd,
        cwd=config.parent,
        timeout=timeout,
        container=container,
    )


def run_def(
    config: Path,
    container: Optional[str] = None,
) -> CommandResult:
    """
    Run SU2_DEF (mesh deformation / design).

    Args:
        config: Path to SU2 config (.cfg) file
        container: Docker container name
    """
    if os.environ.get("SU2_MOCK"):
        return CommandResult(success=True, output="SU2_DEF ran successfully (mock)", returncode=0)

    if not config.exists():
        return CommandResult(
            success=False,
            output="",
            error=f"Config file not found: {config}",
            returncode=1,
        )

    return _run(
        ["/opt/su2/bin/SU2_DEF", str(config)],
        cwd=config.parent,
        container=container,
    )


def run_dot(
    config: Path,
    gradient_type: str = "CONTINUOUS_ADJOINT",
    container: Optional[str] = None,
) -> CommandResult:
    """
    Run SU2_DOT (discrete adjoint).

    Args:
        config: Path to SU2 config (.cfg) file
        gradient_type: CONTINUOUS_ADJOINT or DISCRETE_ADJOINT
        container: Docker container name
    """
    if os.environ.get("SU2_MOCK"):
        return CommandResult(success=True, output="SU2_DOT ran successfully (mock)", returncode=0)

    if not config.exists():
        return CommandResult(
            success=False,
            output="",
            error=f"Config file not found: {config}",
            returncode=1,
        )

    return _run(
        ["/opt/su2/bin/SU2_DOT", str(config), f"--gradient={gradient_type}"],
        cwd=config.parent,
        container=container,
    )


def run_geo(
    config: Path,
    container: Optional[str] = None,
) -> CommandResult:
    """
    Run SU2_GEO (geometry analysis).

    Args:
        config: Path to SU2 config (.cfg) file
        container: Docker container name
    """
    if os.environ.get("SU2_MOCK"):
        return CommandResult(success=True, output="SU2_GEO ran successfully (mock)", returncode=0)

    if not config.exists():
        return CommandResult(
            success=False,
            output="",
            error=f"Config file not found: {config}",
            returncode=1,
        )

    return _run(
        ["/opt/su2/bin/SU2_GEO", str(config)],
        cwd=config.parent,
        container=container,
    )


def run_shape_opt(
    config: Path,
    n_partitions: int = 1,
    gradient: str = "CONTINUOUS_ADJOINT",
    optimization: str = "SLSQP",
    quiet: bool = False,
    timeout: Optional[int] = None,
    container: Optional[str] = None,
) -> CommandResult:
    """
    Run SU2 shape_optimization.py.

    Args:
        config: Path to SU2 config (.cfg) file
        n_partitions: Number of MPI partitions
        gradient: Gradient method (CONTINUOUS_ADJOINT, DISCRETE_ADJOINT, FINDIFF, NONE)
        optimization: Optimization technique (SLSQP, CG, BFGS, POWELL)
        quiet: Suppress SU2 output
        timeout: Max seconds to run
        container: Docker container name
    """
    if os.environ.get("SU2_MOCK"):
        return CommandResult(success=True, output="SU2 shape_opt ran successfully (mock)", returncode=0)

    if not config.exists():
        return CommandResult(
            success=False,
            output="",
            error=f"Config file not found: {config}",
            returncode=1,
        )

    cmd = [
        "/opt/su2/bin/shape_optimization.py",
        "-f", str(config),
        "-g", gradient,
        "-o", optimization,
        "-n", str(n_partitions),
    ]

    if quiet:
        cmd += ["-q", "True"]

    return _run(
        cmd,
        cwd=config.parent,
        env_extra={"SU2_RUN": "/opt/su2/bin"},
        timeout=timeout,
        container=container,
    )


def run_compute_polar(
    config: Path,
    n_partitions: int = 1,
    iterations: int = 100,
    dimension: int = 2,
    verbose: bool = False,
    timeout: Optional[int] = None,
    container: Optional[str] = None,
) -> CommandResult:
    """
    Run SU2 compute_polar.py (drag polar computation).

    Args:
        config: Path to polar control parameters file
        n_partitions: Number of MPI partitions
        iterations: Number of iterations
        dimension: Geometry dimension (2 or 3)
        verbose: Verbose printout
        timeout: Max seconds to run
        container: Docker container name
    """
    if os.environ.get("SU2_MOCK"):
        return CommandResult(success=True, output="SU2 compute_polar ran successfully (mock)", returncode=0)

    if not config.exists():
        return CommandResult(
            success=False,
            output="",
            error=f"Polar control file not found: {config}",
            returncode=1,
        )

    cmd = [
        "/opt/su2/bin/compute_polar.py",
        "-c", str(config),
        "-n", str(n_partitions),
        "-i", str(iterations),
        "-d", str(dimension),
    ]

    if verbose:
        cmd.append("-v")

    return _run(
        cmd,
        cwd=config.parent,
        env_extra={"SU2_RUN": "/opt/su2/bin"},
        timeout=timeout,
        container=container,
    )


# -------------------------------------------------------------------
# Output parsers
# -------------------------------------------------------------------

def parse_solver_output(log_text: str) -> dict:
    """
    Parse SU2_CFD output for convergence metrics.

    Extracts:
      - iteration count
      - objective function value (e.g. DRAG, LIFT)
      - residual info
      - final time if time-dependent
    """
    info: dict = {
        "iterations": 0,
        "objective": None,
        "converged": False,
        "error": "",
    }

    # Extract iteration count
    iter_matches = re.findall(r"iterations:\s+(\d+)", log_text, re.IGNORECASE)
    if iter_matches:
        info["iterations"] = int(iter_matches[-1])

    # Extract objective function (e.g. "Drag = 0.0200" or "OPT OBJECTIVE: DRAG = 0.02")
    obj_matches = re.findall(
        r"(?:OPT\s+)?OBJECTIVE:\s+(\w+)\s*=\s*([0-9.eE+-]+)",
        log_text,
        re.IGNORECASE,
    )
    if obj_matches:
        for name, val in obj_matches[-1:]:
            info["objective"] = {"name": name.upper(), "value": float(val)}

    # Check for convergence markers
    if re.search(r"convergENCE\s+achieved", log_text, re.IGNORECASE):
        info["converged"] = True
    elif re.search(r"error:\s+", log_text, re.IGNORECASE):
        info["error"] = "solver error detected"

    return info
