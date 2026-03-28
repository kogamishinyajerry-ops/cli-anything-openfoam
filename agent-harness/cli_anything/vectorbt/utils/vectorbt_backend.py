"""
vectorbt_backend.py - VectorBT CLI wrapper

VectorBT is a Python library for vectorized backtesting.
It is used via Python scripts, not a native CLI binary.

Operations:
  - Run backtests with config
  - Generate performance reports
  - Plot charts (saved as HTML/PNG)

VectorBT install:
  - pip install vectorbt

Principles:
  - MUST call real VectorBT operations, not reimplement
  - VectorBT is a Python library - requires Python environment
  - Uses pandas/numpy for data, plotters for visualization
  - Backtest results are returned as JSON-compatible dicts
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


# -------------------------------------------------------------------
# Version
# -------------------------------------------------------------------

VECTORBT_VERSION = "1.0.0"


# -------------------------------------------------------------------
# Python interpreter
# -------------------------------------------------------------------

def find_python() -> Path:
    """Find Python interpreter."""
    py = os.environ.get("PYTHON_PATH")
    if py:
        return Path(py)
    return Path(sys.executable)


def get_version() -> dict:
    """Get VectorBT version."""
    if os.environ.get("VECTORBT_MOCK"):
        return {"success": True, "version": "0.5.26", "installed": True}

    try:
        result = subprocess.run(
            [str(find_python()), "-c", "import vectorbt; print(vectorbt.__version__)"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode == 0:
            return {"success": True, "version": result.stdout.strip(), "installed": True}
        return {"success": False, "installed": False, "error": result.stderr}
    except Exception as e:
        return {"success": False, "installed": False, "error": str(e)}


# -------------------------------------------------------------------
# Result dataclass
# -------------------------------------------------------------------

@dataclass
class CommandResult:
    """Result of a VectorBT command execution."""
    success: bool
    output: str = ""
    error: str = ""
    returncode: int = 0
    duration_seconds: float = 0.0


# -------------------------------------------------------------------
# Core runner
# -------------------------------------------------------------------

def _run_python(script: str, timeout: int = 120) -> CommandResult:
    """Run a Python script and return result."""
    python = find_python()
    start = time.time()

    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False
        ) as f:
            f.write(script)
            script_path = f.name

        try:
            proc = subprocess.run(
                [str(python), script_path],
                capture_output=True,
                text=True,
                timeout=timeout,
                shell=False,
            )
            duration = time.time() - start

            return CommandResult(
                success=proc.returncode == 0,
                output=proc.stdout,
                error=proc.stderr,
                returncode=proc.returncode,
                duration_seconds=duration,
            )
        finally:
            try:
                os.unlink(script_path)
            except Exception:
                pass
    except subprocess.TimeoutExpired:
        return CommandResult(
            success=False,
            output="",
            error="Script timed out after {}s".format(timeout),
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
# Backtest strategies
# -------------------------------------------------------------------

STRATEGY_TEMPLATES = {
    "sma_cross": """
class SMACross(vbt.IF):
    def __init__(self, fast_period=10, slow_period=30, run_mode='序列'):
        super().__init__(run_mode=run_mode)
        self.fast_period = fast_period
        self.slow_period = slow_period

    def on_bar(self, i, bars):
        fast = bars['close'].vwm(self.fast_period)
        slow = bars['close'].vwm(self.slow_period)
        if fast > slow and not self.position:
            self.buy()
        elif fast < slow and self.position:
            self.sell()
""",
    "rsi": """
class RSIStrat(vbt.IF):
    def __init__(self, period=14, lower=30, upper=70, run_mode='序列'):
        super().__init__(run_mode=run_mode)
        self.period = period
        self.lower = lower
        self.upper = upper

    def on_bar(self, i, bars):
        rsi = bars['close'].rsi(self.period)
        if rsi < self.lower and not self.position:
            self.buy()
        elif rsi > self.upper and self.position:
            self.sell()
""",
    "布林带": """
class BollingerBands(vbt.IF):
    def __init__(self, period=20, num_std=2, run_mode='序列'):
        super().__init__(run_mode=run_mode)
        self.period = period
        self.num_std = num_std

    def on_bar(self, i, bars):
        sma = bars['close'].wm(self.period)
        std = bars['close'].wstd(self.period)
        upper = sma + self.num_std * std
        lower = sma - self.num_std * std
        if bars['close'] < lower and not self.position:
            self.buy()
        elif bars['close'] > upper and self.position:
            self.sell()
""",
}


def run_backtest(
    data_path: str,
    strategy: str = "sma_cross",
    fast_period: int = 10,
    slow_period: int = 30,
    init_cash: float = 100000.0,
    commission: float = 0.001,
    output_path: Optional[str] = None,
    save_plots: bool = False,
) -> CommandResult:
    """
    Run a VectorBT backtest.

    Args:
        data_path: Path to CSV with columns: open, high, low, close, volume
        strategy: Strategy name (sma_cross, rsi, 布林带)
        fast_period: Fast MA period
        slow_period: Slow MA period
        init_cash: Initial cash
        commission: Commission rate
        output_path: Path to save results JSON
        save_plots: Save HTML plots

    Returns:
        CommandResult
    """
    data_p = Path(data_path)
    if not data_p.exists():
        return CommandResult(success=False, error="Data file not found: {}".format(data_path), returncode=1)

    if strategy not in STRATEGY_TEMPLATES:
        return CommandResult(success=False, error="Unknown strategy: {}".format(strategy), returncode=1)

    if os.environ.get("VECTORBT_MOCK"):
        mock_result = {
            "success": True,
            "strategy": strategy,
            "init_cash": init_cash,
            "final_value": init_cash * 1.18,
            "return_pct": 18.3,
            "total_trades": 42,
            "win_rate": 0.62,
            "max_drawdown_pct": 8.5,
            "sharpe_ratio": 1.23,
        }
        output = json.dumps(mock_result)
        if output_path:
            Path(output_path).write_text(output)
        return CommandResult(success=True, output=output, returncode=0)

    strat_code = STRATEGY_TEMPLATES[strategy]

    script = """
import vectorbt as vbt
import pandas as pd
import json

# Load data
data = pd.read_csv("{data_path}", index_col=0, parse_dates=True)

# Run backtest
{vbt_code}

pf = vbt.Portfolio.from_signals(
    data['close'],
    entries=~data['close'].vwm({fast_period}) < data['close'].vwm({slow_period}),
    exits=~data['close'].vwm({fast_period}) > data['close'].vwm({slow_period}),
    init_cash={init_cash},
    commission={commission},
)

# Extract stats
stats = pf.stats()

result = {{
    "success": True,
    "strategy": "{strategy}",
    "init_cash": float(pf.init_cash),
    "final_value": float(pf.value()[-1]),
    "return_pct": float(stats['return']),
    "total_trades": int(stats['total_trades']),
    "win_rate": float(stats.get('win_rate', 0)),
    "max_drawdown_pct": float(stats.get('max_drawdown', 0)),
    "sharpe_ratio": float(stats.get('sharpe_ratio', 0)),
    "profit_factor": float(stats.get('profit_factor', 0)),
}}

print(json.dumps(result))
""".format(
        data_path=data_path,
        vbt_code=strat_code,
        fast_period=fast_period,
        slow_period=slow_period,
        init_cash=init_cash,
        commission=commission,
        strategy=strategy,
    )

    result = _run_python(script)

    if result.success and output_path:
        Path(output_path).write_text(result.output)

    return result


def generate_report(
    results_path: str,
    output_path: str,
    plot: bool = True,
) -> CommandResult:
    """
    Generate an HTML report from backtest results.

    Args:
        results_path: Path to results JSON file
        output_path: Output HTML report path
        plot: Include plots

    Returns:
        CommandResult
    """
    results_p = Path(results_path)
    if not results_p.exists():
        return CommandResult(success=False, error="Results file not found: {}".format(results_path), returncode=1)

    if os.environ.get("VECTORBT_MOCK"):
        html = "<html><body><h1>Backtest Report</h1><p>Mock report</p></body></html>"
        Path(output_path).write_text(html)
        return CommandResult(success=True, output="Report generated: {}".format(output_path), returncode=0)

    script = """
import json
import vectorbt as vbt
from pathlib import Path

results = json.loads(Path("{results_path}").read_text())

html = "<html><head><title>Backtest Report</title></head><body>"
html += "<h1>Backtest Report: {{}}</h1>".format(results.get('strategy', 'Unknown'))
html += "<table>"
for k, v in results.items():
    if k != 'success':
        html += "<tr><td>{{}}</td><td>{{}}</td></tr>".format(k, v)
html += "</table></body></html>"

Path("{output_path}").write_text(html)
print("Report generated: {output_path}")
""".format(results_path=results_path, output_path=output_path)

    return _run_python(script)


def list_strategies() -> dict:
    """List available strategy templates."""
    return {
        "success": True,
        "strategies": list(STRATEGY_TEMPLATES.keys()),
        "descriptions": {
            "sma_cross": "Simple Moving Average crossover",
            "rsi": "Relative Strength Index",
            "布林带": "Bollinger Bands mean reversion",
        },
    }
