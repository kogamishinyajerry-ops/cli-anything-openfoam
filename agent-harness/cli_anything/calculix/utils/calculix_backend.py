"""
calculix_backend.py - Calculix CLI wrapper

Wraps CalculiX solver (ccx) and preprocessor (cgx) commands.

Calculix is installed via:
  - Linux: packages from calculix.de or compile from source
  - No official macOS release (compile withbrew)

Executables:
  - ccx: Solver (linear static, modal, buckling, thermal)
  - cgx: Preprocessor/visualizer (similar to Abaqus/CAE)

Principles:
  - MUST call real Calculix commands, not reimplement
  - Software is HARD dependency - error clearly if not found
  - Uses .inp (ABAQUS) format for model data
  - Solver output is text-based (.dat, .frd for results)
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

CALCULIX_VERSION = "1.0.0"


# -------------------------------------------------------------------
# Installation detection
# -------------------------------------------------------------------

CCX_PATHS = [
    "/usr/local/bin/ccx",
    "/usr/bin/ccx",
    Path.home() / ".local/bin/ccx",
]

CGX_PATHS = [
    "/usr/local/bin/cgx",
    "/usr/bin/cgx",
    Path.home() / ".local/bin/cgx",
]


def find_ccx() -> Path:
    """Locate ccx (Calculix solver) binary."""
    if os.environ.get("CALCULIX_MOCK"):
        return Path("/usr/bin/true")

    ccx_path = os.environ.get("CCX_PATH")
    if ccx_path:
        p = Path(ccx_path)
        if p.exists():
            return p

    for candidate in CCX_PATHS:
        p = Path(candidate)
        if p.exists():
            return p

    try:
        result = subprocess.run(
            ["which", "ccx"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            return Path(result.stdout.strip())
    except Exception:
        pass

    raise RuntimeError(
        "Calculix (ccx) not found.\n"
        "Set CCX_PATH env var or install CalculiX.\n"
        "Download: https://calculix.de/download.html\n"
        "Linux: sudo apt install calculix-ccx"
    )


def find_cgx() -> Path:
    """Locate cgx (Calculix preprocessor) binary."""
    if os.environ.get("CALCULIX_MOCK"):
        return Path("/usr/bin/true")

    cgx_path = os.environ.get("CGX_PATH")
    if cgx_path:
        p = Path(cgx_path)
        if p.exists():
            return p

    for candidate in CGX_PATHS:
        p = Path(candidate)
        if p.exists():
            return p

    try:
        result = subprocess.run(
            ["which", "cgx"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            return Path(result.stdout.strip())
    except Exception:
        pass

    raise RuntimeError(
        "Calculix preprocessor (cgx) not found.\n"
        "Set CGX_PATH env var or install CalculiX cgx.\n"
        "Download: https://calculix.de/download.html"
    )


# -------------------------------------------------------------------
# Result dataclass
# -------------------------------------------------------------------

@dataclass
class CommandResult:
    """Result of a Calculix command execution."""
    success: bool
    output: str = ""
    error: str = ""
    returncode: int = 0
    duration_seconds: float = 0.0


# -------------------------------------------------------------------
# Core runner
# -------------------------------------------------------------------

def _run_ccx(
    args: list,
    inp_path: str,
    timeout: int = 300,
    check: bool = True,
) -> CommandResult:
    """Run ccx solver."""
    ccx = find_ccx()
    actual_cmd = [str(ccx), "-i", str(Path(inp_path).with_suffix("").name)]
    if args:
        actual_cmd.extend(args)

    inp_file = Path(inp_path)
    cwd = inp_file.parent.resolve()

    start = time.time()
    try:
        proc = subprocess.run(
            actual_cmd,
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
            error="Solver timed out after {}s".format(timeout),
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
    """Get Calculix version."""
    if os.environ.get("CALCULIX_MOCK"):
        return {
            "success": True,
            "version": "2.21",
            "solver": "ccx",
            "preprocessor": "cgx",
        }

    try:
        ccx = find_ccx()
        result = subprocess.run(
            [str(ccx), "-v"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            version_str = result.stdout.strip()
            return {
                "success": True,
                "version": version_str,
                "solver": "ccx",
                "preprocessor": "cgx",
            }
    except Exception:
        pass

    return {"success": False, "error": "Failed to get Calculix version"}


# -------------------------------------------------------------------
# Input file operations
# -------------------------------------------------------------------

def create_static_input(
    output_path: str,
    title: str = "Calculix Static Analysis",
    nodes: Optional[list] = None,
    elements: Optional[list] = None,
    materials: Optional[dict] = None,
    steps: Optional[list] = None,
) -> CommandResult:
    """
    Create a basic static analysis .inp file.

    Args:
        output_path: Output .inp file path
        title: Analysis title
        nodes: List of (node_id, x, y, z)
        elements: List of (elem_id, elem_type, *node_ids)
        materials: {"name": "Steel", "E": 210000, "nu": 0.3, "rho": 7.85e-9}
        steps: List of step definitions

    Returns:
        CommandResult
    """
    path = Path(output_path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)

    lines = []
    lines.append("*HEADING")
    lines.append(title)
    lines.append("")

    # Nodes
    if nodes:
        lines.append("*NODE")
        for nid, x, y, z in nodes:
            lines.append("{} {}, {}, {}".format(nid, x, y, z))
        lines.append("")

    # Elements (default to C3D8R if not specified)
    if elements:
        for elem_id, elem_type, *node_ids in elements:
            lines.append("*{}".format(elem_type))
            lines.append("{}, INTERNAL, 1".format(elem_id))
            lines.append(", ".join(str(n) for n in node_ids))
        lines.append("")

    # Material
    if materials:
        lines.append("*MATERIAL, NAME={}".format(materials.get("name", "MAT1")))
        e = materials.get("E", 210000)
        nu = materials.get("nu", 0.3)
        rho = materials.get("rho", 7.85e-9)
        lines.append("*ELASTIC")
        lines.append("{}, {}".format(e, nu))
        lines.append("*DENSITY")
        lines.append("{}".format(rho))
        lines.append("")
    else:
        # Default steel
        lines.append("*MATERIAL, NAME=Steel")
        lines.append("*ELASTIC")
        lines.append("210000, 0.3")
        lines.append("*DENSITY")
        lines.append("7.85E-9")
        lines.append("")

    # Boundary (default: fixed at node 1)
    lines.append("*BOUNDARY")
    lines.append("1, 1, 3, 0.0")
    lines.append("")

    # Step (default: static load)
    lines.append("*STEP")
    lines.append("*STATIC")
    lines.append("0.1, 1.0")
    lines.append("*CLOAD")
    lines.append("2, 2, 1.0")
    lines.append("*NODE FILE, OUTPUT=3D")
    lines.append("U")
    lines.append("*EL FILE")
    lines.append("S")
    lines.append("*END STEP")
    lines.append("")

    path.write_text("\n".join(lines))

    return CommandResult(
        success=True,
        output="Created input file: {}".format(path),
        returncode=0,
    )


def read_inp_info(inp_path: str) -> dict:
    """
    Read and parse .inp file info.

    Returns:
        dict with model info
    """
    path = Path(inp_path)
    if not path.exists():
        return {"success": False, "error": "Input file not found: {}".format(path)}

    try:
        content = path.read_text()

        # Count nodes and elements
        node_count = 0
        elem_count = 0
        materials = []
        has_thermal = False

        for line in content.split("\n"):
            line = line.strip()
            if line.startswith("*NODE"):
                # Count subsequent lines until * or blank
                pass
            elif line.startswith("*ELEMENT"):
                elem_count += 1
            elif line.startswith("*MATERIAL"):
                m = line.split("=")[1].split(",")[0].strip() if "=" in line else "UNKNOWN"
                materials.append(m)
            elif line.startswith("*THERMAL"):
                has_thermal = True

        # Count node lines
        in_node_section = False
        for line in content.split("\n"):
            stripped = line.strip()
            if stripped.startswith("*NODE"):
                in_node_section = True
                continue
            if in_node_section:
                if stripped.startswith("*") or not stripped:
                    in_node_section = False
                    continue
                if stripped and not stripped.startswith("*"):
                    node_count += 1

        return {
            "success": True,
            "path": str(path),
            "title": content.split("\n")[1].strip() if len(content.split("\n")) > 1 else "Unknown",
            "node_count": node_count,
            "element_count": elem_count,
            "materials": materials,
            "has_thermal": has_thermal,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# -------------------------------------------------------------------
# Solve
# -------------------------------------------------------------------

def solve(
    input_path: str,
    output_name: Optional[str] = None,
    step: Optional[int] = None,
    mode: str = "static",
    timeout: int = 300,
) -> CommandResult:
    """
    Run Calculix solver.

    Args:
        input_path: Path to .inp file
        output_name: Custom output base name
        step: Specific step to solve
        mode: 'static', 'thermal', 'modal', 'buckle'
        timeout: Max seconds

    Returns:
        CommandResult
    """
    inp = Path(input_path)
    if not inp.exists():
        return CommandResult(
            success=False,
            error="Input file not found: {}".format(inp),
            returncode=1,
        )

    if os.environ.get("CALCULIX_MOCK"):
        return CommandResult(
            success=True,
            output="Calculix solver finished (mock mode)\nJob: {} completed".format(inp.stem),
            returncode=0,
        )

    # Build ccx arguments
    args = []
    if output_name:
        args.extend(["-o", output_name])
    if step is not None:
        args.extend(["-step", str(step)])

    # Mode-specific arguments
    if mode == "thermal":
        args.append("-thermal")

    return _run_ccx(args, str(inp), timeout=timeout, check=False)


def solve_modal(
    input_path: str,
    modes: int = 10,
    timeout: int = 300,
) -> CommandResult:
    """
    Run modal analysis.

    Args:
        input_path: Path to .inp file
        modes: Number of modes to extract
        timeout: Max seconds

    Returns:
        CommandResult
    """
    inp = Path(input_path)
    if not inp.exists():
        return CommandResult(
            success=False,
            error="Input file not found: {}".format(inp),
            returncode=1,
        )

    if os.environ.get("CALCULIX_MOCK"):
        mock_freqs = [float(i * 12.5) for i in range(1, modes + 1)]
        output = "Modal Analysis Results (mock)\n"
        output += "Mode | Frequency (Hz)\n"
        for i, freq in enumerate(mock_freqs, 1):
            output += "  {}  |  {:.2f}\n".format(i, freq)
        return CommandResult(success=True, output=output, returncode=0)

    # Modal analysis via *MODAL DYNAMIC or *BUCKLE
    # For simplicity, use direct solver with PARDISO
    script = inp.read_text()
    if "*STEP" not in script and "*MODAL" not in script:
        # Inject modal step
        modal_script = (
            script.rstrip() + "\n"
            "*MODAL DYNAMIC\n"
            "1, {}, 0.0, 1.0\n"
            "*END STEP\n"
        ).format(modes)
        tmp_inp = inp.parent / (inp.stem + "_modal.inp")
        tmp_inp.write_text(modal_script)
        inp = tmp_inp

    result = _run_ccx(["-modal"], str(inp), timeout=timeout, check=False)
    return result


# -------------------------------------------------------------------
# Results parsing
# -------------------------------------------------------------------

def read_dat_file(dat_path: str) -> dict:
    """
    Read and parse .dat results file.

    Returns:
        dict with parsed results
    """
    path = Path(dat_path)
    if not path.exists():
        return {"success": False, "error": "Results file not found: {}".format(path)}

    try:
        content = path.read_text()

        # Parse displacements at nodes
        displacements = []
        stresses = []
        reactions = []

        in_disp = False
        in_stress = False

        for line in content.split("\n"):
            stripped = line.strip()

            # Detect displacement section
            if "DISPLACEMENTS" in line.upper():
                in_disp = True
                in_stress = False
                continue
            # Detect stress section
            if "STRESSES" in line.upper():
                in_stress = True
                in_disp = False
                continue
            # Section end (only on * heading, not blank lines which may precede data)
            if stripped.startswith("*"):
                in_disp = False
                in_stress = False
                continue

            # Parse data lines (typically: node, x, y, z, or component values)
            parts = [p.strip() for p in line.split() if p.strip()]
            if len(parts) >= 4:
                try:
                    if in_disp:
                        displacements.append({
                            "node": int(float(parts[0])),
                            "u1": float(parts[1]),
                            "u2": float(parts[2]),
                            "u3": float(parts[3]),
                        })
                    elif in_stress and len(parts) >= 7:
                        stresses.append({
                            "element": int(float(parts[0])),
                            "s11": float(parts[1]),
                            "s22": float(parts[2]),
                            "s33": float(parts[3]),
                            "s12": float(parts[4]),
                            "s13": float(parts[5]),
                            "s23": float(parts[6]),
                        })
                except (ValueError, IndexError):
                    pass

        return {
            "success": True,
            "path": str(path),
            "displacements": displacements,
            "stresses": stresses,
            "node_count": len(displacements),
            "element_count": len(stresses),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def read_frd_file(frd_path: str) -> dict:
    """
    Read Calculix .frd results file (binary/compressed).

    This is a simplified parser - full FRD parsing requires
    the CGX binary or dedicated library.

    Returns:
        dict with FRD info
    """
    path = Path(frd_path)
    if not path.exists():
        return {"success": False, "error": "FRD file not found: {}".format(path)}

    if os.environ.get("CALCULIX_MOCK"):
        return {
            "success": True,
            "path": str(path),
            "format": "FRD",
            "note": "FRD parsing requires CGX binary for full decode",
            "mock_data": True,
        }

    # Try to read as text (FRD is often ASCII)
    try:
        content = path.read_text(errors="replace")
        size = len(content)

        # Simple check for FRD header
        if "100CL" in content or "DISP" in content:
            return {
                "success": True,
                "path": str(path),
                "format": "FRD (ASCII)",
                "size_bytes": size,
            }
    except Exception:
        pass

    return {
        "success": True,
        "path": str(path),
        "format": "FRD (binary/compressed)",
        "note": "Binary FRD - use cgx to visualize",
    }


# -------------------------------------------------------------------
# Export
# -------------------------------------------------------------------

def export_to_vtk(
    dat_path: str,
    output_path: str,
) -> CommandResult:
    """
    Export results to VTK format for ParaView.

    Args:
        dat_path: Path to .dat results file
        output_path: Output .vtk file path

    Returns:
        CommandResult
    """
    dat = Path(dat_path)
    if not dat.exists():
        return CommandResult(
            success=False,
            error="DAT file not found: {}".format(dat),
            returncode=1,
        )

    if os.environ.get("CALCULIX_MOCK"):
        Path(output_path).write_text("# VTK Mock file\n")
        return CommandResult(
            success=True,
            output="Exported to VTK: {}".format(output_path),
            returncode=0,
        )

    # Use ccx2vtk if available, otherwise use Python script
    try:
        result = subprocess.run(
            ["which", "ccx2vtk"],
            capture_output=True,
            timeout=5,
        )
        if result.returncode == 0:
            proc = subprocess.run(
                ["ccx2vtk", str(dat.with_suffix("")), "-o", str(Path(output_path).with_suffix(""))],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if proc.returncode == 0:
                return CommandResult(
                    success=True,
                    output="Exported to VTK: {}".format(output_path),
                    returncode=0,
                )
    except Exception:
        pass

    # Fallback: simple Python-based conversion
    dat_info = read_dat_file(str(dat))
    if not dat_info.get("success"):
        return CommandResult(success=False, error=dat_info.get("error", "Failed to read DAT"))

    vtk_lines = [
        "# vtk DataFile Version 3.0",
        "Calculix Results",
        "ASCII",
        "DATASET UNSTRUCTURED_GRID",
        "",
    ]

    nodes = dat_info.get("displacements", [])
    if nodes:
        vtk_lines.append("POINTS {} float".format(len(nodes)))
        for n in nodes:
            vtk_lines.append("{:.6f} {:.6f} {:.6f}".format(n["u1"], n["u2"], n["u3"]))
        vtk_lines.append("")

    Path(output_path).write_text("\n".join(vtk_lines))
    return CommandResult(
        success=True,
        output="Exported to VTK: {}".format(output_path),
        returncode=0,
    )


# -------------------------------------------------------------------
# Template input files
# -------------------------------------------------------------------

def get_template_info() -> dict:
    """Get info about available analysis templates."""
    return {
        "success": True,
        "templates": [
            {
                "type": "static",
                "name": "Linear Static",
                "description": "Standard static structural analysis",
                "step_type": "*STATIC",
            },
            {
                "type": "modal",
                "name": "Modal Analysis",
                "description": "Natural frequency extraction",
                "step_type": "*MODAL DYNAMIC",
            },
            {
                "type": "thermal",
                "name": "Steady-State Thermal",
                "description": "Heat transfer analysis",
                "step_type": "*HEAT TRANSFER",
            },
        ],
    }
