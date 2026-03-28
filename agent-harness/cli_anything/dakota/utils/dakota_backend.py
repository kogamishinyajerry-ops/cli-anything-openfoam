"""
dakota_backend.py - Dakota v6.23 CLI wrapper

Wraps real Dakota commands for use by the cli-anything harness.

Dakota is installed at /opt/dakota/bin/ in the cfd-openfoam container.
Executables:
  - dakota        : main CLI
  - dprepro       : pre-processing for parameters
  - fsu_*         : standalone analysis tools

Principles:
- MUST call the real Dakota commands, not reimplement
- Software is a HARD dependency - error clearly if not found
- Always verify output (not just exit 0)
"""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


# -------------------------------------------------------------------
# Installation detection
# -------------------------------------------------------------------

DAKOTA_INSTALL = "/opt/dakota/bin"
DAKOTA_VERSION = "v6.23"


def find_dakota() -> Path:
    """
    Locate Dakota binary directory.

    Returns Path to /opt/dakota/bin.
    Raises RuntimeError if Dakota is not found.
    """
    if os.environ.get("DAKOTA_MOCK"):
        return Path("/usr/bin/true")

    dakota_bin = Path(DAKOTA_INSTALL)
    if not dakota_bin.exists():
        raise RuntimeError(
            f"Dakota is not installed at {DAKOTA_INSTALL}.\n"
            f"Ensure the cfd-openfoam container is running with Dakota v6.23.\n"
            f"Check: docker exec cfd-openfoam ls /opt/dakota/bin/dakota"
        )

    dakota_exe = dakota_bin / "dakota"
    if not dakota_exe.exists():
        raise RuntimeError(
            f"dakota binary not found at {dakota_exe}.\n"
            f"Dakota installation may be corrupted."
        )

    return dakota_bin


# -------------------------------------------------------------------
# Result dataclass
# -------------------------------------------------------------------

@dataclass
class CommandResult:
    """Result of a Dakota command execution."""
    success: bool
    output: str
    error: str = ""
    returncode: int = 0
    duration_seconds: float = 0.0


# -------------------------------------------------------------------
# Core runner
# -------------------------------------------------------------------

CONTAINER_NAME = "cfd-openfoam"


def _quote(s: str) -> str:
    """Quote a string for shell passing through docker exec."""
    s = str(s)
    if " " in s or "'" in s or '"' in s or "$" in s:
        escaped = s.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return f'"{s}"'


def _run_dakota(
    cmd: list[str],
    cwd: Optional[Path] = None,
    env_extra: Optional[dict] = None,
    timeout: Optional[int] = None,
    check: bool = True,
    container: Optional[str] = None,
) -> CommandResult:
    """
    Run a Dakota command inside the cfd-openfoam container.

    Args:
        cmd: Command and arguments as list of strings
        cwd: Working directory for the command
        env_extra: Additional environment variables
        timeout: Max seconds to run (None = no limit)
        check: Raise on non-zero exit (default True)
        container: Docker container name (default: cfd-openfoam)

    Returns:
        CommandResult with success, output, error, returncode, duration
    """
    if os.environ.get("DAKOTA_MOCK"):
        return CommandResult(success=True, output="Dakota ran successfully (mock)", returncode=0)

    start = time.monotonic()

    env = os.environ.copy()
    if env_extra:
        env.update(env_extra)

    cname = container or CONTAINER_NAME

    quoted_cmd = " ".join(_quote(c) for c in cmd)

    docker_cmd = [
        "docker", "exec",
        "-w", str(cwd) if cwd else "/tmp",
        cname,
        "bash", "-c",
        f"/opt/dakota/bin/dakota {_quote(cmd[0])} " +
        " ".join(_quote(c) for c in cmd[1:]) if len(cmd) > 1 else quoted_cmd
    ]

    # Simpler approach: just pass the full command string
    docker_cmd = [
        "docker", "exec",
        "-w", str(cwd) if cwd else "/tmp",
        cname,
        "bash", "-c",
        quoted_cmd
    ]

    try:
        result = subprocess.run(
            docker_cmd,
            cwd=str(cwd) if cwd else None,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=check,
        )
        duration = time.monotonic() - start
        return CommandResult(
            success=result.returncode == 0,
            output=result.stdout,
            error=result.stderr,
            returncode=result.returncode,
            duration_seconds=duration,
        )
    except subprocess.TimeoutExpired as e:
        duration = time.monotonic() - start
        return CommandResult(
            success=False,
            output=e.stdout.decode() if e.stdout else "",
            error=f"Timeout after {timeout}s",
            returncode=-1,
            duration_seconds=duration,
        )
    except subprocess.CalledProcessError as e:
        duration = time.monotonic() - start
        return CommandResult(
            success=False,
            output=e.stdout or "",
            error=e.stderr or "",
            returncode=e.returncode,
            duration_seconds=duration,
        )


# -------------------------------------------------------------------
# Dakota executables
# -------------------------------------------------------------------

def run_dakota(
    input_file: Path,
    case_name: Optional[str] = None,
    param_overrides: Optional[dict[str, str]] = None,
    timeout: Optional[int] = None,
    container: Optional[str] = None,
) -> CommandResult:
    """
    Run Dakota study from an input file.

    Args:
        input_file: Path to Dakota input (.in) file
        case_name: Optional case name for output directories
        param_overrides: Dict of parameter KEY=VALUE overrides to apply
                         to the input file before running
        timeout: Max seconds to run (None = no limit)
        container: Docker container name
    """
    if os.environ.get("DAKOTA_MOCK"):
        return CommandResult(success=True, output="Dakota ran successfully (mock)", returncode=0)

    if not input_file.exists():
        return CommandResult(
            success=False,
            output="",
            error=f"Input file not found: {input_file}",
            returncode=1,
        )

    # Apply param overrides by writing a modified input file
    work_input: Path = input_file
    if param_overrides:
        work_input = _apply_param_overrides(input_file, param_overrides)

    cmd = ["/opt/dakota/bin/dakota", "-i", str(work_input)]
    if case_name:
        cmd += ["--case", case_name]

    return _run_dakota(
        cmd,
        cwd=input_file.parent,
        timeout=timeout,
        container=container,
    )


def _apply_param_overrides(
    input_file: Path,
    overrides: dict[str, str],
) -> Path:
    """
    Apply parameter overrides to a Dakota input file.

    Writes a new temporary input file with overrides applied.
    Handles Dakota DSL KEY = VALUE and KEY = VALUE # comment formats.
    """
    lines = input_file.read_text().splitlines()
    updated_keys: set[str] = set()
    new_lines = []

    override_normalized: dict[str, str] = {k.lower(): v for k, v in overrides.items()}

    for line in lines:
        original = line
        stripped = line.strip()

        # Skip blank lines and comments
        if not stripped or stripped.startswith("#"):
            new_lines.append(original)
            continue

        # Find KEY = VALUE pattern
        # Dakota uses:  keyword = value   or   keyword = value # comment
        eq_match = re.match(r'^(\s*[A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$', stripped)
        if eq_match:
            key = eq_match.group(1).strip()
            rest = eq_match.group(2).strip()

            # Check for inline comment
            value_part = rest.split('#')[0].strip()

            if key.lower() in override_normalized:
                new_value = override_normalized[key.lower()]
                # Preserve comment if any
                comment = ""
                if '#' in rest:
                    comment = "  # " + rest.split('#', 1)[1].strip()
                indent = len(line) - len(line.lstrip())
                new_lines.append(f"{' ' * indent}{key} = {new_value}{comment}")
                updated_keys.add(key.lower())
                continue

        new_lines.append(original)

    # Append any new keys not found in original
    for key, val in overrides.items():
        if key.lower() not in updated_keys:
            new_lines.append(f"{key} = {val}")

    # Write to temp file
    fd, tmp_path = tempfile.mkstemp(suffix=".in", prefix="dakota_")
    with os.fdopen(fd, "w") as f:
        f.write("\n".join(new_lines) + "\n")

    return Path(tmp_path)


# -------------------------------------------------------------------
# Input file parsing
# -------------------------------------------------------------------

def parse_input_file(input_path: Path) -> dict[str, str]:
    """
    Parse a Dakota input (.in) file into a structured dict.

    Extracts top-level blocks and their key=value pairs.
    Handles Dakota's nested block structure:
      environment
        graphics
        tabular_graphics_data
          tabular_graphics_file = 'dakota_results.dat'
      method
        sampling
          sample_type = lhs
          samples = 100

    Returns:
        dict mapping "block.key" -> "value"
    """
    params: dict[str, str] = {}
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    text = input_path.read_text()
    current_block = ""

    for line in text.splitlines():
        stripped = line.strip()

        # Skip blank lines and comments
        if not stripped or stripped.startswith("#"):
            continue

        # Block header (no = sign, ends with {
        if stripped.endswith("{") and "=" not in stripped:
            current_block = stripped.rstrip("{").strip()
            continue

        # End of block
        if stripped == "}":
            current_block = ""
            continue

        # Key = Value
        eq_match = re.match(r'^(\s*[A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$', stripped)
        if eq_match:
            key = eq_match.group(1).strip()
            value = eq_match.group(2).strip()

            # Remove trailing comment
            if "#" in value:
                value = value.split("#")[0].strip()

            if current_block:
                params[f"{current_block}.{key}"] = value
            else:
                params[key] = value

    return params


# -------------------------------------------------------------------
# Output parsing
# -------------------------------------------------------------------

def parse_dakota_output(log_text: str) -> dict:
    """
    Parse Dakota output text for study metrics.

    Extracts:
      - method used (sampling, optimization, etc.)
      - number of samples / evaluations
      - variables and responses summary
      - any error/warning messages
      - convergence info
    """
    info: dict = {
        "method": None,
        "samples": None,
        "variables": None,
        "responses": None,
        "converged": False,
        "error": "",
        "warnings": [],
    }

    # Method detection
    method_match = re.search(r"method\s*=\s*(\w+)", log_text, re.IGNORECASE)
    if method_match:
        info["method"] = method_match.group(1)

    # Sampling info
    samples_match = re.search(r"(\d+)\s+samples?", log_text, re.IGNORECASE)
    if samples_match:
        info["samples"] = int(samples_match.group(1))

    # Number of function evaluations
    eval_match = re.search(r"(\d+)\s+function\s+evaluations?", log_text, re.IGNORECASE)
    if eval_match:
        info["evaluations"] = int(eval_match.group(1))

    # Variables count
    var_match = re.search(r"(\d+)\s+continuous\s+design\s+variables?", log_text, re.IGNORECASE)
    if var_match:
        info["variables"] = int(var_match.group(1))

    # Responses count
    resp_match = re.search(r"(\d+)\s+(?:objective\s+functions?|responses?)", log_text, re.IGNORECASE)
    if resp_match:
        info["responses"] = int(resp_match.group(1))

    # Convergence markers
    if re.search(r"convergence\s+achieved|optimization\s+completed", log_text, re.IGNORECASE):
        info["converged"] = True

    # Error detection
    error_lines = []
    for line in log_text.splitlines():
        if re.search(r"^\s*\*\*\*\* Error", line, re.IGNORECASE):
            error_lines.append(line.strip())
        elif re.search(r"^\s*Error:", line, re.IGNORECASE):
            error_lines.append(line.strip())
    if error_lines:
        info["error"] = " | ".join(error_lines[:5])

    # Warnings
    warn_lines = []
    for line in log_text.splitlines():
        if re.search(r"^\s*Warning:", line, re.IGNORECASE):
            warn_lines.append(line.strip())
    info["warnings"] = warn_lines[:10]

    # CPU time
    cpu_match = re.search(r"Total CPU time\s*[:=]\s*([0-9.eE+-]+)\s*s", log_text, re.IGNORECASE)
    if cpu_match:
        info["cpu_time_seconds"] = float(cpu_match.group(1))

    return info


def parse_results_file(results_path: Path) -> list[dict]:
    """
    Parse a Dakota results file (dakota_results.dat).

    This is a tab/comma-separated file with parameter values
    and response values from the study.

    Returns:
        List of dicts, one per sample/evaluation.
    """
    if not results_path.exists():
        return []

    lines = results_path.read_text().splitlines()
    if len(lines) < 2:
        return []

    # First line is header
    header = lines[0].strip()
    # Detect delimiter
    if "\t" in header:
        delim = "\t"
    elif "," in header:
        delim = ","
    else:
        delim = None

    headers = [h.strip() for h in header.split(delim) if h.strip()]

    records = []
    for line in lines[1:]:
        line = line.strip()
        if not line:
            continue
        values = [v.strip() for v in line.split(delim)]
        if len(values) == len(headers):
            record = {}
            for h, v in zip(headers, values):
                try:
                    record[h] = float(v)
                except ValueError:
                    record[h] = v
            records.append(record)

    return records
