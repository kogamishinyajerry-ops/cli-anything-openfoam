"""gmsh_backend.py — Gmsh CLI wrapper for mesh generation."""
from __future__ import annotations
import os
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class CommandResult:
    success: bool
    output: str
    error: str = ""
    returncode: int = 0
    duration_seconds: float = 0.0


def _run(cmd: list[str], cwd: Optional[Path] = None,
         container: Optional[str] = None, timeout: int = 300) -> CommandResult:
    """Run a command, optionally inside a Docker container."""
    start = time.monotonic()
    if container:
        quoted = " ".join(str(c) for c in cmd)
        docker_cmd = ["docker", "exec", "-w", str(cwd) if cwd else "/tmp",
                      container, "bash", "-c", quoted]
        exec_cwd = None
    else:
        docker_cmd = cmd
        exec_cwd = str(cwd) if cwd else None
    try:
        r = subprocess.run(docker_cmd, cwd=exec_cwd, capture_output=True,
                           text=True, timeout=timeout)
        return CommandResult(r.returncode == 0, r.stdout, r.stderr,
                             r.returncode, time.monotonic() - start)
    except subprocess.TimeoutExpired as e:
        return CommandResult(False, e.stdout.decode() if e.stdout else "",
                             f"Timeout after {timeout}s", -1, time.monotonic() - start)


# ---- Geo file generators ----

def create_geo_box(x: float, y: float, z: float, mesh_size: float = 0.5) -> str:
    """Generate .geo script for a box."""
    return f"""\
SetFactory("OpenCASCADE");
Box(1) = {{0, 0, 0, {x}, {y}, {z}}};
Mesh.CharacteristicLengthMax = {mesh_size};
"""


def create_geo_cylinder(radius: float, length: float, mesh_size: float = 0.3) -> str:
    """Generate .geo script for a cylinder along Z axis."""
    return f"""\
SetFactory("OpenCASCADE");
Cylinder(1) = {{0, 0, 0, 0, 0, {length}, {radius}}};
Mesh.CharacteristicLengthMax = {mesh_size};
"""


def create_geo_channel(length: float, height: float, depth: float,
                       mesh_size: float = 0.2) -> str:
    """Generate .geo script for a 2D channel (extruded) with named boundaries."""
    return f"""\
SetFactory("OpenCASCADE");
Rectangle(1) = {{0, 0, 0, {length}, {height}}};
Extrude {{0, 0, {depth}}} {{ Surface{{1}}; Layers{{1}}; Recombine; }}
Physical Surface("inlet") = {{5}};
Physical Surface("outlet") = {{3}};
Physical Surface("walls") = {{2, 4}};
Physical Surface("frontAndBack") = {{1, 6}};
Physical Volume("internal") = {{1}};
Mesh.CharacteristicLengthMax = {mesh_size};
"""


# ---- Mesh operations ----

def mesh_generate(geo_path: Path, output_path: Path, dim: int = 3,
                  fmt: str = "msh2", container: Optional[str] = None) -> CommandResult:
    """Run gmsh to generate mesh."""
    cmd = ["gmsh", str(geo_path), f"-{dim}", "-o", str(output_path), "-format", fmt]
    return _run(cmd, container=container)


def mesh_info(msh_path: Path, container: Optional[str] = None) -> dict:
    """Get mesh statistics by running gmsh -info."""
    r = _run(["gmsh", str(msh_path), "-0", "-v", "3"], container=container)
    text = r.output + r.error
    info = {"nodes": 0, "elements": 0}
    m = re.search(r'(\d+)\s+vertices', text)
    if m: info["nodes"] = int(m.group(1))
    m = re.search(r'(\d+)\s+elements', text)
    if m: info["elements"] = int(m.group(1))
    return info


def convert_to_openfoam(msh_path: Path, case_path: Path,
                        container: Optional[str] = None) -> CommandResult:
    """Convert .msh to OpenFOAM format using gmshToFoam."""
    if container:
        # Ensure case dir + controlDict exist
        subprocess.run(
            ["docker", "exec", container, "bash", "-c",
             f"mkdir -p '{case_path}/system' && "
             f"test -f '{case_path}/system/controlDict' || "
             f"printf 'FoamFile {{ version 2.0; format ascii; class dictionary; object controlDict; }}\\n"
             f"application simpleFoam;\\nstartFrom startTime;\\nstartTime 0;\\n"
             f"stopAt endTime;\\nendTime 1;\\ndeltaT 1;\\n"
             f"writeControl timeStep;\\nwriteInterval 1;\\nrunTimeModifiable yes;\\n' "
             f"> '{case_path}/system/controlDict'"],
            check=True, timeout=10)
        # Run gmshToFoam
        start = time.monotonic()
        r = subprocess.run(
            ["docker", "exec", container, "bash", "-c",
             f"source /opt/openfoam10/etc/bashrc && gmshToFoam '{msh_path}' -case '{case_path}'"],
            capture_output=True, text=True, timeout=120)
        return CommandResult(r.returncode == 0, r.stdout, r.stderr,
                             r.returncode, time.monotonic() - start)
    else:
        cmd_str = f"source /opt/openfoam10/etc/bashrc && gmshToFoam '{msh_path}' -case '{case_path}'"
        return _run(["bash", "-c", cmd_str])
