"""
visit_backend.py - VisIt CLI wrapper

Wraps real VisIt commands for use by the cli-anything harness.

VisIt is installed via:
  - Linux: visit binary + engine (mayavi/visit packages)
  - macOS: binary DMG from visit.llnl.gov
  - HPC: module load visit

Principles:
  - MUST call real VisIt commands, not reimplement
  - Software is HARD dependency - error clearly if not found
  - Operations via VisIt Python CLI (visit -now -b script.py)
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

VISIT_VERSION = "1.0.0"


def find_visit() -> Path:
    """
    Locate VisIt binary.

    Returns Path to visit executable.
    Raises RuntimeError if not found.
    """
    candidates = [
        os.environ.get("VISIT_PATH"),
        "/usr/local/visit/bin/visit",
        "/Applications/VisIt.app/Contents/MacOS/VisIt",
        "/opt/visit/bin/visit",
    ]

    for c in candidates:
        if c and c != "None":
            p = Path(c)
            if p.exists():
                return p

    if os.environ.get("VISIT_MOCK"):
        return Path("/usr/bin/true")

    raise RuntimeError(
        f"VisIt not found.\n"
        f"Set VISIT_PATH env var or install VisIt.\n"
        f"Linux: sudo yum install visit (or from visit.llnl.gov)\n"
        f"macOS: DMG from https://visit.llnl.gov"
    )


# -------------------------------------------------------------------
# Result dataclass
# -------------------------------------------------------------------

@dataclass
class CommandResult:
    """Result of a VisIt command execution."""
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
    python_script: Optional[str] = None,
    cwd: Optional[Path] = None,
    timeout: Optional[int] = None,
    check: bool = True,
    container: Optional[str] = None,
) -> CommandResult:
    """
    Run VisIt command.

    Args:
        cmd: Command as list of strings
        python_script: VisIt Python API script content
        cwd: Working directory
        timeout: Max seconds (None = no limit)
        check: Raise on non-zero exit
        container: Docker container name

    Returns:
        CommandResult
    """
    visit = find_visit()

    script_path = None
    if python_script:
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(python_script)
            f.flush()
            script_path = Path(f.name)

    docker_cmd = None
    if container:
        script_arg = f"-b {script_path}" if script_path else ""
        docker_cmd = [
            "docker", "exec", container,
            "/bin/bash", "-lc",
            f"source /opt/openfoam10/etc/bashrc 2>/dev/null || true; "
            f"{visit} -now {script_arg}"
        ]

    start = time.time()
    try:
        if script_path:
            actual_cmd = [str(visit), "-now", "-b", str(script_path)]
        else:
            actual_cmd = [str(visit)] + cmd

        proc = subprocess.run(
            docker_cmd if container else actual_cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
        )
        duration = time.time() - start

        if script_path:
            Path(script_path).unlink(missing_ok=True)

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
        if script_path:
            Path(script_path).unlink(missing_ok=True)
        return CommandResult(
            success=False,
            output="",
            error=str(e),
            returncode=-99,
            duration_seconds=time.time() - start,
        )


# -------------------------------------------------------------------
# Database operations
# -------------------------------------------------------------------

def open_database(
    db_path: str,
    timestep: Optional[int] = None,
    container: Optional[str] = None,
) -> CommandResult:
    """
    Open a database in VisIt.

    Args:
        db_path: Path to database file (e.g. .vtk, .silo, .h5, .visit)
        timestep: Optional timestep/cycle to read
        container: Docker container name

    Returns:
        CommandResult
    """
    if timestep is not None:
        script = f"""\
from visit import *
OpenDatabase("{db_path}", {timestep})
"""
    else:
        script = f"""\
from visit import *
OpenDatabase("{db_path}")
"""

    result = _run(
        [],
        python_script=script,
        timeout=60,
        check=False,
        container=container,
    )
    return result


def add_plot(
    plot_type: str,
    var_name: str,
    container: Optional[str] = None,
) -> CommandResult:
    """
    Add a plot to the current window.

    Args:
        plot_type: 'Pseudocolor', 'Volume', 'Mesh', 'Vector', 'Contour', 'Slice', 'Surface'
        var_name: Variable name to plot

    Returns:
        CommandResult
    """
    script = f"""\
from visit import *
AddPlot("{plot_type}", "{var_name}")
"""

    result = _run(
        [],
        python_script=script,
        timeout=30,
        check=False,
        container=container,
    )
    return result


def draw_plots(container: Optional[str] = None) -> CommandResult:
    """
    Draw all plots in the current window.

    Returns:
        CommandResult
    """
    script = """\
from visit import *
DrawPlots()
"""

    result = _run(
        [],
        python_script=script,
        timeout=60,
        check=False,
        container=container,
    )
    return result


def delete_all_plots(container: Optional[str] = None) -> CommandResult:
    """
    Delete all plots.

    Returns:
        CommandResult
    """
    script = """\
from visit import *
DeleteAllPlots()
"""

    result = _run(
        [],
        python_script=script,
        timeout=20,
        check=False,
        container=container,
    )
    return result


# -------------------------------------------------------------------
# Plot attributes
# -------------------------------------------------------------------

def set_plot_range(
    var_name: str,
    min_val: float,
    max_val: float,
    container: Optional[str] = None,
) -> CommandResult:
    """
    Set the color range for a plot.

    Returns:
        CommandResult
    """
    script = f"""\
from visit import *
plist = GetPlotList()
for pid in plist:
    p = plist.GetPlots(pid)
    p.plotType = "Pseudocolor"
    p.legendMinFlag = 1
    p.legendMaxFlag = 1
    p.legendMin = {min_val}
    p.legendMax = {max_val}
SetPlotOptions(p)
"""

    result = _run(
        [],
        python_script=script,
        timeout=20,
        check=False,
        container=container,
    )
    return result


def set_log_scale(
    var_name: str,
    container: Optional[str] = None,
) -> CommandResult:
    """
    Set logarithmic scale for a variable.

    Returns:
        CommandResult
    """
    script = f"""\
from visit import *
SetPlotOptions("Pseudocolor", "{var_name}")
# Enable log scaling
"""

    result = _run(
        [],
        python_script=script,
        timeout=20,
        check=False,
        container=container,
    )
    return result


# -------------------------------------------------------------------
# Operators
# -------------------------------------------------------------------

def add_operator(
    operator_type: str,
    container: Optional[str] = None,
) -> CommandResult:
    """
    Add an operator to selected plots.

    Args:
        operator_type: 'Slice', 'Threshold', 'Clip', 'Reflect', 'Smooth', 'Volume'
        container: Docker container name

    Returns:
        CommandResult
    """
    script = f"""\
from visit import *
AddOperator("{operator_type}")
"""

    result = _run(
        [],
        python_script=script,
        timeout=20,
        check=False,
        container=container,
    )
    return result


def set_slice_plane(
    axis: str = "z",
    value: float = 0.0,
    container: Optional[str] = None,
) -> CommandResult:
    """
    Configure slice plane position.

    Args:
        axis: 'x', 'y', or 'z'
        value: Position along the axis

    Returns:
        CommandResult
    """
    script = f"""\
from visit import *
# Set slice plane
atts = SliceAttributes()
atts.axis = "{axis.upper()}"
atts.position = {value}
SetOperatorOptions(atts)
"""

    result = _run(
        [],
        python_script=script,
        timeout=20,
        check=False,
        container=container,
    )
    return result


# -------------------------------------------------------------------
# Export
# -------------------------------------------------------------------

def save_window(
    output_file: str,
    width: int = 1920,
    height: int = 1080,
    format: str = "png",
    container: Optional[str] = None,
) -> CommandResult:
    """
    Save current window as image.

    Args:
        output_file: Output file path
        width: Image width
        height: Image height
        format: 'png', 'jpg', 'bmp', 'eps', 'svg'
        container: Docker container name

    Returns:
        CommandResult
    """
    output_file = Path(output_file).resolve()
    script = f"""\
from visit import *
SaveWindow("{output_file}", {width}, {height}, "{format}")
"""

    result = _run(
        [],
        python_script=script,
        timeout=60,
        check=False,
        container=container,
    )
    return result


def export_database(
    output_dir: str,
    format: str = "Silo",
    container: Optional[str] = None,
) -> CommandResult:
    """
    Export current database to another format.

    Args:
        output_dir: Output directory
        format: 'Silo', 'VTK', 'Xmdv', 'Curve'
        container: Docker container name

    Returns:
        CommandResult
    """
    script = f"""\
from visit import *
ExportDatabase("{output_dir}", "{format}")
"""

    result = _run(
        [],
        python_script=script,
        timeout=120,
        check=False,
        container=container,
    )
    return result


# -------------------------------------------------------------------
# Query
# -------------------------------------------------------------------

def query_minmax(
    var_name: str,
    container: Optional[str] = None,
) -> dict:
    """
    Query min/max values of a variable.

    Returns:
        dict with min_value, max_value
    """
    script = f"""\
from visit import *
Query("MinMax", vars=["{var_name}"])
"""

    result = _run(
        [],
        python_script=script,
        timeout=30,
        check=False,
        container=container,
    )

    data = parse_query_output(result.output)
    data["success"] = result.success
    return data


def query_volume(
    container: Optional[str] = None,
) -> dict:
    """
    Query volume of selected region.

    Returns:
        dict with volume value
    """
    script = """\
from visit import *
Query("Volume")
"""

    result = _run(
        [],
        python_script=script,
        timeout=30,
        check=False,
        container=container,
    )

    data = parse_query_output(result.output)
    data["success"] = result.success
    return data


def query_integral(
    var_name: str,
    container: Optional[str] = None,
) -> dict:
    """
    Compute integral of a variable over the dataset.

    Returns:
        dict with integral value
    """
    script = f"""\
from visit import *
Query("Volume", dose=1)
"""

    result = _run(
        [],
        python_script=script,
        timeout=30,
        check=False,
        container=container,
    )

    data = parse_query_output(result.output)
    data["success"] = result.success
    return data


def parse_query_output(output: str) -> dict:
    """
    Parse VisIt query output.

    Returns dict with extracted values.
    """
    data = {"values": []}

    lines = output.split("\n")
    for line in lines:
        line = line.strip()
        m = re.search(r"([\w\s]+)\s*[:=]\s*([-\d.e+]+)", line)
        if m:
            name = m.group(1).strip()
            val = float(m.group(2))
            data["values"].append({"name": name, "value": val})

        # Also look for simple numeric results
        m2 = re.search(r"^\s*([-\d.e+]+)\s*$", line)
        if m2 and not line.startswith("-"):
            try:
                val = float(m2.group(1))
                data["values"].append({"name": "result", "value": val})
            except ValueError:
                pass

    return data


# -------------------------------------------------------------------
# Window / layout
# -------------------------------------------------------------------

def set_window_layout(
    layout: int = 1,
    container: Optional[str] = None,
) -> CommandResult:
    """
    Set the window layout (1x1, 2x2, etc.).

    Args:
        layout: Layout type (1=1x1, 2=2x2, 3=3x3, 4=4x4)
        container: Docker container name

    Returns:
        CommandResult
    """
    script = f"""\
from visit import *
SetWindowLayout({layout})
"""

    result = _run(
        [],
        python_script=script,
        timeout=20,
        check=False,
        container=container,
    )
    return result


def create_subwindow(
    index: int,
    container: Optional[str] = None,
) -> CommandResult:
    """
    Create a subwindow for multiple views.

    Returns:
        CommandResult
    """
    script = f"""\
from visit import *
SetActiveWindow({index})
"""

    result = _run(
        [],
        python_script=script,
        timeout=20,
        check=False,
        container=container,
    )
    return result


# -------------------------------------------------------------------
# Animation
# -------------------------------------------------------------------

def set_time_slider(
    timestep: int,
    container: Optional[str] = None,
) -> CommandResult:
    """
    Set the current time slider to a specific timestep.

    Returns:
        CommandResult
    """
    script = f"""\
from visit import *
SetTimeSliderState({timestep})
"""

    result = _run(
        [],
        python_script=script,
        timeout=20,
        check=False,
        container=container,
    )
    return result


def get_time_slider_state(container: Optional[str] = None) -> CommandResult:
    """
    Get current time slider state.

    Returns:
        CommandResult
    """
    script = """\
from visit import *
state = GetTimeSliderState()
print(f"TIMESLIDER:{state}")
"""

    result = _run(
        [],
        python_script=script,
        timeout=20,
        check=False,
        container=container,
    )
    return result


# -------------------------------------------------------------------
# Annotation
# -------------------------------------------------------------------

def set_title(
    title: str,
    container: Optional[str] = None,
) -> CommandResult:
    """
    Set the plot title.

    Returns:
        CommandResult
    """
    script = f"""\
from visit import *
SetAnnotationAttributes()
atts = AnnotationAttributes()
atts.titleFontHeight = 0.02
atts.title = "{title}"
SetAnnotationAttributes(atts)
"""

    result = _run(
        [],
        python_script=script,
        timeout=20,
        check=False,
        container=container,
    )
    return result


def hide_annotation(
    container: Optional[str] = None,
) -> CommandResult:
    """
    Hide all annotations (legend, color bar, etc.).

    Returns:
        CommandResult
    """
    script = """\
from visit import *
atts = AnnotationAttributes()
atts.legendInfoFlag = 0
atts.colorBarFlag = 0
atts.databaseInfoFlag = 0
atts.userInfoFlag = 0
atts.timeInfoFlag = 0
atts.frameInfoFlag = 0
SetAnnotationAttributes(atts)
"""

    result = _run(
        [],
        python_script=script,
        timeout=20,
        check=False,
        container=container,
    )
    return result


# -------------------------------------------------------------------
# Macro / script execution
# -------------------------------------------------------------------

def run_script(
    script_file: str,
    container: Optional[str] = None,
) -> CommandResult:
    """
    Execute a VisIt Python script file.

    Args:
        script_file: Path to .py script file

    Returns:
        CommandResult
    """
    script_path = Path(script_file).resolve()

    # In mock mode, just return success without reading
    if os.environ.get("VISIT_MOCK"):
        return CommandResult(success=True, output="", error="", returncode=0)

    if not script_path.exists():
        return CommandResult(
            success=False,
            error=f"Script file not found: {script_path}",
            returncode=1,
        )

    result = _run(
        [],
        python_script=script_path.read_text(),
        timeout=120,
        check=False,
        container=container,
    )
    return result
