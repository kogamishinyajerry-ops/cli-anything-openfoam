"""
vectorbt_cli.py - VectorBT CLI harness

Usage:
  vectorbt run <data.csv> [options]    Run backtest
  vectorbt report <results.json> [opts] Generate HTML report
  vectorbt strategies                  List available strategies
  vectorbt version                     Show VectorBT version
"""

from __future__ import annotations

import click
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from cli_anything.vectorbt.utils import vectorbt_backend as vb


@click.group()
@click.version_option(version=vb.VECTORBT_VERSION, prog_name="vectorbt")
def cli():
    """VectorBT vectorized backtesting CLI."""
    pass


@cli.command("run")
@click.argument("data_path", type=click.Path(exists=True))
@click.option("--strategy", default="sma_cross", help="Strategy name")
@click.option("--fast-period", default=10, help="Fast period for SMA strategies")
@click.option("--slow-period", default=30, help="Slow period for SMA strategies")
@click.option("--init-cash", default=100000.0, type=float, help="Initial cash")
@click.option("--commission", default=0.001, type=float, help="Commission rate")
@click.option("--output", "output_path", help="Output JSON path for results")
@click.option("--json", "use_json", is_flag=True, help="Output as JSON")
def run_cmd(
    data_path: str,
    strategy: str,
    fast_period: int,
    slow_period: int,
    init_cash: float,
    commission: float,
    output_path: str | None,
    use_json: bool,
):
    """Run a VectorBT backtest on CSV data."""
    result = vb.run_backtest(
        data_path=data_path,
        strategy=strategy,
        fast_period=fast_period,
        slow_period=slow_period,
        init_cash=init_cash,
        commission=commission,
        output_path=output_path,
    )

    if result.success:
        if use_json:
            click.echo(result.output)
        else:
            data = json.loads(result.output)
            click.echo("[OK] Backtest completed")
            click.echo("  Strategy: {}".format(data.get("strategy")))
            click.echo("  Return: {:.2f}%".format(data.get("return_pct", 0)))
            click.echo("  Final value: ${:.2f}".format(data.get("final_value", 0)))
            click.echo("  Total trades: {}".format(data.get("total_trades", 0)))
            click.echo("  Win rate: {:.1f}%".format(data.get("win_rate", 0) * 100))
            if output_path:
                click.echo("  Results saved to: {}".format(output_path))
    else:
        click.echo("Error: " + result.error, err=True)
        sys.exit(1)


@cli.command("report")
@click.argument("results_path", type=click.Path(exists=True))
@click.option("--output", "output_path", required=True, help="Output HTML path")
@click.option("--no-plot", is_flag=True, help="Exclude plots")
def report_cmd(results_path: str, output_path: str, no_plot: bool):
    """Generate HTML report from backtest results."""
    result = vb.generate_report(
        results_path=results_path,
        output_path=output_path,
        plot=not no_plot,
    )
    if result.success:
        click.echo(result.output)
    else:
        click.echo("Error: " + result.error, err=True)
        sys.exit(1)


@cli.command("strategies")
def strategies_cmd():
    """List available strategy templates."""
    info = vb.list_strategies()
    click.echo("Available strategies:")
    for s in info.get("strategies", []):
        desc = info.get("descriptions", {}).get(s, "")
        click.echo("  {:12s} - {}".format(s, desc))


@cli.command("version")
def version_cmd():
    """Show VectorBT version."""
    info = vb.get_version()
    if info.get("success"):
        click.echo("VectorBT version {} (installed: {})".format(
            info.get("version"), info.get("installed", True)))
    else:
        click.echo("VectorBT: not found - " + info.get("error", "unknown error"), err=True)
        sys.exit(1)


def main():
    cli()


if __name__ == "__main__":
    main()
