"""
calculix_cli.py - Click CLI for cli-anything-calculix

Commands:
  solve        - Run solver (static, modal, thermal)
  create      - Create input file from templates
  results     - Parse and export results
  info        - Version and template info

All commands support --json for machine-readable output.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import click

from .utils import calculix_backend as cb

__all__ = ["main"]

JSON_MODE = False


def echo(msg: str, **kwargs) -> None:
    click.echo(msg, err=True, **kwargs)


def success(msg: str) -> None:
    click.echo("[OK] {}".format(msg), err=True)


def error(msg: str) -> None:
    click.echo("[ERROR] {}".format(msg), err=True, color="red")


def json_out(data: dict) -> None:
    click.echo(json.dumps(data, indent=2))


# -------------------------------------------------------------------
# Main
# -------------------------------------------------------------------

@click.group(invoke_without_command=True)
@click.option("--json", "json_output", is_flag=True, help="JSON output mode")
@click.pass_context
def cli(ctx, json_output: bool):
    """Calculix FEA — structural and thermal analysis from the CLI.

    Calculix is an open-source finite element analysis software.
    Supports linear static, modal, buckling, and thermal analysis.

    Examples:
      calculix create static --output beam.inp
      calculix solve --input beam.inp
      calculix solve modal --input beam.inp --modes 20
      calculix results parse --dat beam.dat
      calculix results export-vtk --dat beam.dat --output beam.vtk
    """
    global JSON_MODE
    JSON_MODE = json_output
    ctx.ensure_object(dict)
    ctx.obj["json"] = json_output

    if ctx.invoked_subcommand is None:
        echo("Calculix FEA harness (CLI wrapper)")
        v = cb.get_version()
        if v.get("success"):
            echo("Version: {}".format(v["version"]))
        else:
            echo("Calculix: not found")


# ==================================================================
# info command
# ==================================================================

@cli.group("info")
def cmd_info():
    """Version and template information."""
    pass


@cmd_info.command("version")
def cmd_version():
    """Show Calculix version."""
    global JSON_MODE
    v = cb.get_version()
    if JSON_MODE:
        json_out(v)
    else:
        if v.get("success"):
            echo("Calculix {}".format(v["version"]))
            echo("  Solver: {}".format(v.get("solver", "ccx")))
            echo("  Preprocessor: {}".format(v.get("preprocessor", "cgx")))
        else:
            error("Failed to get version")
            echo("  {}".format(v.get("error", "")))


@cmd_info.command("templates")
def cmd_templates():
    """Show available analysis templates."""
    global JSON_MODE
    info = cb.get_template_info()
    if JSON_MODE:
        json_out(info)
    else:
        if info.get("success"):
            echo("Available Templates:")
            for t in info.get("templates", []):
                echo("  {}: {}".format(t["type"], t["name"]))
                echo("    {}".format(t["description"]))


# ==================================================================
# create command
# ==================================================================

@cli.command("create")
@click.option("--output", "-o", required=True, help="Output .inp file path")
@click.option("--title", "-t", default="Calculix Analysis", help="Analysis title")
@click.option("--type", "-ty", default="static",
              type=click.Choice(["static"]),
              help="Analysis type")
def cmd_create(output: str, title: str, type: str):
    """Create a new analysis input file."""
    global JSON_MODE

    # Create basic static analysis input
    # Default simple beam with 2 nodes
    nodes = [
        (1, 0.0, 0.0, 0.0),
        (2, 100.0, 0.0, 0.0),
    ]
    elements = [
        (1, "B31", 1, 2),  # Beam element
    ]
    materials = {
        "name": "Steel",
        "E": 210000.0,
        "nu": 0.3,
        "rho": 7.85e-9,
    }

    result = cb.create_static_input(
        output_path=output,
        title=title,
        nodes=nodes,
        elements=elements,
        materials=materials,
    )

    if JSON_MODE:
        json_out({"success": result.success, "output": result.output})
    else:
        if result.success:
            success("Created: {}".format(output))
        else:
            error("Failed to create input file")
            echo("  {}".format(result.error[:200]))


# ==================================================================
# solve command
# ==================================================================

@cli.group("solve")
def cmd_solve():
    """Run analysis."""
    pass


@cmd_solve.command("static")
@click.option("--input", "-i", required=True, help="Input .inp file")
@click.option("--timeout", "-t", type=int, default=300, help="Timeout seconds")
@click.option("--output-name", "-o", help="Custom output base name")
def cmd_solve_static(input: str, timeout: int, output_name: Optional[str]):
    """Run static analysis."""
    global JSON_MODE

    result = cb.solve(input, output_name=output_name, mode="static", timeout=timeout)

    if JSON_MODE:
        json_out({"success": result.success, "output": result.output, "error": result.error})
    else:
        if result.success:
            success("Static analysis complete")
            echo(result.output[:500])
        else:
            error("Static analysis failed")
            echo("  {}".format(result.error[:200]))


@cmd_solve.command("modal")
@click.option("--input", "-i", required=True, help="Input .inp file")
@click.option("--modes", "-m", type=int, default=10, help="Number of modes")
@click.option("--timeout", "-t", type=int, default=300, help="Timeout seconds")
def cmd_solve_modal(input: str, modes: int, timeout: int):
    """Run modal analysis."""
    global JSON_MODE

    result = cb.solve_modal(input, modes=modes, timeout=timeout)

    if JSON_MODE:
        json_out({"success": result.success, "output": result.output, "error": result.error})
    else:
        if result.success:
            success("Modal analysis complete")
            echo(result.output[:500])
        else:
            error("Modal analysis failed")
            echo("  {}".format(result.error[:200]))


@cmd_solve.command("thermal")
@click.option("--input", "-i", required=True, help="Input .inp file")
@click.option("--timeout", "-t", type=int, default=300, help="Timeout seconds")
def cmd_solve_thermal(input: str, timeout: int):
    """Run thermal analysis."""
    global JSON_MODE

    result = cb.solve(input, mode="thermal", timeout=timeout)

    if JSON_MODE:
        json_out({"success": result.success, "output": result.output, "error": result.error})
    else:
        if result.success:
            success("Thermal analysis complete")
            echo(result.output[:500])
        else:
            error("Thermal analysis failed")
            echo("  {}".format(result.error[:200]))


# ==================================================================
# results command
# ==================================================================

@cli.group("results")
def cmd_results():
    """Parse and export results."""
    pass


@cmd_results.command("parse")
@click.option("--dat", "-d", required=True, help="Path to .dat results file")
def cmd_parse(dat: str):
    """Parse .dat results file."""
    global JSON_MODE

    info = cb.read_dat_file(dat)

    if JSON_MODE:
        json_out(info)
    else:
        if info.get("success"):
            echo("Results: {}".format(dat))
            echo("  Displacements: {} nodes".format(info.get("node_count", 0)))
            echo("  Stresses: {} elements".format(info.get("element_count", 0)))
            if info.get("displacements"):
                echo("\nSample displacements (first 3):")
                for d in info.get("displacements", [])[:3]:
                    echo("  Node {}: U=({:.4f}, {:.4f}, {:.4f})".format(
                        d["node"], d["u1"], d["u2"], d["u3"]))
        else:
            error("Failed to parse results")
            echo("  {}".format(info.get("error", "")))


@cmd_results.command("export-vtk")
@click.option("--dat", "-d", required=True, help="Path to .dat results file")
@click.option("--output", "-o", required=True, help="Output .vtk file path")
def cmd_export_vtk(dat: str, output: str):
    """Export results to VTK format for ParaView."""
    global JSON_MODE

    result = cb.export_to_vtk(dat, output)

    if JSON_MODE:
        json_out({"success": result.success, "output": result.output, "error": result.error})
    else:
        if result.success:
            success("Exported to VTK: {}".format(output))
        else:
            error("Export failed")
            echo("  {}".format(result.error[:200]))


# ==================================================================
# Entry point
# ==================================================================

def main():
    cli(obj={})


if __name__ == "__main__":
    main()
