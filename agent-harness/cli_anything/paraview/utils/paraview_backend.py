"""paraview_backend.py — ParaView pvpython wrapper for CFD post-processing."""
from __future__ import annotations
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

PVPYTHON = "/opt/paraviewopenfoam510/bin/pvpython"


@dataclass
class CommandResult:
    success: bool
    output: str
    error: str = ""
    returncode: int = 0
    duration_seconds: float = 0.0


def _run_pvpython(script: str, container: Optional[str] = None,
                  timeout: int = 120) -> CommandResult:
    """Run a pvpython script inside the container with xvfb for offscreen rendering."""
    start = time.monotonic()
    if container:
        cmd = ["docker", "exec", container, "xvfb-run", "-a", PVPYTHON, "-c", script]
    else:
        cmd = ["pvpython", "-c", script]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return CommandResult(r.returncode == 0, r.stdout, r.stderr,
                             r.returncode, time.monotonic() - start)
    except subprocess.TimeoutExpired:
        return CommandResult(False, "", f"Timeout after {timeout}s",
                             -1, time.monotonic() - start)


def screenshot(case_path: str, field: str, output: str,
               time_value: str = "latest", view: str = "iso",
               width: int = 1200, height: int = 800,
               container: Optional[str] = None) -> CommandResult:
    """Take a screenshot of a field from an OpenFOAM case."""
    foam_file = f"{case_path}/{Path(case_path).name}.foam"

    view_lines = {
        "iso": ["view.CameraPosition = [15, 10, 10]",
                "view.CameraFocalPoint = [5, 0.5, 0.05]"],
        "top": ["view.CameraPosition = [5, 0.5, 20]",
                "view.CameraFocalPoint = [5, 0.5, 0]",
                "view.CameraViewUp = [0, 1, 0]"],
        "front": ["view.CameraPosition = [5, -20, 0.05]",
                  "view.CameraFocalPoint = [5, 0.5, 0.05]",
                  "view.CameraViewUp = [0, 0, 1]"],
        "side": ["view.CameraPosition = [-20, 0.5, 0.05]",
                 "view.CameraFocalPoint = [5, 0.5, 0.05]",
                 "view.CameraViewUp = [0, 0, 1]"],
    }
    vc = "\n    ".join(view_lines.get(view, view_lines["iso"]))

    script = (
        "import os\n"
        f"foam_file = '{foam_file}'\n"
        "if not os.path.exists(foam_file):\n"
        "    open(foam_file, 'w').close()\n"
        "from paraview.simple import *\n"
        f"reader = OpenFOAMReader(FileName=foam_file)\n"
        "reader.MeshRegions = ['internalMesh']\n"
        "times = reader.TimestepValues\n"
        "if times:\n"
        "    view_obj = GetActiveViewOrCreate('RenderView')\n"
        "    animationScene = GetAnimationScene()\n"
        "    animationScene.AnimationTime = times[-1]\n"
        "    display = Show(reader, view_obj)\n"
        "    display.Representation = 'Surface'\n"
        f"    ColorBy(display, ('CELLS', '{field}'))\n"
        "    display.RescaleTransferFunctionToDataRange(True)\n"
        "    display.SetScalarBarVisibility(view_obj, True)\n"
        "    view = view_obj\n"
        f"    view.ViewSize = [{width}, {height}]\n"
        f"    {vc}\n"
        "    view.ResetCamera()\n"
        "    Render()\n"
        f"    SaveScreenshot('{output}', view)\n"
        "    print('SCREENSHOT_OK')\n"
        "    print('TIME=' + str(times[-1]))\n"
        "    print('FIELDS=' + str(reader.CellArrays.GetData()))\n"
        "else:\n"
        "    print('NO_TIMESTEPS')\n"
    )
    return _run_pvpython(script, container)


def extract_line(case_path: str, field: str, point1: str, point2: str,
                 output: str, n_points: int = 100,
                 container: Optional[str] = None) -> CommandResult:
    """Extract field values along a line and save as CSV."""
    foam_file = f"{case_path}/{Path(case_path).name}.foam"
    p1 = [float(x) for x in point1.split(",")]
    p2 = [float(x) for x in point2.split(",")]

    script = f"""
import os
foam_file = '{foam_file}'
if not os.path.exists(foam_file):
    open(foam_file, 'w').close()
from paraview.simple import *
reader = OpenFOAMReader(FileName=foam_file)
reader.MeshRegions = ['internalMesh']
times = reader.TimestepValues
if times:
    animationScene = GetAnimationScene()
    animationScene.AnimationTime = times[-1]
    line = PlotOverLine(Input=reader)
    line.Point1 = {p1}
    line.Point2 = {p2}
    line.Resolution = {n_points}
    SaveData('{output}', proxy=line)
    print('EXTRACT_OK')
    print('POINTS={n_points}')
else:
    print('NO_TIMESTEPS')
"""
    return _run_pvpython(script, container)


def extract_slice(case_path: str, field: str, origin: str, normal: str,
                  output: str, container: Optional[str] = None) -> CommandResult:
    """Extract a slice and save as CSV."""
    foam_file = f"{case_path}/{Path(case_path).name}.foam"
    o = [float(x) for x in origin.split(",")]
    n = [float(x) for x in normal.split(",")]

    script = f"""
import os
foam_file = '{foam_file}'
if not os.path.exists(foam_file):
    open(foam_file, 'w').close()
from paraview.simple import *
reader = OpenFOAMReader(FileName=foam_file)
reader.MeshRegions = ['internalMesh']
times = reader.TimestepValues
if times:
    animationScene = GetAnimationScene()
    animationScene.AnimationTime = times[-1]
    sl = Slice(Input=reader)
    sl.SliceType.Origin = {o}
    sl.SliceType.Normal = {n}
    SaveData('{output}', proxy=sl)
    print('SLICE_OK')
else:
    print('NO_TIMESTEPS')
"""
    return _run_pvpython(script, container)


def get_case_info(case_path: str, container: Optional[str] = None) -> CommandResult:
    """Get case info: time steps, fields, boundaries."""
    foam_file = f"{case_path}/{Path(case_path).name}.foam"

    script = f"""
import os
foam_file = '{foam_file}'
if not os.path.exists(foam_file):
    open(foam_file, 'w').close()
from paraview.simple import *
reader = OpenFOAMReader(FileName=foam_file)
print('TIMES=' + str(list(reader.TimestepValues)))
print('CELL_FIELDS=' + str(reader.CellArrays.GetData()))
print('POINT_FIELDS=' + str(reader.PointArrays.GetData()))
print('REGIONS=' + str(reader.MeshRegions.GetData()))
print('INFO_OK')
"""
    return _run_pvpython(script, container)
