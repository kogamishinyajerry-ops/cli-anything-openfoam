"""
usd_backend.py - Universal Scene Description (USD) CLI wrapper

Wraps Pixar's USD tools for 3D scene description format conversion and inspection.

USD is installed via:
  - macOS: brew install usd
  - Linux: build from source or use pip install usd

Key commands:
  - usdcat          Convert USD files between formats (usda, usdc, usdz)
  - usdchecker      Validate USD files
  - usdview         View USD files (GUI)
  - usddump         Dump USD stage info

Principles:
  - MOCK FIRST pattern: check USD_MOCK env var before any operation
  - Existence check AFTER mock check
  - Software is HARD dependency - error clearly if not found (real mode)
  - Supports usda (ASCII), usdc (binary), usdz (package) formats
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
# Version
# -------------------------------------------------------------------

USD_VERSION = "1.0.0"


# -------------------------------------------------------------------
# Installation detection
# -------------------------------------------------------------------

USD_COMMON_PATHS = [
    "/usr/bin/usdcat",
    "/usr/local/bin/usdcat",
    "/opt/homebrew/bin/usdcat",
]


def find_usdcat() -> Path:
    """Locate usdcat binary."""
    # MOCK FIRST
    if os.environ.get("USD_MOCK"):
        return Path("/usr/bin/true")

    # Check env var
    usd_bin = os.environ.get("USD_BIN_PATH")
    if usd_bin:
        p = Path(usd_bin) / "usdcat"
        if p.exists():
            return p

    # Check common paths
    for candidate in USD_COMMON_PATHS:
        p = Path(candidate)
        if p.exists():
            return p

    raise RuntimeError(
        "usdcat not found.\n"
        "Set USD_BIN_PATH env var or install USD.\n"
        "macOS: brew install usd\n"
        "Download: https://github.com/PixarAnimationStudios/USD"
    )


def find_usdchecker() -> Path:
    """Locate usdchecker binary."""
    # MOCK FIRST
    if os.environ.get("USD_MOCK"):
        return Path("/usr/bin/true")

    # Check env var
    usd_bin = os.environ.get("USD_BIN_PATH")
    if usd_bin:
        p = Path(usd_bin) / "usdchecker"
        if p.exists():
            return p

    # Check common paths with usd prefix
    usd_paths = [
        "/usr/bin/usdchecker",
        "/usr/local/bin/usdchecker",
        "/opt/homebrew/bin/usdchecker",
    ]
    for candidate in usd_paths:
        p = Path(candidate)
        if p.exists():
            return p

    raise RuntimeError(
        "usdchecker not found.\n"
        "Set USD_BIN_PATH env var or install USD.\n"
        "macOS: brew install usd\n"
        "Download: https://github.com/PixarAnimationStudios/USD"
    )


# -------------------------------------------------------------------
# Result dataclass
# -------------------------------------------------------------------

@dataclass
class CommandResult:
    """Result of a USD command execution."""
    success: bool
    output: str = ""
    error: str = ""
    returncode: int = 0
    duration_seconds: float = 0.0


# -------------------------------------------------------------------
# Core runner
# -------------------------------------------------------------------

def _run(args: list, timeout: int = 120, check: bool = True) -> CommandResult:
    """Run USD command."""
    start = time.time()
    try:
        proc = subprocess.run(
            args,
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
    """Get USD version."""
    # MOCK FIRST
    if os.environ.get("USD_MOCK"):
        return {
            "success": True,
            "version": "USD 23.05",
        }

    try:
        usdcat = find_usdcat()
        result = _run([str(usdcat), "--version"], timeout=10, check=False)
        if result.success:
            # Parse version from output like "usdcat version 23.05"
            match = re.search(r"(\d+\.\d+)", result.output)
            version = match.group(1) if match else result.output.strip()
            return {"success": True, "version": "USD " + version}
    except Exception:
        pass

    return {"success": False, "error": "Failed to get USD version"}


def validate_usd(usd_file: str) -> CommandResult:
    """
    Validate a USD file using usdchecker.

    Args:
        usd_file: Path to USD file to validate

    Returns:
        CommandResult
    """
    p = Path(usd_file)

    # MOCK FIRST
    if os.environ.get("USD_MOCK"):
        return CommandResult(
            success=True,
            output="Mock validation: {} is valid".format(p.name),
            returncode=0,
        )

    # EXISTENCE CHECK
    if not p.exists():
        return CommandResult(
            success=False,
            error="File not found: {}".format(p),
            returncode=1,
        )

    # REAL IMPLEMENTATION
    usdchecker = find_usdchecker()
    return _run([str(usdchecker), str(p)], timeout=60, check=False)


def usd_info(usd_file: str) -> dict:
    """
    Get information about a USD stage.

    Args:
        usd_file: Path to USD file

    Returns:
        dict with stage info (prims, layers, etc.)
    """
    p = Path(usd_file)

    # MOCK FIRST
    if os.environ.get("USD_MOCK"):
        return {
            "success": True,
            "path": str(p),
            "filename": p.name,
            "stage": "mock_stage",
            "prims": ["Root", "World", "Mesh", "Material"],
            "layers": ["mock_layer.usda", "sub_layer.usda"],
            "prim_count": 4,
            "layer_count": 2,
            "mock": True,
        }

    # EXISTENCE CHECK
    if not p.exists():
        return {"success": False, "error": "File not found: {}".format(p)}

    # REAL IMPLEMENTATION
    usdcat = find_usdcat()
    result = _run([str(usdcat), "-dump", str(p)], timeout=30, check=False)

    if not result.success:
        return {"success": False, "error": result.error}

    info = {
        "success": True,
        "path": str(p),
        "filename": p.name,
        "raw_output": result.output,
    }

    # Parse output for prims and layers
    prims = []
    layers = []
    for line in result.output.split("\n"):
        line = line.strip()
        if line.startswith("def "):
            # Extract prim name
            parts = line.split(" ", 2)
            if len(parts) >= 3:
                prims.append(parts[2])
        elif line.startswith("<Layer "):
            # Extract layer name
            match = re.search(r"(\S+\.usd\S*)", line)
            if match:
                layers.append(match.group(1))

    info["prims"] = prims
    info["layers"] = layers
    info["prim_count"] = len(prims)
    info["layer_count"] = len(layers)

    return info


def convert_usd(input_file: str, output_file: str, format: str) -> CommandResult:
    """
    Convert a USD file to another format.

    Args:
        input_file: Input USD file path
        output_file: Output USD file path
        format: Target format (usda, usdc, usdz)

    Returns:
        CommandResult
    """
    inp = Path(input_file)
    out = Path(output_file)

    # EXISTENCE CHECK FIRST
    if not inp.exists():
        return CommandResult(
            success=False,
            error="Input file not found: {}".format(inp),
            returncode=1,
        )

    # MOCK FIRST
    if os.environ.get("USD_MOCK"):
        return CommandResult(
            success=True,
            output="Converted {} -> {} ({})".format(inp.name, out.name, format),
            returncode=0,
        )

    # REAL IMPLEMENTATION
    usdcat = find_usdcat()

    # Determine format-specific flags
    if format == "usda":
        args = [str(usdcat), "-a", str(inp), "-o", str(out)]
    elif format == "usdc":
        args = [str(usdcat), "-d", str(inp), "-o", str(out)]
    elif format == "usdz":
        args = [str(usdcat), "-z", str(inp), "-o", str(out)]
    else:
        return CommandResult(
            success=False,
            error="Unsupported format: {}. Use usda, usdc, or usdz".format(format),
            returncode=1,
        )

    return _run(args, timeout=120, check=False)


def list_layers(usd_file: str) -> dict:
    """
    List all layers in a USD file.

    Args:
        usd_file: Path to USD file

    Returns:
        dict with layer information
    """
    p = Path(usd_file)

    # MOCK FIRST
    if os.environ.get("USD_MOCK"):
        return {
            "success": True,
            "path": str(p),
            "filename": p.name,
            "layers": [
                {"name": "mock_layer.usda", "path": "/layers/mock_layer.usda"},
                {"name": "sub_layer.usda", "path": "/layers/sub_layer.usda"},
            ],
            "layer_count": 2,
            "mock": True,
        }

    # EXISTENCE CHECK
    if not p.exists():
        return {"success": False, "error": "File not found: {}".format(p)}

    # REAL IMPLEMENTATION
    usdcat = find_usdcat()
    result = _run([str(usdcat), "-l", str(p)], timeout=30, check=False)

    if not result.success:
        return {"success": False, "error": result.error}

    layers = []
    for line in result.output.split("\n"):
        line = line.strip()
        if not line:
            continue
        # Parse layer paths from usdcat -l output
        if line.startswith("/") or line.endswith(".usda") or line.endswith(".usdc"):
            layers.append({"name": Path(line).name, "path": line})

    return {
        "success": True,
        "path": str(p),
        "filename": p.name,
        "layers": layers,
        "layer_count": len(layers),
    }
