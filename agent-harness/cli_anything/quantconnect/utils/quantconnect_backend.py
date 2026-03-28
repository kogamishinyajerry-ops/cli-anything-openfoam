"""
quantconnect_backend.py - QuantConnect Lean CLI wrapper

Wraps QuantConnect Lean engine CLI for algorithmic trading backtesting.

Lean CLI commands:
  - lean create-project <name>     Create a new QC project
  - lean backtest <project>        Run backtest
  - lean live <project>             Deploy live trading
  - lean optimize <project>        Run optimization
  - lean report <backtest-id>       Generate report
  - lean init                      Initialize configuration

Installation:
  - dotnet tool install -g QuantConnect.Lean.Cli

Configuration:
  - QuantConnect API token required (from quantconnect.com)
  - Set QC_API_TOKEN environment variable

Principles:
  - MUST call real Lean CLI, not reimplement
  - Lean is a .NET tool invoked via `dotnet lean` or `lean`
  - Supports Python and C# algorithms
  - Backtests run locally or on QuantConnect cloud
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

QUANTCONNECT_VERSION = "1.0.0"


# -------------------------------------------------------------------
# Installation detection
# -------------------------------------------------------------------

LEAN_PATHS = [
    "/usr/local/bin/lean",
    "/usr/bin/lean",
    Path.home() / ".dotnet/tools/lean",
]


def find_lean() -> Path:
    """Locate Lean CLI binary."""
    if os.environ.get("QC_MOCK"):
        return Path("/usr/bin/true")

    # Check DOTNET_TOOLS_PATH
    dotnet_tools = os.environ.get("DOTNET_TOOLS_PATH", "")
    if dotnet_tools:
        p = Path(dotnet_tools) / "lean"
        if p.exists():
            return p

    for candidate in LEAN_PATHS:
        p = Path(candidate)
        if p.exists():
            return p

    try:
        result = subprocess.run(
            ["which", "lean"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            return Path(result.stdout.strip())
    except Exception:
        pass

    # Try dotnet lean
    try:
        result = subprocess.run(
            ["dotnet", "lean", "--version"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode == 0:
            return Path("dotnet")  # placeholder, actual invocation uses dotnet lean
    except Exception:
        pass

    raise RuntimeError(
        "QuantConnect Lean CLI not found.\n"
        "Install with: dotnet tool install -g QuantConnect.Lean.Cli\n"
        "Or: pip install quantconnect\n"
        "Download: https://www.quantconnect.com/lean\n"
        "Set QC_MOCK=1 for testing without installation."
    )


# -------------------------------------------------------------------
# Result dataclass
# -------------------------------------------------------------------

@dataclass
class CommandResult:
    """Result of a QuantConnect command execution."""
    success: bool
    output: str = ""
    error: str = ""
    returncode: int = 0
    duration_seconds: float = 0.0


# -------------------------------------------------------------------
# Core runner
# -------------------------------------------------------------------

def _run(args: list, timeout: int = 300, check: bool = True) -> CommandResult:
    """Run Lean CLI command."""
    lean = find_lean()
    cmd = [str(lean)] + args if str(lean) != "dotnet" else ["dotnet", "lean"] + args

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
    """Get Lean CLI version."""
    if os.environ.get("QC_MOCK"):
        return {"success": True, "version": "2.0.0", "engine": "Lean", "api": "v2"}

    result = _run(["--version"], timeout=15, check=False)
    if result.success:
        v = result.output.strip()
        return {"success": True, "version": v, "engine": "Lean"}
    return {"success": False, "error": result.error}


def get_status() -> dict:
    """Get QuantConnect status / connectivity."""
    if os.environ.get("QC_MOCK"):
        return {
            "success": True,
            "api_connected": True,
            "data_feed": "running",
            "algorithm": "idle",
        }

    result = _run(["status"], timeout=15, check=False)
    if result.success:
        return {"success": True, "output": result.output}
    return {"success": False, "error": result.error}


# -------------------------------------------------------------------
# Project management
# -------------------------------------------------------------------

def create_project(
    name: str,
    language: str = "python",
    directory: Optional[str] = None,
) -> CommandResult:
    """
    Create a new QuantConnect project.

    Args:
        name: Project name
        language: 'python' or 'csharp'
        directory: Parent directory

    Returns:
        CommandResult
    """
    if os.environ.get("QC_MOCK"):
        return CommandResult(
            success=True,
            output="Successfully created project '{}' at ./{qcdir}/".format(name, qcdir=directory or "."),
            returncode=0,
        )

    args = ["create-project", name, "--language", language]
    if directory:
        args.extend(["--directory", directory])

    return _run(args, timeout=30, check=False)


def list_projects(directory: Optional[str] = None) -> dict:
    """
    List local QuantConnect projects.

    Returns dict with project list.
    """
    if os.environ.get("QC_MOCK"):
        return {
            "success": True,
            "projects": [
                {"name": "my-algorithm", "language": "python", "path": "./MyAlgorithm"},
                {"name": "mean-reversion", "language": "csharp", "path": "./MeanReversion"},
            ],
        }

    dir_path = Path(directory) if directory else Path.cwd()
    projects = []
    for item in dir_path.iterdir():
        if item.is_dir() and (item / "main.py").exists() or (item / "Main.cs").exists():
            lang = "python" if (item / "main.py").exists() else "csharp"
            projects.append({"name": item.name, "language": lang, "path": str(item)})

    return {"success": True, "projects": projects}


# -------------------------------------------------------------------
# Backtesting
# -------------------------------------------------------------------

def run_backtest(
    project_path: str,
    output_dir: Optional[str] = None,
    detach: bool = False,
    estimate: bool = False,
) -> CommandResult:
    """
    Run a Lean backtest.

    Args:
        project_path: Path to project directory
        output_dir: Output directory for results
        detach: Run in background
        estimate: Estimate runtime without executing

    Returns:
        CommandResult
    """
    proj = Path(project_path)
    if not proj.exists():
        return CommandResult(
            success=False,
            error="Project not found: {}".format(proj),
            returncode=1,
        )

    if os.environ.get("QC_MOCK"):
        return CommandResult(
            success=True,
            output="Backtest completed: 100 steps, 42 trades, return 12.5%",
            returncode=0,
        )

    args = ["backtest", str(proj)]
    if output_dir:
        args.extend(["--output", output_dir])
    if detach:
        args.append("--detach")
    if estimate:
        args.append("--estimate")

    return _run(args, timeout=600, check=False)


def read_backtest_results(results_path: str) -> dict:
    """
    Read and parse backtest results JSON.

    Returns dict with backtest statistics.
    """
    path = Path(results_path)
    if not path.exists():
        return {"success": False, "error": "Results file not found: {}".format(path)}

    if os.environ.get("QC_MOCK"):
        return {
            "success": True,
            "statistics": {
                "Profit/Loss": "$1,250.00",
                "Return": "12.5%",
                "Total Trades": 42,
                "Avg Win": "$150.00",
                "Avg Loss": "$-80.00",
                "Win Rate": "64.3%",
                "Sharpe Ratio": "1.45",
                "Max Drawdown": "8.2%",
            },
        }

    try:
        data = json.loads(path.read_text())
        return {"success": True, "data": data}
    except Exception as e:
        return {"success": False, "error": str(e)}


# -------------------------------------------------------------------
# Live trading
# -------------------------------------------------------------------

def deploy_live(
    project_path: str,
    broker: str = "paper",
    auto: bool = False,
) -> CommandResult:
    """
    Deploy algorithm to live trading.

    Args:
        project_path: Path to project
        broker: 'paper', 'interactive-brokers', 'alpaca', etc.
        auto: Automatic order execution

    Returns:
        CommandResult
    """
    proj = Path(project_path)
    if not proj.exists():
        return CommandResult(success=False, error="Project not found", returncode=1)

    if os.environ.get("QC_MOCK"):
        return CommandResult(
            success=True,
            output="Live deployment complete (paper trading): algo_id=qc-algo-12345",
            returncode=0,
        )

    args = ["live", str(proj), "--broker", broker]
    if auto:
        args.append("--auto")

    return _run(args, timeout=60, check=False)


# -------------------------------------------------------------------
# Optimization
# -------------------------------------------------------------------

def optimize(
    project_path: str,
    output_dir: Optional[str] = None,
) -> CommandResult:
    """
    Run parameter optimization.

    Args:
        project_path: Path to project
        output_dir: Output directory for results

    Returns:
        CommandResult
    """
    proj = Path(project_path)
    if not proj.exists():
        return CommandResult(success=False, error="Project not found", returncode=1)

    if os.environ.get("QC_MOCK"):
        return CommandResult(
            success=True,
            output="Optimization complete: 150/200 runs, best params: period=30, threshold=0.65",
            returncode=0,
        )

    args = ["optimize", str(proj)]
    if output_dir:
        args.extend(["--output", output_dir])

    return _run(args, timeout=1800, check=False)
