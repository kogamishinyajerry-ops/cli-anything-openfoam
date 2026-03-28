"""
quantconnect_cli.py - QuantConnect Lean CLI harness

Usage:
  quantconnect create <name>        Create a new project
  quantconnect backtest <project>   Run backtest
  quantconnect results <path>       Show backtest results
  quantconnect live <project>        Deploy to live trading
  quantconnect optimize <project>   Run parameter optimization
  quantconnect projects             List local projects
  quantconnect status               Show QC status
  quantconnect version              Show Lean version
"""

from __future__ import annotations

import click
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from cli_anything.quantconnect.utils import quantconnect_backend as qb


@click.group()
@click.version_option(version=qb.QUANTCONNECT_VERSION, prog_name="quantconnect")
def cli():
    """QuantConnect Lean algorithmic trading CLI."""
    pass


@cli.command("create")
@click.argument("name")
@click.option("--language", default="python", type=click.Choice(["python", "csharp"]))
@click.option("--directory", help="Parent directory")
def create_cmd(name: str, language: str, directory: str | None):
    """Create a new QuantConnect project."""
    result = qb.create_project(name, language=language, directory=directory)
    if result.success:
        click.echo(result.output)
    else:
        click.echo("Error: " + result.error, err=True)
        sys.exit(1)


@cli.command("backtest")
@click.argument("project_path", type=click.Path(exists=True))
@click.option("--output", help="Output directory for results")
@click.option("--detach", is_flag=True, help="Run in background")
@click.option("--estimate", is_flag=True, help="Estimate runtime only")
@click.option("--json", "use_json", is_flag=True, help="Output as JSON")
def backtest_cmd(project_path: str, output: str | None, detach: bool, estimate: bool, use_json: bool):
    """Run a backtest."""
    result = qb.run_backtest(
        project_path=project_path,
        output_dir=output,
        detach=detach,
        estimate=estimate,
    )
    if result.success:
        if use_json:
            click.echo(json.dumps({"success": True, "output": result.output}, indent=2))
        else:
            click.echo(result.output)
    else:
        click.echo("Error: " + result.error, err=True)
        sys.exit(1)


@cli.command("results")
@click.argument("results_path", type=click.Path(exists=True))
@click.option("--json", "use_json", is_flag=True, help="Output as JSON")
def results_cmd(results_path: str, use_json: bool):
    """Show backtest results."""
    info = qb.read_backtest_results(results_path)
    if info.get("success"):
        data = info.get("data", info.get("statistics", {}))
        if use_json:
            click.echo(json.dumps(data, indent=2))
        else:
            stats = data.get("statistics", data) if isinstance(data, dict) else {}
            if stats:
                click.echo("Backtest Statistics:")
                for k, v in stats.items():
                    click.echo("  {:<20s}: {}".format(k, v))
            else:
                click.echo(json.dumps(data, indent=2))
    else:
        click.echo("Error: " + info.get("error", "Unknown error"), err=True)
        sys.exit(1)


@cli.command("live")
@click.argument("project_path", type=click.Path(exists=True))
@click.option("--broker", default="paper", help="Broker (paper, interactive-brokers, alpaca)")
@click.option("--auto", is_flag=True, help="Automatic order execution")
def live_cmd(project_path: str, broker: str, auto: bool):
    """Deploy algorithm to live trading."""
    result = qb.deploy_live(project_path, broker=broker, auto=auto)
    if result.success:
        click.echo(result.output)
    else:
        click.echo("Error: " + result.error, err=True)
        sys.exit(1)


@cli.command("optimize")
@click.argument("project_path", type=click.Path(exists=True))
@click.option("--output", help="Output directory")
def optimize_cmd(project_path: str, output: str | None):
    """Run parameter optimization."""
    result = qb.optimize(project_path, output_dir=output)
    if result.success:
        click.echo(result.output)
    else:
        click.echo("Error: " + result.error, err=True)
        sys.exit(1)


@cli.command("projects")
@click.option("--directory", help="Directory to search")
def projects_cmd(directory: str | None):
    """List local QuantConnect projects."""
    info = qb.list_projects(directory=directory)
    if info.get("success"):
        projects = info.get("projects", [])
        if projects:
            click.echo("{:<20s} {:>10s} {}".format("NAME", "LANGUAGE", "PATH"))
            for p in projects:
                click.echo("{:<20s} {:>10s} {}".format(
                    p.get("name", "?"),
                    p.get("language", "?"),
                    p.get("path", "?"),
                ))
        else:
            click.echo("(no projects found)")
    else:
        click.echo("Error: " + info.get("error", "Unknown error"), err=True)
        sys.exit(1)


@cli.command("status")
def status_cmd():
    """Show QuantConnect status."""
    info = qb.get_status()
    if info.get("success"):
        for k, v in info.items():
            if k != "success":
                click.echo("  {}: {}".format(k, v))
    else:
        click.echo("Error: " + info.get("error", "Unknown error"), err=True)
        sys.exit(1)


@cli.command("version")
def version_cmd():
    """Show Lean version."""
    info = qb.get_version()
    if info.get("success"):
        click.echo("Lean version: {} (engine: {})".format(
            info.get("version", "?"), info.get("engine", "?")))
    else:
        click.echo("Lean CLI: not found", err=True)
        sys.exit(1)


def main():
    cli()


if __name__ == "__main__":
    main()
