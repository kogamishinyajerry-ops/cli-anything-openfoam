"""
tecplot_backend.py - Tecplot 360 CLI wrapper

Wraps real Tecplot commands for use by the cli-anything harness.

Tecplot 360 is installed via:
  - Linux: standard Tecplot installation (/usr/local/tecplot/)
  - Container: pre-installed in cfd-openfoam

Principles:
  - MUST call real Tecplot commands, not reimplement
  - Software is HARD dependency - error clearly if not found
  - Operations via Tecplot's Python API (tecio) or CLI batch mode
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

TECPLOT_VERSION = "1.0.0"


def find_tecplot() -> Path:
    """
    Locate Tecplot executable.

    Returns Path to tec360 or tecplot binary.
    Raises RuntimeError if not found.
    """
    # Check common Tecplot installation paths
    candidates = [
        os.environ.get("TECPLOT_PATH"),
        "/usr/local/tecplot/bin/tec360",
        "/usr/local/tecplot/bin/tecplot",
        "/opt/tecplot/bin/tec360",
        "/Applications/Tecplot 360 EX 2023 R2.app/Contents/MacOS/tec360",
    ]

    for c in candidates:
        if c and c != "None":
            p = Path(c)
            if p.exists():
                return p

    if os.environ.get("TECPLOT_MOCK"):
        return Path("/usr/bin/true")

    raise RuntimeError(
        f"Tecplot not found.\n"
        f"Set TECPLOT_PATH env var or install Tecplot 360.\n"
        f"macOS: /Applications/Tecplot 360 EX...\n"
        f"Linux: /usr/local/tecplot/bin/tec360"
    )


# -------------------------------------------------------------------
# Result dataclass
# -------------------------------------------------------------------

@dataclass
class CommandResult:
    """Result of a Tecplot command execution."""
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
    Run Tecplot command.

    Args:
        cmd: Command as list of strings
        python_script: Tecplot Python API script content
        cwd: Working directory
        timeout: Max seconds (None = no limit)
        check: Raise on non-zero exit
        container: Docker container name

    Returns:
        CommandResult
    """
    tecplot = find_tecplot()

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
            f"{tecplot} {' '.join(cmd)} {script_arg}"
        ]

    start = time.time()
    try:
        if script_path:
            actual_cmd = [str(tecplot)] + cmd + ["-b", str(script_path)]
        else:
            actual_cmd = [str(tecplot)] + cmd

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
# Data loading
# -------------------------------------------------------------------

def load_data(
    data_file: str,
    container: Optional[str] = None,
) -> CommandResult:
    """
    Load a data file into Tecplot.

    Args:
        data_file: Path to data file (.dat, .plt, .cas, .h5, .sgl)
        container: Docker container name

    Returns:
        CommandResult
    """
    data_file = Path(data_file).resolve()
    script = f"""\
import tecplot
tecplot.session.connect()
dataset = tecplot.data.load_fluent(
    filename='{data_file}',
    shadow_dataset=True
)
"""
    result = _run(
        ["-noloadvol"],
        python_script=script,
        timeout=60,
        check=False,
        container=container,
    )
    return result


def load_zone(
    zone_name: str,
    container: Optional[str] = None,
) -> CommandResult:
    """
    Load a specific zone from current data.

    Returns:
        CommandResult
    """
    script = f"""\
import tecplot
tecplot.session.connect()
frame = tecplot.active_frame()
frame.dataset.zone('{zone_name}')
"""
    result = _run(
        [],
        python_script=script,
        timeout=30,
        check=False,
        container=container,
    )
    return result


# -------------------------------------------------------------------
# Plotting
# -------------------------------------------------------------------

def set_plot_type(
    plot_type: str = "cartesian",
    container: Optional[str] = None,
) -> CommandResult:
    """
    Set the plot type.

    Args:
        plot_type: 'cartesian', 'polar', 'XYLine', 'Sketch'
        container: Docker container name

    Returns:
        CommandResult
    """
    plot_map = {
        "cartesian": "Cartesian",
        "polar": "Polar",
        "XYLine": "XY Line",
        "Sketch": "Sketch",
    }
    ptype = plot_map.get(plot_type, "Cartesian")

    script = f"""\
import tecplot
tecplot.session.connect()
frame = tecplot.active_frame()
frame.plot_type = tecplot.constant.PlotType.{ptype}
"""
    result = _run(
        [],
        python_script=script,
        timeout=20,
        check=False,
        container=container,
    )
    return result


def contour_levels(
    var_name: str,
    levels: Optional[list] = None,
    container: Optional[str] = None,
) -> CommandResult:
    """
    Set contour levels for a variable.

    Args:
        var_name: Variable name for contour
        levels: List of contour level values (if None, auto-generated)
        container: Docker container name

    Returns:
        CommandResult
    """
    if levels:
        levels_str = ", ".join(str(l) for l in levels)
        script = f"""\
import tecplot
from tecplot.constant import *
tecplot.session.connect()
frame = tecplot.active_frame()
plot = frame.plot()
plot.contour(0).levels.set([{levels_str}])
plot.contour(0).variable = frame.dataset.variable('{var_name}')
"""
    else:
        script = f"""\
import tecplot
from tecplot.constant import *
tecplot.session.connect()
frame = tecplot.active_frame()
plot = frame.plot()
plot.contour(0).variable = frame.dataset.variable('{var_name}')
plot.contour(0).levels.reset()
"""

    result = _run(
        [],
        python_script=script,
        timeout=20,
        check=False,
        container=container,
    )
    return result


def set_variable_range(
    var_name: str,
    vmin: float,
    vmax: float,
    container: Optional[str] = None,
) -> CommandResult:
    """
    Set axis range for a variable.

    Returns:
        CommandResult
    """
    script = f"""\
import tecplot
tecplot.session.connect()
frame = tecplot.active_frame()
var = frame.dataset.variable('{var_name}')
var.valid_range = ({vmin}, {vmax})
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
# Export / Images
# -------------------------------------------------------------------

def export_image(
    output_file: str,
    width: int = 1920,
    height: int = 1080,
    container: Optional[str] = None,
) -> CommandResult:
    """
    Export current plot as image.

    Args:
        output_file: Output image path (.png, .jpg, .eps, .svg, .pdf)
        width: Image width in pixels
        height: Image height in pixels
        container: Docker container name

    Returns:
        CommandResult
    """
    output_file = Path(output_file).resolve()
    ext = output_file.suffix.lstrip(".")

    script = f"""\
import tecplot
tecplot.session.connect()
frame = tecplot.active_frame()
frame.plot().export_snapshot('{output_file}')
"""

    result = _run(
        [],
        python_script=script,
        timeout=60,
        check=False,
        container=container,
    )
    return result


def export_vector_format(
    output_file: str,
    format: str = "eps",
    container: Optional[str] = None,
) -> CommandResult:
    """
    Export as vector format (EPS, SVG, PDF).

    Returns:
        CommandResult
    """
    script = f"""\
import tecplot
tecplot.session.connect()
frame = tecplot.active_frame()
tecplot.io.save_entity('{output_file}')
"""

    result = _run(
        [],
        python_script=script,
        timeout=60,
        check=False,
        container=container,
    )
    return result


def export_data(
    output_file: str,
    zone_name: Optional[str] = None,
    container: Optional[str] = None,
) -> CommandResult:
    """
    Export data to file.

    Args:
        output_file: Output file path
        zone_name: Optional specific zone to export

    Returns:
        CommandResult
    """
    zone_arg = f", zone=zone('{zone_name}')" if zone_name else ""
    script = f"""\
import tecplot
tecplot.session.connect()
tecplot.data.save_tecplot_ascii('{output_file}'{zone_arg})
"""

    result = _run(
        [],
        python_script=script,
        timeout=60,
        check=False,
        container=container,
    )
    return result


# -------------------------------------------------------------------
# Macro / Automation
# -------------------------------------------------------------------

def run_macro(
    macro_file: str,
    container: Optional[str] = None,
) -> CommandResult:
    """
    Execute a Tecplot macro file.

    Args:
        macro_file: Path to .mac macro file

    Returns:
        CommandResult
    """
    macro_file = Path(macro_file).resolve()
    result = _run(
        [f"-m{macro_file}"],
        timeout=120,
        check=False,
        container=container,
    )
    return result


def run_python_script(
    script_file: str,
    container: Optional[str] = None,
) -> CommandResult:
    """
    Execute a Tecplot Python script.

    Args:
        script_file: Path to .py script file

    Returns:
        CommandResult
    """
    script_file = Path(script_file).resolve()
    result = _run(
        ["-b", str(script_file)],
        timeout=120,
        check=False,
        container=container,
    )
    return result


# -------------------------------------------------------------------
# Layout operations
# -------------------------------------------------------------------

def new_layout(
    layout_name: str,
    container: Optional[str] = None,
) -> CommandResult:
    """
    Create a new layout.

    Returns:
        CommandResult
    """
    script = f"""\
import tecplot
tecplot.session.connect()
layout = tecplot.layout.new()
layout.name = '{layout_name}'
"""

    result = _run(
        [],
        python_script=script,
        timeout=20,
        check=False,
        container=container,
    )
    return result


def load_layout(
    layout_file: str,
    container: Optional[str] = None,
) -> CommandResult:
    """
    Load a Tecplot layout file.

    Args:
        layout_file: Path to .lay layout file

    Returns:
        CommandResult
    """
    layout_file = Path(layout_file).resolve()
    script = f"""\
import tecplot
tecplot.session.connect()
tecplot.layout.load('{layout_file}')
"""

    result = _run(
        [],
        python_script=script,
        timeout=30,
        check=False,
        container=container,
    )
    return result


def save_layout(
    layout_file: str,
    container: Optional[str] = None,
) -> CommandResult:
    """
    Save current layout.

    Returns:
        CommandResult
    """
    layout_file = Path(layout_file).resolve()
    script = f"""\
import tecplot
tecplot.session.connect()
tecplot.layout.save('{layout_file}')
"""

    result = _run(
        [],
        python_script=script,
        timeout=30,
        check=False,
        container=container,
    )
    return result


# -------------------------------------------------------------------
# Slice / contour plots
# -------------------------------------------------------------------

def create_slice_plane(
    slice_type: str = "zone slices",
    container: Optional[str] = None,
) -> CommandResult:
    """
    Create a slice plane through the data.

    Args:
        slice_type: 'zone slices', 'multiple', 'i-slice', 'j-slice', 'k-slice'

    Returns:
        CommandResult
    """
    slice_map = {
        "zone slices": "Zone Slices",
        "multiple": "Multiple",
        "i-slice": "I-Constant Slice",
        "j-slice": "J-Constant Slice",
        "k-slice": "K-Constant Slice",
    }
    stype = slice_map.get(slice_type, "Zone Slices")

    script = f"""\
import tecplot
from tecplot.constant import *
tecplot.session.connect()
frame = tecplot.active_frame()
plot = frame.plot()
plot.show_slices = True
slice = plot.slice(0)
slice.slice_type = SliceType.{stype}
"""

    result = _run(
        [],
        python_script=script,
        timeout=20,
        check=False,
        container=container,
    )
    return result


def create_iso_surface(
    var_name: str,
    value: float,
    container: Optional[str] = None,
) -> CommandResult:
    """
    Create an iso-surface.

    Args:
        var_name: Variable for iso-surface
        value: Iso-value

    Returns:
        CommandResult
    """
    script = f"""\
import tecplot
from tecplot.constant import *
tecplot.session.connect()
frame = tecplot.active_frame()
plot = frame.plot()
plot.show_isosurfaces = True
plot.isosurface(0).variable = frame.dataset.variable('{var_name}')
plot.isosurface(0).isosurface_values[0] = {value}
"""

    result = _run(
        [],
        python_script=script,
        timeout=20,
        check=False,
        container=container,
    )
    return result


def create_streamtrace(
    container: Optional[str] = None,
) -> CommandResult:
    """
    Create streamtraces.

    Returns:
        CommandResult
    """
    script = """\
import tecplot
from tecplot.constant import *
tecplot.session.connect()
frame = tecplot.active_frame()
plot = frame.plot()
plot.show_streamtraces = True
"""

    result = _run(
        [],
        python_script=script,
        timeout=20,
        check=False,
        container=container,
    )
    return result
