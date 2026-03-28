"""
slurm_cli.py - Slurm/PBS HPC Job Scheduler CLI harness

Usage:
  slurm submit <script> [options]   Submit a job script
  slurm list [options]              List jobs in queue
  slurm cancel <jobid>             Cancel a job
  slurm nodes                       Show node info
  slurm info <jobid>                Show job details
  slurm version                     Show scheduler version
"""

from __future__ import annotations

import click
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from cli_anything.slurm.utils import slurm_backend as sb


@click.group()
@click.version_option(version=sb.SLURM_VERSION, prog_name="slurm")
def cli():
    """HPC job scheduler (Slurm/PBS) CLI."""
    pass


# ------------------------------------------------------------------
# Submit
# ------------------------------------------------------------------

@cli.command("submit")
@click.argument("script_path", type=click.Path(exists=True))
@click.option("--nodes", default=1, help="Number of nodes")
@click.option("--ntasks", default=1, help="Number of tasks")
@click.option("--cpus-per-task", default=1, help="CPUs per task")
@click.option("--mem", default="4G", help="Memory per node (e.g. 4G, 8000M)")
@click.option("--time", "time_limit", default="1:00:00", help="Time limit (HH:MM:SS)")
@click.option("--partition", help="Partition/queue name")
@click.option("--name", "job_name", help="Job name")
@click.option("--output", help="Output file path")
@click.option("--error", help="Error file path")
def submit_cmd(
    script_path: str,
    nodes: int,
    ntasks: int,
    cpus_per_task: int,
    mem: str,
    time_limit: str,
    partition: str | None,
    job_name: str | None,
    output: str | None,
    error: str | None,
):
    """Submit a job script to the scheduler."""
    scheduler = os.environ.get("SCHEDULER_TYPE", "auto").lower()
    if scheduler == "pbs" or os.environ.get("PBS_MOCK"):
        result = sb.pbs_submit(
            script_path, nodes, cpus_per_task, time_limit,
            queue=partition, job_name=job_name, output=output, error=error,
        )
    elif scheduler == "slurm" or os.environ.get("SLURM_MOCK"):
        result = sb.slurm_submit(
            script_path, nodes, ntasks, cpus_per_task, mem, time_limit,
            partition=partition, job_name=job_name, output=output, error=error,
        )
    else:
        result = sb.submit_job(
            script_path, nodes, ntasks, cpus_per_task, mem, time_limit,
            partition=partition, job_name=job_name,
        )

    if result.success:
        click.echo(result.output)
    else:
        click.echo("Error: " + result.error, err=True)
        sys.exit(1)


# ------------------------------------------------------------------
# List
# ------------------------------------------------------------------

@cli.command("list")
@click.option("--user", help="Filter by username")
@click.option("--state", help="Filter by state (Slurm only)")
@click.option("--json", "use_json", is_flag=True, help="Output as JSON")
def list_cmd(user: str | None, state: str | None, use_json: bool):
    """List jobs in the queue."""
    result = sb.list_jobs(user=user)

    if result.success:
        if use_json:
            lines = result.output.strip().split("\n")
            click.echo(json.dumps({"success": True, "jobs": lines}, indent=2))
        else:
            click.echo(result.output)
    else:
        click.echo("Error: " + result.error, err=True)
        sys.exit(1)


# ------------------------------------------------------------------
# Cancel
# ------------------------------------------------------------------

@cli.command("cancel")
@click.argument("job_id")
def cancel_cmd(job_id: str):
    """Cancel a job."""
    result = sb.cancel_job(job_id)
    if result.success:
        click.echo(result.output)
    else:
        click.echo("Error: " + result.error, err=True)
        sys.exit(1)


# ------------------------------------------------------------------
# Nodes
# ------------------------------------------------------------------

@cli.command("nodes")
def nodes_cmd():
    """Show cluster node information."""
    if os.environ.get("PBS_MOCK") or os.environ.get("SCHEDULER_TYPE") == "pbs":
        result = sb.pbs_node_info()
    else:
        result = sb.slurm_node_info()

    if result.success:
        click.echo(result.output)
    else:
        click.echo("Error: " + result.error, err=True)
        sys.exit(1)


# ------------------------------------------------------------------
# Info
# ------------------------------------------------------------------

@cli.command("info")
@click.argument("job_id")
@click.option("--json", "use_json", is_flag=True, help="Output as JSON")
def info_cmd(job_id: str, use_json: bool):
    """Show detailed job information."""
    info = sb.slurm_job_info(job_id)
    if use_json:
        click.echo(json.dumps(info, indent=2))
    else:
        if info.get("success"):
            for key, val in info.items():
                click.echo("  {}: {}".format(key, val))
        else:
            click.echo("Error: " + info.get("error", "Unknown error"), err=True)
            sys.exit(1)


# ------------------------------------------------------------------
# Version
# ------------------------------------------------------------------

@cli.command("version")
def version_cmd():
    """Show scheduler version."""
    info = sb.get_version()
    if info.get("success"):
        click.echo("{} version {}".format(info.get("scheduler", "scheduler").upper(), info.get("version")))
    else:
        click.echo("Scheduler: not detected", err=True)
        sys.exit(1)


import os


def main():
    cli()


if __name__ == "__main__":
    main()
