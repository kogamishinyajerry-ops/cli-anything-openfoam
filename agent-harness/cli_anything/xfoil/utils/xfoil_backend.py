"""
xfoil_backend.py - XFoil CLI wrapper

Wraps real XFoil commands for use by the cli-anything harness.

XFoil is installed via:
  - macOS: brew install xfoil (or from source)
  - Linux: apt install xfoil or build from source
  - Container: pre-installed in cfd-openfoam

Principles:
  - MUST call real XFoil commands, not reimplement
  - Software is HARD dependency - error clearly if not found
  - All operations via stdin command piping (XFoil interactive)
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

XFOIL_DEFAULT_INSTALL = "/usr/local/bin/xfoil"
XFOIL_VERSION = "1.0.0"


def find_xfoil() -> Path:
    """
    Locate XFoil binary.

    Returns Path to xfoil.
    Raises RuntimeError if not found.
    """
    xfoil_bin = os.environ.get("XFOIL_PATH", XFOIL_DEFAULT_INSTALL)
    bin_path = Path(xfoil_bin)

    if not bin_path.exists():
        if os.environ.get("XFOIL_MOCK"):
            return Path("/usr/bin/true")
        raise RuntimeError(
            f"XFoil not found at {bin_path}.\n"
            f"Set XFOIL_PATH env var or install xfoil.\n"
            f"macOS: brew install xfoil\n"
            f"Linux: sudo apt install xfoil"
        )

    return bin_path


# -------------------------------------------------------------------
# Result dataclass
# -------------------------------------------------------------------

@dataclass
class CommandResult:
    """Result of an XFoil command execution."""
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
    stdin_input: Optional[str] = None,
    cwd: Optional[Path] = None,
    timeout: Optional[int] = None,
    check: bool = True,
    container: Optional[str] = None,
) -> CommandResult:
    """
    Run xfoil with optional stdin commands.

    Args:
        cmd: Command as list of strings
        stdin_input: Commands to pipe via stdin
        cwd: Working directory
        timeout: Max seconds (None = no limit)
        check: Raise on non-zero exit
        container: Docker container name

    Returns:
        CommandResult
    """
    xfoil = find_xfoil()

    docker_cmd = None
    if container:
        docker_cmd = [
            "docker", "exec", container,
            "/bin/bash", "-lc",
            f"source /opt/openfoam10/etc/bashrc 2>/dev/null || true; " +
            " ".join(f"'{c}'" for c in cmd)
        ]

    start = time.time()
    try:
        proc = subprocess.run(
            docker_cmd if container else [str(xfoil)],
            input=stdin_input,
            cwd=cwd,
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
            error=f"Command timed out after {timeout}s",
            returncode=-1,
            duration_seconds=timeout or 0,
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
# Airfoil operations
# -------------------------------------------------------------------

def load_airfoil(
    name: str,
    container: Optional[str] = None,
) -> CommandResult:
    """
    Load an airfoil by name (NACA XXXX, or known name like 'NACA0012').

    Returns CommandResult with output.
    """
    # Build xfoil command sequence
    commands = f"NACA {name}\n"

    result = _run(
        ["xfoil"],
        stdin_input=commands,
        timeout=30,
        check=False,
        container=container,
    )
    return result


def load_airfoil_from_file(
    file_path: Path,
    container: Optional[str] = None,
) -> CommandResult:
    """
    Load an airfoil from a coordinate file (.dat, .txt).

    Args:
        file_path: Path to coordinate file (Selig format)
        container: Docker container name

    Returns:
        CommandResult
    """
    file_path = Path(file_path).resolve()
    if not file_path.exists():
        return CommandResult(
            success=False,
            output="",
            error=f"Airfoil file not found: {file_path}",
            returncode=1,
        )

    # Read coordinates to determine format
    commands = f"LOAD {file_path}\n\n"

    result = _run(
        ["xfoil"],
        stdin_input=commands,
        timeout=30,
        check=False,
        container=container,
    )
    return result


# -------------------------------------------------------------------
# Polar analysis
# -------------------------------------------------------------------

def compute_polar(
    airfoil: str,
    reynolds: float,
    mach: float = 0.0,
    alpha_start: float = -5.0,
    alpha_end: float = 15.0,
    alpha_step: float = 0.5,
    container: Optional[str] = None,
) -> CommandResult:
    """
    Compute a polar for an airfoil.

    Args:
        airfoil: Airfoil name (e.g., '4412') or 'NACA XXXX'
        reynolds: Reynolds number (e.g., 3e6)
        mach: Mach number (default 0.0 for incompressible)
        alpha_start: Start angle of attack (degrees)
        alpha_end: End angle of attack
        alpha_step: Angle increment
        container: Docker container name

    Returns:
        CommandResult with full xfoil output
    """
    commands = f"""NACA {airfoil}
OPER
VISC {reynolds}
MACH {mach}
PACC
polar_{airfoil}.dat

ASEQ {alpha_start} {alpha_end} {alpha_step}
"""

    result = _run(
        ["xfoil"],
        stdin_input=commands,
        timeout=120,
        check=False,
        container=container,
    )
    return result


def compute_polar_file(
    airfoil_file: Path,
    reynolds: float,
    mach: float = 0.0,
    alpha_start: float = -5.0,
    alpha_end: float = 15.0,
    alpha_step: float = 0.5,
    container: Optional[str] = None,
) -> CommandResult:
    """
    Compute polar from airfoil coordinate file.
    """
    airfoil_file = Path(airfoil_file).resolve()
    if not airfoil_file.exists():
        return CommandResult(
            success=False,
            output="",
            error=f"Airfoil file not found: {airfoil_file}",
            returncode=1,
        )

    # XFoil expects Selig/Lednicer format
    commands = f"""LOAD {airfoil_file}

OPER
VISC {reynolds}
MACH {mach}
PACC
polar_{airfoil_file.stem}.dat

ASEQ {alpha_start} {alpha_end} {alpha_step}
"""

    result = _run(
        ["xfoil"],
        stdin_input=commands,
        timeout=120,
        check=False,
        container=container,
    )
    return result


# -------------------------------------------------------------------
# Single-point analysis
# -------------------------------------------------------------------

def analyze(
    airfoil: str,
    alpha: float,
    reynolds: float,
    mach: float = 0.0,
    container: Optional[str] = None,
) -> dict:
    """
    Analyze a single operating point.

    Returns dict with CL, CD, CDp, CM, etc.
    """
    commands = f"""NACA {airfoil}
OPER
VISC {reynolds}
MACH {mach}
ALFA {alpha}
"""

    result = _run(
        ["xfoil"],
        stdin_input=commands,
        timeout=30,
        check=False,
        container=container,
    )

    parsed = parse_analyze_output(result.output)
    parsed["success"] = result.success
    parsed["alpha"] = alpha
    parsed["reynolds"] = reynolds
    parsed["mach"] = mach
    parsed["raw_output"] = result.output[-500:]
    return parsed


# -------------------------------------------------------------------
# Output parsers
# -------------------------------------------------------------------

def parse_analyze_output(output: str) -> dict:
    """
    Parse XFoil 'ALFA' single-point output.

    Extracts: CL, CD, CDp, CM, L/D, etc.
    """
    data = {
        "CL": None,
        "CD": None,
        "CDp": None,
        "CM": None,
        "L_D": None,
        "CP_min": None,
        "-transition": None,
        "transition_nm": None,
    }

    lines = output.split("\n")
    for line in lines:
        line = line.strip()

        # CL = 0.1234
        m = re.search(r"CL\s*=\s*([-\d.e+]+)", line)
        if m:
            data["CL"] = float(m.group(1))

        # CD = 0.01234
        m = re.search(r"CD\s*=\s*([-\d.e+]+)", line)
        if m:
            data["CD"] = float(m.group(1))

        # CDp = 0.00567
        m = re.search(r"CDp\s*=\s*([-\d.e+]+)", line)
        if m:
            data["CDp"] = float(m.group(1))

        # CM = -0.0500
        m = re.search(r"CM\s*=\s*([-\d.e+]+)", line)
        if m:
            data["CM"] = float(m.group(1))

        # L/D = 12.345
        m = re.search(r"L/D\s*=\s*([-\d.e+]+)", line)
        if m:
            data["L_D"] = float(m.group(1))

        # CP_min = -0.9876
        m = re.search(r"CPmin\s*=\s*([-\d.e+]+)", line)
        if m:
            data["CP_min"] = float(m.group(1))

        # Top (n1) transition xtr = 0.1234
        m = re.search(r"Top.*transition.*=\s*([\d.e+-]+)", line)
        if m:
            data["top_transition"] = float(m.group(1))

        # Bot (n2) transition xtr = 0.5678
        m = re.search(r"Bot.*transition.*=\s*([\d.e+-]+)", line)
        if m:
            data["bot_transition"] = float(m.group(1))

    return data


def parse_polar_file(polar_file: Path) -> dict:
    """
    Parse a polar file written by XFoil.

    Returns dict with header info and data rows.
    """
    polar_file = Path(polar_file)
    if not polar_file.exists():
        return {"error": f"Polar file not found: {polar_file}", "success": False}

    text = polar_file.read_text()
    lines = text.strip().split("\n")

    # Parse header line (first comment line)
    header = ""
    data_lines = []
    for line in lines:
        if line.startswith("#"):
            header = line.lstrip("# ").strip()
        elif line.strip():
            data_lines.append(line.strip())

    # Parse data columns
    # Typical format: alpha  CL      CD      CDp     CM     Top_Xtr Bot_Xtr
    rows = []
    for line in data_lines:
        parts = line.split()
        if len(parts) >= 6:
            try:
                row = {
                    "alpha": float(parts[0]),
                    "CL": float(parts[1]),
                    "CD": float(parts[2]),
                    "CDp": float(parts[3]),
                    "CM": float(parts[4]),
                    "Top_Xtr": float(parts[5]) if len(parts) > 5 else None,
                    "Bot_Xtr": float(parts[6]) if len(parts) > 6 else None,
                }
                rows.append(row)
            except ValueError:
                continue

    return {
        "success": True,
        "header": header,
        "n_points": len(rows),
        "data": rows,
    }


def parse_polar_output(output: str) -> dict:
    """
    Parse polar data from xfoil stdout (ASEQ output block).

    Extracts: alpha, CL, CD, CDp, CM per point.
    XFoil polar output format:
      ALS   =  0.000   CL =   0.5000   CD =   0.02000   CDp =  0.01000   CM =  -0.0300
    """
    data_lines = []
    for line in output.split("\n"):
        line = line.strip()
        if not line:
            continue

        # Skip lines that are clearly not polar data
        skip_prefixes = ["XFoil", "--->", "PACC", "HARMONIC", "NACA", "LOAD",
                         "SAVE", "PROFILE", "PLOT", "PWRT", "STORE", "CASE",
                         "EXPERIMENTAL", "WINDOW", "SURFACE", "VISCAL",
                         "MASSFLOW", "RNA", "COLD"]
        if any(line.startswith(p) for p in skip_prefixes):
            continue

        # Extract values using regex (XFoil format: "ALS = value" / "CL = value")
        alpha_m = re.search(r"ALS\s*=\s*([-\d.e+]+)", line)
        cl_m = re.search(r"CL\s*=\s*([-\d.e+]+)", line)
        cd_m = re.search(r"CD\s*=\s*([-\d.e+]+)", line)
        cdp_m = re.search(r"CDp\s*=\s*([-\d.e+]+)", line)
        cm_m = re.search(r"CM\s*=\s*([-\d.e+]+)", line)

        if alpha_m and cl_m and cd_m:
            try:
                data_lines.append({
                    "alpha": float(alpha_m.group(1)),
                    "CL": float(cl_m.group(1)),
                    "CD": float(cd_m.group(1)),
                    "CDp": float(cdp_m.group(1)) if cdp_m else None,
                    "CM": float(cm_m.group(1)) if cm_m else None,
                })
            except ValueError:
                continue

    return {
        "success": len(data_lines) > 0,
        "n_points": len(data_lines),
        "data": data_lines,
    }


# -------------------------------------------------------------------
# Batch: multiple alpha points
# -------------------------------------------------------------------

def alpha_sweep(
    airfoil: str,
    reynolds: float,
    alpha_start: float,
    alpha_end: float,
    alpha_step: float,
    mach: float = 0.0,
    container: Optional[str] = None,
) -> dict:
    """
    Sweep angle of attack and return polar data.

    Args:
        airfoil: Airfoil name (e.g., '4412')
        reynolds: Reynolds number
        alpha_start: Start angle (deg)
        alpha_end: End angle
        alpha_step: Increment
        mach: Mach number
        container: Docker container name

    Returns:
        dict with polar data
    """
    commands = f"""NACA {airfoil}
OPER
VISC {reynolds}
MACH {mach}
ASEQ {alpha_start} {alpha_end} {alpha_step}
"""

    result = _run(
        ["xfoil"],
        stdin_input=commands,
        timeout=120,
        check=False,
        container=container,
    )

    parsed = parse_polar_output(result.output)

    # Also try to read polar file if it was written
    polar_file = Path(f"polar_{airfoil}.dat")
    if polar_file.exists():
        file_parsed = parse_polar_file(polar_file)
        if file_parsed["success"]:
            parsed = file_parsed

    return parsed


# -------------------------------------------------------------------
# Glance/quality check
# -------------------------------------------------------------------

def check_airfoil(
    name: str,
    container: Optional[str] = None,
) -> dict:
    """
    Quick check of an airfoil - load and show coordinates.

    Returns dict with airfoil info.
    """
    commands = f"""NACA {name}
PPAR
quit
"""

    result = _run(
        ["xfoil"],
        stdin_input=commands,
        timeout=20,
        check=False,
        container=container,
    )

    info = {
        "name": name,
        "success": result.success,
        "output": result.output,
    }

    # Extract key parameters from PPAR output
    for line in result.output.split("\n"):
        line = line.strip()
        m = re.search(r"LE\s*radius\s*=\s*([\d.e+-]+)", line)
        if m:
            info["LE_radius"] = float(m.group(1))
        m = re.search(r"thickness\s*=\s*([\d.e+-]+)\s*%\s*(?:at|x)\s*=\s*([\d.e+-]+)", line)
        if m:
            info["thickness_pct"] = float(m.group(1))
            info["thickness_x"] = float(m.group(2))
        m = re.search(r"camber\s*=\s*([\d.e+-]+)\s*%\s*(?:at|x)\s*=\s*([\d.e+-]+)", line)
        if m:
            info["camber_pct"] = float(m.group(1))
            info["camber_x"] = float(m.group(2))

    return info


# -------------------------------------------------------------------
#常见翼型预置
# -------------------------------------------------------------------

# 预置翼型数据库（常用）
AIRFOIL_PRESETS = {
    "naca0012": {"type": "NACA", "series": "00xx", "description": "Symmetric, 12% thickness"},
    "naca2412": {"type": "NACA", "series": "24xx", "description": "Cambered, 12% thickness, m=0.02"},
    "naca4412": {"type": "NACA", "series": "44xx", "description": "Cambered, 12% thickness, m=0.04"},
    "naca4415": {"type": "NACA", "series": "44xx", "description": "Cambered, 15% thickness, m=0.04"},
    "naca6409": {"type": "NACA", "series": "64xx", "description": "Cambered, 9% thickness, m=0.06"},
    "naca0015": {"type": "NACA", "series": "00xx", "description": "Symmetric, 15% thickness"},
    "naca23012": {"type": "NACA", "series": "23xx", "description": "Cambered, 12% thickness"},
    "naca23024": {"type": "NACA", "series": "23xx", "description": "Cambered, 24% thickness"},
    "goe123": {"type": "GOE", "series": "123", "description": "Göttingen empirical airfoil"},
    "e387": {"type": "Eppler", "series": "387", "description": "High-performance sailplane"},
}
