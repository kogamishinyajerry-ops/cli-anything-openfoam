"""
elmer_cli.py - Elmer FEM Solver CLI harness

Usage:
  elmer run <sif> <mesh>       Run simulation
  elmer create <output>        Create static analysis SIF
  elmer mesh import <fmt> <in> <outdir>
  elmer mesh info <mesh>
  elmer version                Show version
"""

from __future__ import annotations

import click
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from cli_anything.elmer.utils import elmer_backend as eb


@click.group()
@click.version_option(version=eb.ELMER_VERSION, prog_name="elmer")
def cli():
    """Elmer FEM multiphysics simulation CLI."""
    pass


@cli.command("run")
@click.argument("sif_file", type=click.Path(exists=True))
@click.argument("mesh_dir", type=click.Path(exists=True, file_okay=False))
@click.option("--output", "output_dir", help="Output directory")
@click.option("--name", "case_name", help="Case name")
def run_cmd(sif_file: str, mesh_dir: str, output_dir: str | None, case_name: str | None):
    """Run ElmerSolver simulation."""
    result = eb.run_simulation(
        sif_file=sif_file,
        mesh_dir=mesh_dir,
        output_dir=output_dir,
        case_name=case_name,
    )
    if result.success:
        click.echo(result.output)
    else:
        click.echo("Error: " + result.error, err=True)
        sys.exit(1)


@cli.command("create")
@click.argument("output_path", type=click.Path())
@click.option("--title", default="Elmer Static Analysis")
@click.option("--body-force", default=0.0, type=float)
@click.option("--pressure", default=0.0, type=float)
@click.option("--young", default=210000.0, type=float, help="Young's modulus (Pa)")
@click.option("--poisson", default=0.3, type=float, help="Poisson's ratio")
def create_cmd(output_path: str, title: str, body_force: float, pressure: float, young: float, poisson: float):
    """Create a static analysis SIF file."""
    result = eb.create_static_sif(
        output_path=output_path,
        title=title,
        body_force=body_force,
        pressure=pressure,
        youngs_modulus=young,
        poissons_ratio=poisson,
    )
    if result.success:
        click.echo(result.output)
    else:
        click.echo("Error: " + result.error, err=True)
        sys.exit(1)


@cli.group("mesh")
def mesh_group():
    """Mesh operations."""
    pass


@mesh_group.command("import")
@click.argument("mesh_format")
@click.argument("input_file", type=click.Path(exists=True))
@click.argument("output_dir", type=click.Path(file_okay=False))
def mesh_import_cmd(mesh_format: str, input_file: str, output_dir: str):
    """Import mesh to Elmer format."""
    result = eb.import_mesh(mesh_format, input_file, output_dir)
    if result.success:
        click.echo(result.output)
    else:
        click.echo("Error: " + result.error, err=True)
        sys.exit(1)


@mesh_group.command("info")
@click.argument("mesh_dir", type=click.Path(exists=True, file_okay=False))
@click.option("--json", "use_json", is_flag=True)
def mesh_info_cmd(mesh_dir: str, use_json: bool):
    """Show mesh information."""
    info = eb.mesh_info(mesh_dir)
    if use_json:
        click.echo(json.dumps(info, indent=2))
    elif info.get("success"):
        for k, v in info.items():
            if k != "success":
                click.echo("  {}: {}".format(k, v))
    else:
        click.echo("Error: " + info.get("error", "Unknown error"), err=True)
        sys.exit(1)


@cli.command("version")
def version_cmd():
    """Show Elmer version."""
    info = eb.get_version()
    if info.get("success"):
        click.echo("Elmer version: {}".format(info.get("version")))
    else:
        click.echo("Elmer: not found", err=True)
        sys.exit(1)


def main():
    cli()


if __name__ == "__main__":
    main()
