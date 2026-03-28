"""
gltf_backend.py - glTF CLI wrapper

Wraps glTF operations for use by the cli-anything harness.

glTF (Graphics Library Transmission Format) is a runtime 3D asset
delivery format. This harness provides conversion and validation
operations for glTF (JSON) and GLB (binary) formats.

Principles:
  - Supports glTF 2.0 JSON and binary (GLB) formats
  - Uses Python stdlib json for parsing/serialization
  - Mock mode for testing without real glTF tools
"""

from __future__ import annotations

import json
import os
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


# -------------------------------------------------------------------
# Version
# -------------------------------------------------------------------

GLTF_VERSION = "1.0.0"


# -------------------------------------------------------------------
# Result dataclass
# -------------------------------------------------------------------

@dataclass
class CommandResult:
    """Result of a glTF command execution."""
    success: bool
    output: str = ""
    error: str = ""
    returncode: int = 0
    duration_seconds: float = 0.0


# -------------------------------------------------------------------
# Installation detection
# -------------------------------------------------------------------

def find_gltf() -> Path:
    """
    Locate glTF tool.

    Since there's no dedicated glTF CLI tool on this system,
    returns a Path pointing to /usr/bin/python3 as a stand-in (no-op).

    Returns:
        Path to python3 (stand-in)
    """
    if os.environ.get("GLTF_MOCK"):
        return Path("/usr/bin/true")

    # No real glTF CLI tool available - return python3 as stand-in
    python_path = Path("/usr/bin/python3")
    if python_path.exists():
        return python_path

    # Fallback
    return Path("/usr/bin/true")


# -------------------------------------------------------------------
# Version / Info
# -------------------------------------------------------------------

def get_version() -> dict:
    """
    Get glTF version information.

    Returns:
        dict with version info
    """
    if os.environ.get("GLTF_MOCK"):
        return {
            "success": True,
            "version": "glTF 2.0",
            "tool": "python-json",
        }

    return {
        "success": True,
        "version": "glTF 2.0",
        "tool": "system",
    }


# -------------------------------------------------------------------
# Validation
# -------------------------------------------------------------------

def validate_gltf(gltf_path: str) -> CommandResult:
    """
    Validate a glTF/GLB file.

    Args:
        gltf_path: Path to glTF (JSON) or GLB file

    Returns:
        CommandResult with validation status
    """
    if os.environ.get("GLTF_MOCK"):
        return CommandResult(success=True, output="glTF file is valid", returncode=0)

    path = Path(gltf_path)
    if not path.exists():
        return CommandResult(
            success=False,
            error=f"File not found: {gltf_path}",
            returncode=1,
        )

    # Determine if GLB or glTF by extension
    if path.suffix.lower() == ".glb":
        return _validate_glb(path)
    else:
        return _validate_gltf_json(path)


def _validate_gltf_json(path: Path) -> CommandResult:
    """Validate a glTF JSON file."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Check for required glTF 2.0 fields
        if "asset" not in data:
            return CommandResult(
                success=False,
                error="Missing required 'asset' field",
                returncode=1,
            )

        asset = data.get("asset", {})
        version = asset.get("version")
        if not version:
            return CommandResult(
                success=False,
                error="Missing required 'asset.version' field",
                returncode=1,
            )

        # glTF 2.0 uses version "2.0"
        if version != "2.0":
            return CommandResult(
                success=False,
                error=f"Unsupported glTF version: {version} (expected 2.0)",
                returncode=1,
            )

        return CommandResult(
            success=True,
            output=f"Valid glTF 2.0 file: {path.name}",
            returncode=0,
        )

    except json.JSONDecodeError as e:
        return CommandResult(
            success=False,
            error=f"Invalid JSON: {e}",
            returncode=1,
        )
    except Exception as e:
        return CommandResult(
            success=False,
            error=f"Validation error: {e}",
            returncode=1,
        )


def _validate_glb(path: Path) -> CommandResult:
    """Validate a GLB binary file."""
    try:
        with open(path, "rb") as f:
            # GLB header: magic (4 bytes), version (4 bytes), length (4 bytes)
            magic = f.read(4)
            if len(magic) < 4:
                return CommandResult(success=False, error="File too short", returncode=1)

            # magic should be 0x46546C67 (ASCII "glTF")
            if struct.unpack("<I", magic)[0] != 0x46546C67:
                return CommandResult(
                    success=False,
                    error="Invalid GLB magic number",
                    returncode=1,
                )

            version = struct.unpack("<I", f.read(4))[0]
            if version != 2:
                return CommandResult(
                    success=False,
                    error=f"Unsupported GLB version: {version} (expected 2)",
                    returncode=1,
                )

            length = struct.unpack("<I", f.read(4))[0]

            # Read JSON chunk
            chunk_length = struct.unpack("<I", f.read(4))[0]
            chunk_type = struct.unpack("<I", f.read(4))[0]
            if chunk_type != 0x4E4F534A:  # "JSON"
                return CommandResult(
                    success=False,
                    error="First chunk is not JSON",
                    returncode=1,
                )

            json_data = f.read(chunk_length)
            json.loads(json_data.decode("utf-8"))

            return CommandResult(
                success=True,
                output=f"Valid GLB file: {path.name}",
                returncode=0,
            )

    except struct.error as e:
        return CommandResult(success=False, error=f"Invalid GLB structure: {e}", returncode=1)
    except json.JSONDecodeError as e:
        return CommandResult(success=False, error=f"Invalid JSON in GLB: {e}", returncode=1)
    except Exception as e:
        return CommandResult(success=False, error=f"Validation error: {e}", returncode=1)


# -------------------------------------------------------------------
# glTF to GLB conversion
# -------------------------------------------------------------------

def gltf_to_glb(gltf_file: str, output_file: str) -> CommandResult:
    """
    Convert a glTF JSON file to GLB binary format.

    Args:
        gltf_file: Path to input glTF JSON file
        output_file: Path to output GLB file

    Returns:
        CommandResult with conversion status
    """
    if os.environ.get("GLTF_MOCK"):
        return CommandResult(
            success=True,
            output=f"Converted {gltf_file} to {output_file}",
            returncode=0,
        )

    gltf_path = Path(gltf_file)
    if not gltf_path.exists():
        return CommandResult(
            success=False,
            error=f"Input file not found: {gltf_file}",
            returncode=1,
        )

    try:
        # Read glTF JSON
        with open(gltf_path, "r", encoding="utf-8") as f:
            gltf_data = json.load(f)

        # Validate it looks like glTF
        if "asset" not in gltf_data:
            return CommandResult(success=False, error="Not a valid glTF file", returncode=1)

        # Create GLB structure
        json_str = json.dumps(gltf_data, separators=(",", ":"), ensure_ascii=False)
        json_bytes = json_str.encode("utf-8")

        # GLB header
        magic = struct.pack("<I", 0x46546C67)
        version = struct.pack("<I", 2)

        # JSON chunk header
        json_chunk_length = len(json_bytes)
        json_chunk_type = struct.pack("<I", 0x4E4F534A)  # "JSON"

        # JSON chunk data
        json_chunk = json_bytes

        # Binary chunk (empty for now - no binary data)
        binary_chunk = b""

        # Binary chunk header (only if we have binary data)
        if binary_chunk:
            binary_chunk_length = struct.pack("<I", len(binary_chunk))
            binary_chunk_type = struct.pack("<I", 0x004E4942)  # "BIN\0"
            binary_header = binary_chunk_length + binary_chunk_type + binary_chunk
        else:
            binary_header = b""

        # Total length
        total_length = 12 + 8 + len(json_bytes) + len(binary_header)
        length = struct.pack("<I", total_length)

        # Write GLB
        with open(output_file, "wb") as f:
            f.write(magic)
            f.write(version)
            f.write(length)
            f.write(json_chunk_length)
            f.write(json_chunk_type)
            f.write(json_chunk)
            if binary_header:
                f.write(binary_header)

        return CommandResult(
            success=True,
            output=f"Converted {gltf_file} to {output_file}",
            returncode=0,
        )

    except json.JSONDecodeError as e:
        return CommandResult(success=False, error=f"Invalid JSON: {e}", returncode=1)
    except Exception as e:
        return CommandResult(success=False, error=f"Conversion error: {e}", returncode=1)


# -------------------------------------------------------------------
# GLB to glTF conversion
# -------------------------------------------------------------------

def glb_to_gltf(glb_file: str, output_file: str) -> CommandResult:
    """
    Convert a GLB binary file to glTF JSON format.

    Args:
        glb_file: Path to input GLB file
        output_file: Path to output glTF JSON file

    Returns:
        CommandResult with conversion status
    """
    if os.environ.get("GLTF_MOCK"):
        return CommandResult(
            success=True,
            output=f"Converted {glb_file} to {output_file}",
            returncode=0,
        )

    path = Path(glb_file)
    if not path.exists():
        return CommandResult(
            success=False,
            error=f"Input file not found: {glb_file}",
            returncode=1,
        )

    try:
        with open(path, "rb") as f:
            # Read and validate header
            magic = f.read(4)
            if struct.unpack("<I", magic)[0] != 0x46546C67:
                return CommandResult(success=False, error="Invalid GLB magic", returncode=1)

            version = struct.unpack("<I", f.read(4))[0]
            if version != 2:
                return CommandResult(success=False, error=f"Unsupported GLB version: {version}", returncode=1)

            # Skip length
            f.read(4)

            # Read JSON chunk
            chunk_length = struct.unpack("<I", f.read(4))[0]
            chunk_type = struct.unpack("<I", f.read(4))[0]

            if chunk_type != 0x4E4F534A:  # "JSON"
                return CommandResult(success=False, error="First chunk is not JSON", returncode=1)

            json_bytes = f.read(chunk_length)
            gltf_data = json.loads(json_bytes.decode("utf-8"))

            # Write glTF JSON
            with open(output_file, "w", encoding="utf-8") as out:
                json.dump(gltf_data, out, indent=2, ensure_ascii=False)

            return CommandResult(
                success=True,
                output=f"Converted {glb_file} to {output_file}",
                returncode=0,
            )

    except struct.error as e:
        return CommandResult(success=False, error=f"Invalid GLB structure: {e}", returncode=1)
    except json.JSONDecodeError as e:
        return CommandResult(success=False, error=f"Invalid JSON in GLB: {e}", returncode=1)
    except Exception as e:
        return CommandResult(success=False, error=f"Conversion error: {e}", returncode=1)


# -------------------------------------------------------------------
# glTF Info
# -------------------------------------------------------------------

def gltf_info(gltf_path: str) -> dict:
    """
    Get information about a glTF file.

    Args:
        gltf_path: Path to glTF file (JSON or GLB)

    Returns:
        dict with glTF statistics
    """
    if os.environ.get("GLTF_MOCK"):
        return {
            "success": True,
            "path": gltf_path,
            "format": "glTF 2.0",
            "nodes": 5,
            "meshes": 2,
            "images": 1,
            "accessors": 8,
            "materials": 1,
            "animations": 0,
            "cameras": 0,
            "skins": 0,
        }

    path = Path(gltf_path)
    if not path.exists():
        return {
            "success": False,
            "error": f"File not found: {gltf_path}",
        }

    try:
        if path.suffix.lower() == ".glb":
            data = _read_glb_json(path)
        else:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

        # Extract statistics
        info = {
            "success": True,
            "path": gltf_path,
            "format": "glTF 2.0",
            "asset_version": data.get("asset", {}).get("version", "unknown"),
            "nodes": len(data.get("nodes", [])),
            "meshes": len(data.get("meshes", [])),
            "images": len(data.get("images", [])),
            "accessors": len(data.get("accessors", [])),
            "materials": len(data.get("materials", [])),
            "animations": len(data.get("animations", [])),
            "cameras": len(data.get("cameras", [])),
            "skins": len(data.get("skins", [])),
            "bufferViews": len(data.get("bufferViews", [])),
            "buffers": len(data.get("buffers", [])),
        }

        return info

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


def _read_glb_json(path: Path) -> dict:
    """Extract JSON chunk from GLB file."""
    with open(path, "rb") as f:
        # Skip header
        f.read(12)
        # Read JSON chunk
        chunk_length = struct.unpack("<I", f.read(4))[0]
        f.read(4)  # chunk type
        json_bytes = f.read(chunk_length)
        return json.loads(json_bytes.decode("utf-8"))
