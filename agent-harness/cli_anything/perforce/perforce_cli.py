"""
perforce_cli.py - Perforce Helix Core CLI harness

Usage:
  perforce info                    Show server/client info
  perforce sync [path]             Sync files from depot
  perforce files <depot_path>     List files in depot
  perforce changes [path]          List recent changes
  perforce describe <change>       Show change details
  perforce status                  Show workspace status
  perforce submit <desc>           Submit changes
  perforce client <name> <root>   Create client workspace
  perforce version                 Show version
"""

from __future__ import annotations

import click
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from cli_anything.perforce.utils import perforce_backend as pb


@click.group()
@click.version_option(version=pb.PERFORCE_VERSION, prog_name="perforce")
def cli():
    """Perforce Helix Core version control CLI."""
    pass


@cli.command("info")
@click.option("--json", "use_json", is_flag=True)
def info_cmd(use_json: bool):
    """Show Perforce server/client info."""
    info = pb.get_info()
    if info.get("success"):
        if use_json:
            click.echo(json.dumps(info, indent=2))
        else:
            for k, v in info.items():
                if k != "success":
                    click.echo("  {}: {}".format(k, v))
    else:
        click.echo("Error: " + info.get("error", "Unknown error"), err=True)
        sys.exit(1)


@cli.command("sync")
@click.argument("branch", default="//depot/main/...")
def sync_cmd(branch: str):
    """Sync files from depot."""
    result = pb.sync(branch=branch)
    if result.success:
        click.echo(result.output)
    else:
        click.echo("Error: " + result.error, err=True)
        sys.exit(1)


@cli.command("files")
@click.argument("depot_path", default="//depot/...")
@click.option("--max", "max_results", default=50, help="Max files to list")
@click.option("--json", "use_json", is_flag=True)
def files_cmd(depot_path: str, max_results: int, use_json: bool):
    """List files in depot."""
    info = pb.list_files(depot_path, max_results=max_results)
    if info.get("success"):
        files = info.get("files", [])
        if use_json:
            click.echo(json.dumps(files, indent=2))
        else:
            if files:
                click.echo("{:<50s} {:>6s} {:>10s}".format("DEPOT PATH", "REV", "TYPE"))
                for f in files:
                    click.echo("{:<50s} {:>6s} {:>10s}".format(
                        f.get("depotFile", "?")[:50],
                        f.get("rev", "?"),
                        f.get("headType", "?")[:10],
                    ))
            else:
                click.echo("(no files found)")
    else:
        click.echo("Error: " + info.get("error", "Unknown error"), err=True)
        sys.exit(1)


@cli.command("changes")
@click.argument("depot_path", default="//depot/...")
@click.option("--max", "max_changes", default=10, help="Max changes to list")
@click.option("--json", "use_json", is_flag=True)
def changes_cmd(depot_path: str, max_changes: int, use_json: bool):
    """List recent changes."""
    info = pb.list_changes(depot_path, max_changes=max_changes)
    if info.get("success"):
        changes = info.get("changes", [])
        if use_json:
            click.echo(json.dumps(changes, indent=2))
        else:
            if changes:
                click.echo("{:<8s} {:<12s} {:<15s} {}".format("CHANGE", "USER", "CLIENT", "DESCRIPTION"))
                for c in changes:
                    click.echo("{:<8s} {:<12s} {:<15s} {}".format(
                        c.get("change", "?"),
                        c.get("user", "?")[:12],
                        c.get("client", "?")[:15],
                        c.get("desc", "?")[:50],
                    ))
            else:
                click.echo("(no changes found)")
    else:
        click.echo("Error: " + info.get("error", "Unknown error"), err=True)
        sys.exit(1)


@cli.command("describe")
@click.argument("change_num")
@click.option("--json", "use_json", is_flag=True)
def describe_cmd(change_num: str, use_json: bool):
    """Show change details."""
    info = pb.describe_change(change_num)
    if info.get("success"):
        if use_json:
            click.echo(json.dumps(info, indent=2))
        else:
            click.echo("Change #{}".format(info.get("change")))
            click.echo("  Description: {}".format(info.get("desc", "")))
            click.echo("  Files:")
            for f in info.get("files", []):
                click.echo("    {}".format(f))
    else:
        click.echo("Error: " + info.get("error", "Unknown error"), err=True)
        sys.exit(1)


@cli.command("status")
def status_cmd():
    """Show workspace status."""
    info = pb.status()
    if info.get("success"):
        if info.get("opened_files"):
            click.echo("Opened files for edit:")
            for f in info["opened_files"]:
                click.echo("  (edit) {}".format(f))
        if info.get("added_files"):
            click.echo("Opened files for add:")
            for f in info["added_files"]:
                click.echo("  (add)  {}".format(f))
        if info.get("deleted_files"):
            click.echo("Opened files for delete:")
            for f in info["deleted_files"]:
                click.echo("  (del)  {}".format(f))
        if info.get("untracked"):
            click.echo("Untracked files:")
            for f in info["untracked"]:
                click.echo("  ?      {}".format(f))
        if not any([info.get("opened_files"), info.get("added_files"),
                    info.get("deleted_files"), info.get("untracked")]):
            click.echo("(no pending changes)")
    else:
        click.echo("Error: " + info.get("error", "Unknown error"), err=True)
        sys.exit(1)


@cli.command("submit")
@click.argument("description")
@click.option("--files", "file_paths", multiple=True, help="Specific files to submit")
def submit_cmd(description: str, file_paths: list):
    """Submit changes to depot."""
    result = pb.submit(description=description, file_paths=list(file_paths) if file_paths else None)
    if isinstance(result, dict):
        if result.get("success"):
            click.echo("Submitted as change #{}".format(result.get("change")))
        else:
            click.echo("Error: " + result.get("error", "Submit failed"), err=True)
            sys.exit(1)
    else:
        # It's a CommandResult
        if result.success:
            click.echo(result.output)
        else:
            click.echo("Error: " + result.error, err=True)
            sys.exit(1)


@cli.command("client")
@click.argument("client_name")
@click.argument("root_dir", type=click.Path(file_okay=False))
@click.option("--host", help="Server host")
def client_cmd(client_name: str, root_dir: str, host: str | None):
    """Create a Perforce client workspace."""
    result = pb.create_client(client_name=client_name, root_dir=root_dir, host=host)
    if result.success:
        click.echo(result.output)
    else:
        click.echo("Error: " + result.error, err=True)
        sys.exit(1)


@cli.command("version")
def version_cmd():
    """Show Perforce version."""
    info = pb.get_version()
    if info.get("success"):
        click.echo("Perforce version: {} (server: {})".format(
            info.get("version", "?"), info.get("server", "?")))
    else:
        click.echo("Perforce: not found", err=True)
        sys.exit(1)


def main():
    cli()


if __name__ == "__main__":
    main()
