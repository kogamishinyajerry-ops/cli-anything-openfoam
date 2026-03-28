"""
backtrader_backend.py - Backtrader CLI wrapper

Wraps Backtrader backtesting operations via Python execution.

Backtrader is installed via:
  - pip install backtrader

Principles:
  - MUST call real Backtrader operations, not reimplement
  - Pure Python backtesting framework
  - Operations via Python scripts + data feeds
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

BACKTRADER_VERSION = "1.0.0"


# -------------------------------------------------------------------
# Installation detection
# -------------------------------------------------------------------

def find_python() -> Path:
    """Find Python interpreter."""
    py = os.environ.get("PYTHON_PATH")
    if py:
        return Path(py)
    return Path(sys.executable)


def get_version() -> dict:
    """Get Backtrader version."""
    if os.environ.get("BACKTRADER_MOCK"):
        return {"success": True, "version": "1.9.78.123", "installed": True}

    try:
        result = subprocess.run(
            [sys.executable, "-c", "import backtrader as bt; print(bt.__version__)"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode == 0:
            return {
                "success": True,
                "version": result.stdout.strip(),
                "installed": True,
            }
        return {"success": False, "installed": False, "error": "backtrader not importable"}
    except Exception as e:
        return {"success": False, "installed": False, "error": str(e)}


# -------------------------------------------------------------------
# Result dataclass
# -------------------------------------------------------------------

@dataclass
class CommandResult:
    """Result of a Backtrader command execution."""
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
# Strategy templates
# -------------------------------------------------------------------

_STRAT_SMA = """
class SMACross(bt.Strategy):
    params = (("fast_period", 10), ("slow_period", 30))

    def __init__(self):
        sma_fast = bt.ind.SMA(period=self.p.fast_period)
        sma_slow = bt.ind.SMA(period=self.p.slow_period)
        self.crossover = bt.ind.CrossOver(sma_fast, sma_slow)

    def next(self):
        if self.crossover > 0:
            self.buy()
        elif self.crossover < 0:
            self.sell()
"""

_STRAT_RSI = """
class RSIStrat(bt.Strategy):
    params = (("rsi_period", 14), ("rsi_upper", 70), ("rsi_lower", 30))

    def __init__(self):
        self.rsi = bt.ind.RSI(period=self.p.rsi_period)

    def next(self):
        if self.rsi < self.p.rsi_lower and not self.position:
            self.buy()
        elif self.rsi > self.p.rsi_upper and self.position:
            self.sell()
"""

_STRAT_MACD = """
class MACDStrat(bt.Strategy):
    def __init__(self):
        macd = bt.ind.MACD()
        self.signal = macd.signal

    def next(self):
        if self.signal > 0 and not self.position:
            self.buy()
        elif self.signal < 0 and self.position:
            self.sell()
"""

_STRAT_MEAN_REV = """
class MeanRev(bt.Strategy):
    params = (("period", 20), ("devfactor", 2.0))

    def __init__(self):
        self.sma = bt.ind.SMA(period=self.p.period)
        self.stddev = bt.ind.StandardDeviation(period=self.p.period)

    def next(self):
        upper = self.sma + self.p.devfactor * self.stddev
        lower = self.sma - self.p.devfactor * self.stddev
        if self.data.close < lower and not self.position:
            self.buy()
        elif self.data.close > upper and self.position:
            self.sell()
"""

STRATEGY_TEMPLATES = {
    "sma_crossover": _STRAT_SMA,
    "rsi": _STRAT_RSI,
    "macd": _STRAT_MACD,
    "mean_reversion": _STRAT_MEAN_REV,
}

STRATEGY_CLASSES = {
    "sma_crossover": "SMACross",
    "rsi": "RSIStrat",
    "macd": "MACDStrat",
    "mean_reversion": "MeanRev",
}


# -------------------------------------------------------------------
# Data operations
# -------------------------------------------------------------------

def load_csv_data(
    data_path: str,
    name: str = "Data",
) -> dict:
    """Parse CSV data file info."""
    path = Path(data_path)
    if not path.exists():
        return {"success": False, "error": "Data file not found: {}".format(data_path)}

    try:
        lines = path.read_text().split("\n")
        rows = sum(1 for line in lines if line.strip())
        return {
            "success": True,
            "path": str(path),
            "name": name,
            "rows": rows,
            "preview": "\n".join(lines[:6]),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# -------------------------------------------------------------------
# Backtest
# -------------------------------------------------------------------

def run_backtest(
    data_path: str,
    strategy: str = "sma_crossover",
    cash: float = 10000.0,
    commission: float = 0.0,
    fast_period: int = 10,
    slow_period: int = 30,
    rsi_period: int = 14,
    rsi_upper: int = 70,
    rsi_lower: int = 30,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    output_path: Optional[str] = None,
) -> CommandResult:
    """
    Run a backtest.
    """
    data_p = Path(data_path)
    if not data_p.exists():
        return CommandResult(success=False, error="Data file not found: {}".format(data_path), returncode=1)

    if strategy not in STRATEGY_TEMPLATES:
        return CommandResult(success=False, error="Unknown strategy: {}".format(strategy), returncode=1)

    class_name = STRATEGY_CLASSES[strategy]
    strat_code = STRATEGY_TEMPLATES[strategy]

    # Set params based on strategy type
    if strategy == "sma_crossover":
        params_str = "fast_period={}, slow_period={}".format(fast_period, slow_period)
    elif strategy == "rsi":
        params_str = "rsi_period={}, rsi_upper={}, rsi_lower={}".format(rsi_period, rsi_upper, rsi_lower)
    elif strategy == "mean_reversion":
        params_str = "period=20, devfactor=2.0"
    else:
        params_str = ""

    from_str = "datetime.datetime({})".format(from_date) if from_date else "None"
    to_str = "datetime.datetime({})".format(to_date) if to_date else "None"

    script = """
import backtrader as bt
import json
import datetime

{}

cerebro = bt.Cerebro()
cerebro.addstrategy({}, {})
cerebro.adddata(bt.feeds.GenericCSVData(
    dataname="{}",
    fromdate={},
    todate={},
    dtformat="%Y-%m-%d",
    datetime=0, open=1, high=2, low=3, close=4, volume=5, openinterest=-1,
))
cerebro.broker.setcash({})
cerebro.broker.setcommission(commission={})

results = cerebro.run()
strat = results[0]
portfolio_value = cerebro.broker.getvalue()

output = {{
    "success": True,
    "strategy": "{}",
    "final_value": round(portfolio_value, 2),
    "cash": round(cerebro.broker.getcash(), 2),
    "starting_cash": {},
    "return_pct": round((portfolio_value - {}) / {} * 100, 2),
    "trades": 0,
}}
print(json.dumps(output))
""".format(
        strat_code, class_name, params_str,
        data_path, from_str, to_str,
        cash, commission,
        strategy, cash, cash, cash
    )

    if os.environ.get("BACKTRADER_MOCK"):
        mock_result = {
            "success": True,
            "strategy": strategy,
            "final_value": cash * 1.123,
            "cash": cash * 0.05,
            "starting_cash": cash,
            "return_pct": 12.3,
            "trades": 15,
        }
        if output_path:
            Path(output_path).write_text(json.dumps(mock_result, indent=2))
        return CommandResult(
            success=True,
            output=json.dumps(mock_result, indent=2),
            returncode=0,
        )

    result = _run_python(script)

    if result.success and output_path:
        Path(output_path).write_text(result.output)

    return result


def run_backtest_with_analyzers(
    data_path: str,
    strategy: str = "sma_crossover",
    cash: float = 10000.0,
    output_path: Optional[str] = None,
) -> CommandResult:
    """Run backtest with full analyzer output."""
    if strategy not in STRATEGY_TEMPLATES:
        return CommandResult(success=False, error="Unknown strategy: {}".format(strategy), returncode=1)

    class_name = STRATEGY_CLASSES[strategy]
    strat_code = STRATEGY_TEMPLATES[strategy]

    script = """
import backtrader as bt
import json

{}

cerebro = bt.Cerebro()
cerebro.addstrategy({})

cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name="sharpe")
cerebro.addanalyzer(bt.analyzers.Returns, _name="returns")
cerebro.addanalyzer(bt.analyzers.DrawDown, _name="drawdown")

cerebro.adddata(bt.feeds.GenericCSVData(
    dataname="{}",
    fromdate=None, todate=None,
    dtformat="%Y-%m-%d",
    datetime=0, open=1, high=2, low=3, close=4, volume=5, openinterest=-1,
))
cerebro.broker.setcash({})

results = cerebro.run()
strat = results[0]

sharpe = strat.analyzers.sharpe.get_analysis()
returns = strat.analyzers.returns.get_analysis()
dd = strat.analyzers.drawdown.get_analysis()

output = {{
    "success": True,
    "strategy": "{}",
    "final_value": round(cerebro.broker.getvalue(), 2),
    "starting_cash": {},
    "sharpe_ratio": sharpe.get("sharperatio"),
    "annual_return": returns.get("rnorm100"),
    "max_drawdown_pct": dd.get("max", {{}}).get("drawdown"),
}}
print(json.dumps(output))
""".format(strat_code, class_name, data_path, cash, strategy, cash)

    if os.environ.get("BACKTRADER_MOCK"):
        mock = {
            "success": True,
            "strategy": strategy,
            "final_value": cash * 1.15,
            "starting_cash": cash,
            "sharpe_ratio": 1.23,
            "annual_return": 15.4,
            "max_drawdown_pct": 8.5,
        }
        if output_path:
            Path(output_path).write_text(json.dumps(mock, indent=2))
        return CommandResult(success=True, output=json.dumps(mock, indent=2), returncode=0)

    result = _run_python(script)

    if result.success and output_path:
        Path(output_path).write_text(result.output)

    return result


def list_strategies() -> dict:
    """List available strategy templates."""
    return {
        "success": True,
        "strategies": list(STRATEGY_TEMPLATES.keys()),
    }


def get_strategy_info(strategy: str) -> dict:
    """Get info about a strategy."""
    if strategy not in STRATEGY_TEMPLATES:
        return {"success": False, "error": "Unknown strategy: {}".format(strategy)}

    info = {
        "sma_crossover": {
            "name": "SMA Crossover",
            "params": ["fast_period", "slow_period"],
            "description": "Buy when fast SMA crosses above slow SMA, sell on reverse",
        },
        "rsi": {
            "name": "RSI",
            "params": ["rsi_period", "rsi_upper", "rsi_lower"],
            "description": "Buy when RSI oversold, sell when RSI overbought",
        },
        "macd": {
            "name": "MACD",
            "params": [],
            "description": "Buy/sell on MACD signal line crossovers",
        },
        "mean_reversion": {
            "name": "Mean Reversion",
            "params": ["period", "devfactor"],
            "description": "Buy at lower band, sell at upper band (Bollinger-style)",
        },
    }

    return {
        "success": True,
        "strategy": strategy,
        **info[strategy],
    }


# -------------------------------------------------------------------
# Generate strategy file
# -------------------------------------------------------------------

def generate_strategy(
    strategy: str,
    output_path: Optional[str] = None,
) -> dict:
    """Generate a strategy Python file."""
    if strategy not in STRATEGY_TEMPLATES:
        return {"success": False, "error": "Unknown strategy: {}".format(strategy)}

    class_name = STRATEGY_CLASSES[strategy]
    strat_body = STRATEGY_TEMPLATES[strategy].strip()

    lines = [
        '"""',
        "Backtrader strategy: {}".format(strategy),
        "Generated by cli-anything-backtrader",
        '"""',
        "",
        "import backtrader as bt",
        "",
        "",
        "class {}(bt.Strategy):".format(class_name),
        '    """Generated strategy: {}"""'.format(strategy),
        "",
        strat_body,
        "",
        "",
        'if __name__ == "__main__":',
        "    import json",
        "    cerebro = bt.Cerebro()",
        "    cerebro.addstrategy({})".format(class_name),
        "    results = cerebro.run()",
        '    print(json.dumps({{"status": "ok", "strategy": "{}"}}))'.format(strategy),
        "",
    ]
    content = "\n".join(lines)

    if output_path:
        Path(output_path).resolve().parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text(content)

    return {
        "success": True,
        "strategy": strategy,
        "path": str(output_path) if output_path else None,
        "content": content,
    }


# -------------------------------------------------------------------
# Fetch Yahoo data
# -------------------------------------------------------------------

def fetch_yahoo_data(
    ticker: str,
    start: str,
    end: str,
    output_path: Optional[str] = None,
) -> CommandResult:
    """Fetch Yahoo Finance data as CSV."""
    script = (
        "import yfinance as yf\n"
        "import json\n"
        "data = yf.download('{}', start='{}', end='{}')\n"
        "outpath = '{}'\n"
        "data.to_csv(outpath)\n"
        "print(json.dumps({{'success': True, 'ticker': '{}', 'rows': len(data), 'path': outpath}}))\n"
    ).format(ticker, start, end, output_path or "yahoo_data.csv", ticker)

    if os.environ.get("BACKTRADER_MOCK"):
        out = Path(output_path) if output_path else Path("yahoo_data.csv")
        out.write_text("Date,Open,High,Low,Close,Adj Close,Volume\n2024-01-01,100,101,99,100,100,1000\n")
        return CommandResult(
            success=True,
            output=json.dumps({"success": True, "ticker": ticker, "rows": 1}),
            returncode=0,
        )

    return _run_python(script, timeout=60)


# -------------------------------------------------------------------
# Format info
# -------------------------------------------------------------------

def get_data_format_info() -> dict:
    """Get required CSV format for data files."""
    return {
        "success": True,
        "format": "CSV with columns: Date, Open, High, Low, Close, Volume",
        "columns": {
            "datetime": 0,
            "open": 1,
            "high": 2,
            "low": 3,
            "close": 4,
            "volume": 5,
            "openinterest": -1,
        },
        "dtformat": "%Y-%m-%d",
        "note": "Column indices are configurable in run-backtest",
    }
