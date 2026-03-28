"""
assimp_backend.py - Assimp (Open Asset Import Library) CLI wrapper

Wraps assimp/ASSIMP tools for 3D model format conversion and inspection.

Assimp is installed via:
  - Linux: sudo apt install assimp-utils (assimp command)
  - macOS: brew install assimp
  - Windows: binaries from github.com/assimp/assimp

Key commands:
  - assimp export <input> <output>  Convert model format
  - assimp info <file>             Show model info
  - assimp listext                 List supported file formats
  - assimp version                 Show version

Principles:
  - MUST call real ASSIMP commands, not reimplement
  - Software is HARD dependency - error clearly if not found
  - Supports 40+ 3D file formats (OBJ, FBX, STL, GLTF, COLLADA, etc.)
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

ASSIMP_VERSION = "1.0.0"


# -------------------------------------------------------------------
# Installation detection
# -------------------------------------------------------------------

ASSIMP_PATHS = [
    "/usr/bin/assimp",
    "/usr/local/bin/assimp",
    "/opt/homebrew/bin/assimp",
    Path.home() / ".local/bin/assimp",
]


def find_assimp() -> Path:
    """Locate assimp binary."""
    if os.environ.get("ASSIMP_MOCK"):
        return Path("/usr/bin/true")

    assimp_bin = os.environ.get("ASSIMP_PATH")
    if assimp_bin:
        p = Path(assimp_bin)
        if p.exists():
            return p

    for candidate in ASSIMP_PATHS:
        p = Path(candidate)
        if p.exists():
            return p

    try:
        result = subprocess.run(
            ["which", "assimp"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            return Path(result.stdout.strip())
    except Exception:
        pass

    raise RuntimeError(
        "Assimp not found.\n"
        "Set ASSIMP_PATH env var or install ASSIMP.\n"
        "macOS: brew install assimp\n"
        "Linux: sudo apt install assimp-utils\n"
        "Download: https://github.com/assimp/assimp/releases"
    )


# -------------------------------------------------------------------
# Result dataclass
# -------------------------------------------------------------------

@dataclass
class CommandResult:
    """Result of an assimp command execution."""
    success: bool
    output: str = ""
    error: str = ""
    returncode: int = 0
    duration_seconds: float = 0.0


# -------------------------------------------------------------------
# Core runner
# -------------------------------------------------------------------

def _run(args: list, timeout: int = 120, check: bool = True) -> CommandResult:
    """Run assimp command."""
    assimp = find_assimp()
    cmd = [str(assimp)] + args

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
    """Get Assimp version."""
    if os.environ.get("ASSIMP_MOCK"):
        return {
            "success": True,
            "version": "5.2.5",
            "supported_formats": ["obj", "fbx", "stl", "gltf", "glb", "dae", "3ds", "ply", "blend"],
        }

    try:
        result = _run(["version"], timeout=10, check=False)
        if result.success:
            match = re.search(r"(\d+\.\d+\.\d+)", result.output)
            version = match.group(1) if match else "unknown"
            return {"success": True, "version": version}
    except Exception:
        pass

    return {"success": False, "error": "Failed to get Assimp version"}


def list_formats() -> dict:
    """List supported file formats."""
    if os.environ.get("ASSIMP_MOCK"):
        return {
            "success": True,
            "import_formats": ["obj", "fbx", "stl", "gltf", "glb", "dae", "3ds", "ply", "blend", "ifc", "x3d", "lwo"],
            "export_formats": ["obj", "fbx", "stl", "gltf", "glb", "dae", "ply", "3ds"],
        }

    result = _run(["help"], timeout=10, check=False)
    if result.success:
        output = result.output.lower()
        return {
            "success": True,
            "raw_output": result.output,
        }
    return {"success": False, "error": result.error}


def get_model_info(model_path: str) -> dict:
    """
    Get information about a 3D model.

    Returns dict with mesh count, material info, texture count, etc.
    """
    path = Path(model_path)

    if os.environ.get("ASSIMP_MOCK"):
        if not path.exists():
            return {
                "success": True,
                "path": str(path),
                "filename": path.name,
                "format": path.suffix.lstrip(".") or "stl",
                "mesh_count": 3,
                "vertex_count": 12500,
                "face_count": 8200,
                "material_count": 2,
                "texture_count": 3,
                "animation_count": 0,
                "mock": True,
            }
        return {
            "success": True,
            "path": str(path),
            "filename": path.name,
            "format": path.suffix.lstrip("."),
            "mesh_count": 3,
            "vertex_count": 12500,
            "face_count": 8200,
            "material_count": 2,
            "texture_count": 3,
            "animation_count": 0,
        }

    if not path.exists():
        return {"success": False, "error": "Model file not found: {}".format(path)}

    result = _run(["info", str(path)], timeout=30, check=False)
    if not result.success:
        return {"success": False, "error": result.error}

    info = {"success": True, "path": str(path), "filename": path.name}

    # Parse output
    for line in result.output.split("\n"):
        line = line.strip()
        if not line or ":" not in line:
            continue
        key, val = line.split(":", 1)
        key = key.strip().lower().replace(" ", "_")
        val = val.strip()
        if val.isdigit():
            info[key] = int(val)
        else:
            info[key] = val

    return info


# -------------------------------------------------------------------
# Format conversion
# -------------------------------------------------------------------

SUPPORTED_FORMATS = {
    "obj": "Wavefront OBJ",
    "fbx": "Autodesk FBX",
    "stl": "Stereolithography STL",
    "gltf": "GL Transmisson Format",
    "glb": "GL Binary",
    "dae": "COLLADA",
    "3ds": "3D Studio MAX",
    "ply": "Stanford PLY",
    "blend": "Blender",
    "ifc": "Industry Foundation Classes",
    "lwo": "LightWave Object",
    "x3d": "X3D",
    "dxf": "AutoCAD DXF",
    "off": "OFF",
    "stlb": "Binary STL",
}


def convert(
    input_path: str,
    output_path: str,
    matrix: Optional[str] = None,
    flip_normals: bool = False,
    flip_uvs: bool = False,
    process_all: bool = True,
) -> CommandResult:
    """
    Convert a 3D model from one format to another.

    Args:
        input_path: Input model file path
        output_path: Output model file path
        matrix: 4x4 transformation matrix (e.g. "1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1")
        flip_normals: Flip normal vectors
        flip_uvs: Flip UV coordinates
        process_all: Apply all processing steps

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

    if os.environ.get("ASSIMP_MOCK"):
        return CommandResult(
            success=True,
            output="Converted {} -> {}".format(inp.name, Path(output_path).name),
            returncode=0,
        )

    args = ["export", str(inp), str(output_path)]

    if matrix:
        args.extend(["--matrix", matrix])
    if flip_normals:
        args.append("--flip-normals")
    if flip_uvs:
        args.append("--flip-uvs")
    if process_all:
        args.append("--process-all")

    return _run(args, timeout=120, check=False)


def convert_batch(
    input_dir: str,
    output_dir: str,
    input_format: str,
    output_format: str,
    recursive: bool = False,
) -> CommandResult:
    """
    Batch convert all files of a given format in a directory.

    Args:
        input_dir: Input directory
        output_dir: Output directory
        input_format: Input format (e.g. 'stl', 'obj')
        output_format: Output format (e.g. 'gltf', 'fbx')
        recursive: Search subdirectories

    Returns:
        CommandResult
    """
    inp_dir = Path(input_dir)
    out_dir = Path(output_dir)

    if not inp_dir.exists():
        return CommandResult(success=False, error="Input directory not found", returncode=1)

    out_dir.mkdir(parents=True, exist_ok=True)

    pattern = "**/*." + input_format if recursive else "*." + input_format
    files = list(inp_dir.glob(pattern))

    if not files:
        return CommandResult(
            success=False,
            error="No .{f} files found in {d}".format(f=input_format, d=input_dir),
            returncode=1,
        )

    if os.environ.get("ASSIMP_MOCK"):
        return CommandResult(
            success=True,
            output="Batch converted .{f} files in {indir} to .{of} in {outdir}".format(
                f=input_format, indir=input_dir, of=output_format, outdir=output_dir
            ),
            returncode=0,
        )

    results = []
    for f in files:
        out_name = f.stem + "." + output_format
        out_path = out_dir / out_name
        result = convert(str(f), str(out_path))
        results.append({"file": f.name, "success": result.success})

    success_count = sum(1 for r in results if r["success"])
    return CommandResult(
        success=success_count == len(results),
        output="Converted {}/{} files".format(success_count, len(results)),
        returncode=0 if success_count == len(results) else 1,
    )


# -------------------------------------------------------------------
# Validation
# -------------------------------------------------------------------

def validate(input_path: str) -> dict:
    """
    Validate a 3D model file.

    Returns dict with validation results.
    """
    path = Path(input_path)
    if not path.exists():
        return {"success": False, "error": "File not found: {}".format(path)}

    info = get_model_info(str(path))
    if not info.get("success"):
        return info

    issues = []
    warnings = []

    # Check basic properties
    if info.get("mesh_count", 0) == 0:
        issues.append("No meshes found in model")
    if info.get("vertex_count", 0) == 0:
        issues.append("No vertices in model")
    if info.get("face_count", 0) == 0:
        warnings.append("No faces (empty mesh)")

    # Check file size
    size_mb = path.stat().st_size / (1024 * 1024)
    if size_mb > 500:
        warnings.append("Large file size: {:.1f} MB".format(size_mb))

    return {
        "success": len(issues) == 0,
        "path": str(path),
        "valid": len(issues) == 0,
        "issues": issues,
        "warnings": warnings,
        "info": info,
    }
