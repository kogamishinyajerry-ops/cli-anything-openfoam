"""
backtrader_cli.py - Click CLI for cli-anything-backtrader

Commands:
  backtest     - Run strategy backtest
  strategies   - List/describe strategies
  generate     - Generate strategy file
  data         - Data operations (info, fetch)
  info         - Version and format info

All commands support --json for machine-readable output.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import click

from .utils import backtrader_backend as bb

__all__ = ["main"]

JSON_MODE = False


def echo(msg: str, **kwargs) -> None:
    click.echo(msg, err=True, **kwargs)


def success(msg: str) -> None:
    click.echo(f"[OK] {msg}", err=True)


def error(msg: str) -> None:
    click.echo(f"[ERROR] {msg}", err=True, color="red")


def json_out(data: dict) -> None:
    click.echo(json.dumps(data, indent=2))


# -------------------------------------------------------------------
# Main
# -------------------------------------------------------------------

@click.group(invoke_without_command=True)
@click.option("--json", "json_output", is_flag=True, help="JSON output mode")
@click.pass_context
def cli(ctx, json_output: bool):
    """Backtrader Quantitative Trading — backtest trading strategies from the CLI.

    Backtrader is a pure-Python backtesting framework for trading strategies.
    Supports SMA crossover, RSI, MACD, Mean Reversion and custom strategies.

    Examples:
      backtrader info format
      backtrader data fetch --ticker AAPL --start 2024-01-01 --end 2024-12-31
      backtrader strategies list
      backtrader backtest run --data prices.csv --strategy sma_crossover
    """
    global JSON_MODE
    JSON_MODE = json_output
    ctx.ensure_object(dict)
    ctx.obj["json"] = json_output

    if ctx.invoked_subcommand is None:
        echo("Backtrader harness (CLI wrapper)")
        v = bb.get_version()
        if v.get("success"):
            echo(f"Version: {v['version']}")
        else:
            echo("Backtrader: not installed")


# ==================================================================
# info command
# ==================================================================

@cli.group("info")
def cmd_info():
    """Version and settings information."""
    pass


@cmd_info.command("version")
def cmd_version():
    """Show Backtrader version."""
    global JSON_MODE
    v = bb.get_version()
    if JSON_MODE:
        json_out(v)
    else:
        if v.get("success"):
            echo(f"Backtrader {v['version']}")
            echo(f"Installed: {v.get('installed', True)}")
        else:
            error("Backtrader not installed")
            echo(f"  {v.get('error', '')}")


@cmd_info.command("format")
def cmd_format():
    """Show required CSV data format."""
    global JSON_MODE
    info = bb.get_data_format_info()
    if JSON_MODE:
        json_out(info)
    else:
        echo("Required CSV columns (by index):")
        for col, idx in info["columns"].items():
            echo(f"  {col}: {idx}")
        echo(f"\nDate format: {info['dtformat']}")
        echo(f"\nExample header:")
        echo("  Date,Open,High,Low,Close,Adj Close,Volume")


# ==================================================================
# data command
# ==================================================================

@cli.group("data")
def cmd_data():
    """Data operations."""
    pass


@cmd_data.command("info")
@click.option("--data", "-d", required=True, help="CSV data file path")
def cmd_data_info(data: str):
    """Show data file info."""
    global JSON_MODE
    info = bb.load_csv_data(data)
    if JSON_MODE:
        json_out(info)
    else:
        if info.get("success"):
            echo(f"Path: {info['path']}")
            echo(f"Rows: {info['rows']}")
            echo(f"\nPreview (first 5 lines):")
            echo(info.get("preview", ""))
        else:
            error("Failed to read data file")
            echo(f"  {info.get('error', '')}")


@cmd_data.command("fetch")
@click.option("--ticker", "-t", required=True, help="Yahoo ticker symbol")
@click.option("--start", "-s", required=True, help="Start date (YYYY-MM-DD)")
@click.option("--end", "-e", required=True, help="End date (YYYY-MM-DD)")
@click.option("--output", "-o", help="Output CSV path")
def cmd_data_fetch(ticker: str, start: str, end: str, output: Optional[str]):
    """Fetch Yahoo Finance data as CSV."""
    global JSON_MODE
    result = bb.fetch_yahoo_data(ticker, start, end, output)

    if JSON_MODE:
        json_out({"success": result.success, "output": result.output, "error": result.error})
    else:
        if result.success:
            success(f"Data fetched: {ticker}")
            try:
                d = json.loads(result.output)
                echo(f"  Rows: {d.get('rows', '?')}")
                echo(f"  Path: {d.get('path', output or 'yahoo_data.csv')}")
            except Exception:
                echo(result.output[:200])
        else:
            error("Failed to fetch data")
            echo(f"  {result.error[:200]}")


# ==================================================================
# strategies command
# ==================================================================

@cli.group("strategies")
def cmd_strategies():
    """Strategy operations."""
    pass


@cmd_strategies.command("list")
def cmd_strategies_list():
    """List available strategy templates."""
    global JSON_MODE
    info = bb.list_strategies()
    if JSON_MODE:
        json_out(info)
    else:
        if info.get("success"):
            echo("Available strategies:")
            for s in info.get("strategies", []):
                echo(f"  - {s}")


@cmd_strategies.command("info")
@click.option("--strategy", "-s", required=True, help="Strategy name")
def cmd_strategies_info(strategy: str):
    """Get strategy details."""
    global JSON_MODE
    info = bb.get_strategy_info(strategy)
    if JSON_MODE:
        json_out(info)
    else:
        if info.get("success"):
            echo(f"Strategy: {info.get('name', strategy)}")
            echo(f"Key: {info.get('strategy', '')}")
            echo(f"Params: {', '.join(info.get('params', [])) or 'none'}")
            echo(f"\n{info.get('description', '')}")
        else:
            error(f"Unknown strategy: {strategy}")


@cmd_strategies.command("generate")
@click.option("--strategy", "-s", required=True, help="Strategy name")
@click.option("--output", "-o", help="Output file path")
def cmd_strategies_generate(strategy: str, output: Optional[str]):
    """Generate a strategy Python file."""
    global JSON_MODE
    result = bb.generate_strategy(strategy, output)
    if JSON_MODE:
        json_out(result)
    else:
        if result.get("success"):
            success(f"Generated: {result.get('path', 'stdout')}")
            if output:
                echo(f"  Saved to: {output}")
            else:
                echo("---")
                echo(result.get("content", "")[:500])
                echo("---")
        else:
            error(f"Generation failed: {result.get('error', '')}")


# ==================================================================
# backtest command
# ==================================================================

@cli.group("backtest")
def cmd_backtest():
    """Run backtest operations."""
    pass


@cmd_backtest.command("run")
@click.option("--data", "-d", required=True, help="CSV data file path")
@click.option("--strategy", "-st", default="sma_crossover",
              type=click.Choice(["sma_crossover", "rsi", "macd", "mean_reversion"]),
              help="Strategy name")
@click.option("--cash", "-c", type=float, default=10000.0, help="Starting cash")
@click.option("--commission", "-cm", type=float, default=0.0, help="Commission rate")
@click.option("--fast-period", type=int, help="Fast period (for sma_crossover)")
@click.option("--slow-period", type=int, help="Slow period (for sma_crossover)")
@click.option("--rsi-period", type=int, help="RSI period")
@click.option("--rsi-upper", type=int, help="RSI upper threshold")
@click.option("--rsi-lower", type=int, help="RSI lower threshold")
@click.option("--from", "from_date", help="Start date YYYY-MM-DD")
@click.option("--to", "to_date", help="End date YYYY-MM-DD")
@click.option("--output", "-o", help="Results JSON output path")
def cmd_backtest_run(
    data: str,
    strategy: str,
    cash: float,
    commission: float,
    fast_period: Optional[int],
    slow_period: Optional[int],
    rsi_period: Optional[int],
    rsi_upper: Optional[int],
    rsi_lower: Optional[int],
    from_date: Optional[str],
    to_date: Optional[str],
    output: Optional[str],
):
    """Run a backtest."""
    global JSON_MODE

    result = bb.run_backtest(
        data_path=data,
        strategy=strategy,
        cash=cash,
        commission=commission,
        fast_period=fast_period or 10,
        slow_period=slow_period or 30,
        rsi_period=rsi_period or 14,
        rsi_upper=rsi_upper or 70,
        rsi_lower=rsi_lower or 30,
        from_date=from_date,
        to_date=to_date,
        output_path=output,
    )

    if JSON_MODE:
        try:
            json_out(json.loads(result.output))
        except Exception:
            json_out({"success": result.success, "output": result.output, "error": result.error})
    else:
        if result.success:
            try:
                d = json.loads(result.output)
                success("Backtest complete")
                echo(f"  Strategy:    {d.get('strategy', strategy)}")
                echo(f"  Start Cash:  ${d.get('starting_cash', cash):,.2f}")
                echo(f"  Final Value:  ${d.get('final_value', 0):,.2f}")
                echo(f"  Return:       {d.get('return_pct', 0):.2f}%")
                if output:
                    echo(f"  Output:      {output}")
            except Exception:
                echo(result.output[:300])
        else:
            error("Backtest failed")
            echo(f"  {result.error[:200]}")


@cmd_backtest.command("analyze")
@click.option("--data", "-d", required=True, help="CSV data file path")
@click.option("--strategy", "-st", default="sma_crossover",
              type=click.Choice(["sma_crossover", "rsi", "macd", "mean_reversion"]),
              help="Strategy name")
@click.option("--cash", "-c", type=float, default=10000.0, help="Starting cash")
@click.option("--output", "-o", help="Results JSON output path")
def cmd_backtest_analyze(data: str, strategy: str, cash: float, output: Optional[str]):
    """Run backtest with full analyzer output."""
    global JSON_MODE

    result = bb.run_backtest_with_analyzers(
        data_path=data,
        strategy=strategy,
        cash=cash,
        output_path=output,
    )

    if JSON_MODE:
        try:
            json_out(json.loads(result.output))
        except Exception:
            json_out({"success": result.success, "output": result.output, "error": result.error})
    else:
        if result.success:
            try:
                d = json.loads(result.output)
                success("Analysis complete")
                echo(f"  Strategy:       {d.get('strategy', strategy)}")
                echo(f"  Final Value:    ${d.get('final_value', 0):,.2f}")
                echo(f"  Sharpe Ratio:   {d.get('sharpe_ratio', 'N/A')}")
                echo(f"  Annual Return:  {d.get('annual_return', 'N/A')}%")
                echo(f"  Max Drawdown:   {d.get('max_drawdown_pct', 'N/A')}%")
            except Exception:
                echo(result.output[:300])
        else:
            error("Analysis failed")
            echo(f"  {result.error[:200]}")


# ==================================================================
# Entry point
# ==================================================================

def main():
    cli(obj={})


if __name__ == "__main__":
    main()
