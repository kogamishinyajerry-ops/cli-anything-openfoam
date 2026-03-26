"""freecad_backend.py — FreeCAD CLI wrapper for CAD operations."""
from __future__ import annotations
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


def _run_freecad(script: str, container: Optional[str] = None,
                 timeout: int = 120) -> CommandResult:
    """Run a FreeCAD Python script via freecad -c."""
    start = time.monotonic()
    if container:
        cmd = ["docker", "exec", container, "freecad", "-c", script]
    else:
        cmd = ["freecad", "-c", script]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return CommandResult(r.returncode == 0, r.stdout, r.stderr,
                             r.returncode, time.monotonic() - start)
    except subprocess.TimeoutExpired:
        return CommandResult(False, "", f"Timeout after {timeout}s",
                             -1, time.monotonic() - start)


def create_box(length: float, width: float, height: float,
               output: str, container: Optional[str] = None) -> CommandResult:
    script = (
        "import FreeCAD, Part, Mesh\n"
        "doc = FreeCAD.newDocument('model')\n"
        "box = doc.addObject('Part::Box', 'Box')\n"
        f"box.Length = {length}; box.Width = {width}; box.Height = {height}\n"
        "doc.recompute()\n"
        f"Mesh.export([box], '{output}')\n"
        "print('VOLUME=' + str(box.Shape.Volume))\n"
        "print('AREA=' + str(box.Shape.Area))\n"
        "bb = box.Shape.BoundBox\n"
        "print('BBOX=' + str([bb.XMin,bb.YMin,bb.ZMin,bb.XMax,bb.YMax,bb.ZMax]))\n"
        "print('EXPORT_OK')\n"
    )
    return _run_freecad(script, container)


def create_cylinder(radius: float, height: float,
                    output: str, container: Optional[str] = None) -> CommandResult:
    script = (
        "import FreeCAD, Part, Mesh\n"
        "doc = FreeCAD.newDocument('model')\n"
        "cyl = doc.addObject('Part::Cylinder', 'Cylinder')\n"
        f"cyl.Radius = {radius}; cyl.Height = {height}\n"
        "doc.recompute()\n"
        f"Mesh.export([cyl], '{output}')\n"
        "print('VOLUME=' + str(cyl.Shape.Volume))\n"
        "print('EXPORT_OK')\n"
    )
    return _run_freecad(script, container)


def create_pipe(outer_radius: float, inner_radius: float, length: float,
                output: str, container: Optional[str] = None) -> CommandResult:
    script = (
        "import FreeCAD, Part, Mesh\n"
        "doc = FreeCAD.newDocument('model')\n"
        "outer = doc.addObject('Part::Cylinder', 'Outer')\n"
        f"outer.Radius = {outer_radius}; outer.Height = {length}\n"
        "inner = doc.addObject('Part::Cylinder', 'Inner')\n"
        f"inner.Radius = {inner_radius}; inner.Height = {length}\n"
        "doc.recompute()\n"
        "pipe = doc.addObject('Part::Cut', 'Pipe')\n"
        "pipe.Base = outer; pipe.Tool = inner\n"
        "doc.recompute()\n"
        f"Mesh.export([pipe], '{output}')\n"
        "print('VOLUME=' + str(pipe.Shape.Volume))\n"
        "print('EXPORT_OK')\n"
    )
    return _run_freecad(script, container)


def get_info(input_path: str, container: Optional[str] = None) -> CommandResult:
    """Get geometry info (volume, area, bounding box)."""
    script = (
        "import FreeCAD, Mesh\n"
        f"mesh = Mesh.Mesh('{input_path}')\n"
        "print('POINTS=' + str(mesh.CountPoints))\n"
        "print('FACETS=' + str(mesh.CountFacets))\n"
        "bb = mesh.BoundBox\n"
        "print('BBOX=' + str([bb.XMin,bb.YMin,bb.ZMin,bb.XMax,bb.YMax,bb.ZMax]))\n"
        "print('VOLUME=' + str(mesh.Volume))\n"
        "print('AREA=' + str(mesh.Area))\n"
        "print('INFO_OK')\n"
    )
    return _run_freecad(script, container)


def run_script(script_path: str, container: Optional[str] = None) -> CommandResult:
    """Run an arbitrary FreeCAD Python script."""
    if container:
        cmd = ["docker", "exec", container, "freecad", "-c",
               "exec(open('" + script_path + "').read())"]
    else:
        cmd = ["freecad", "-c", "exec(open('" + script_path + "').read())"]
    start = time.monotonic()
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        return CommandResult(r.returncode == 0, r.stdout, r.stderr,
                             r.returncode, time.monotonic() - start)
    except subprocess.TimeoutExpired:
        return CommandResult(False, "", "Timeout", -1, time.monotonic() - start)
