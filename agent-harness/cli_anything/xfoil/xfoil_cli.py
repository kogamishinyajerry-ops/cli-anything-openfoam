"""
xfoil_cli.py - Click CLI entry point for cli-anything-xfoil

Command groups:
  analyze     - Single-point analysis (alpha, CL, CD, CM)
  polar       - Compute polar file (ASEQ sweep)
  check       - Quick airfoil geometry check

All commands support --json for machine-readable output.
Bare 'xfoil' enters REPL mode.

Follows HARNESS.md principles:
  - Real XFoil commands called via xfoil_backend
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

import click

from .utils import xfoil_backend as xb

__all__ = ["main"]

JSON_MODE = False


# -------------------------------------------------------------------
# Utility helpers
# -------------------------------------------------------------------

def echo(msg: str, **kwargs) -> None:
    click.echo(msg, err=True, **kwargs)


def success(msg: str) -> None:
    click.echo(f"[OK] {msg}", err=True)


def error(msg: str) -> None:
    click.echo(f"[ERROR] {msg}", err=True, color="red")


def warn(msg: str) -> None:
    click.echo(f"[WARN] {msg}", err=True, color="yellow")


def json_out(data: dict) -> None:
    click.echo(json.dumps(data, indent=2))


# -------------------------------------------------------------------
# Main group
# -------------------------------------------------------------------

@click.group(invoke_without_command=True)
@click.option("--json", "json_output", is_flag=True, help="JSON output mode")
@click.option("--container", "-c", default="cfd-openfoam",
              help="Docker container name (default: cfd-openfoam)")
@click.pass_context
def cli(ctx, json_output: bool, container: str):
    """XFoil aerodynamic analysis CLI — airfoil analysis and polar computation.

    XFoil is an interactive panel method for analyzing isolated airfoils.
    Supports NACA 4/5-digit series, Eppler, and Selig-format coordinates.

    Examples:
      xfoil analyze --airfoil 4412 --alpha 5 --Re 3e6
      xfoil polar --airfoil 4412 --Re 3e6 --alpha -5 15 0.5
    """
    global JSON_MODE
    JSON_MODE = json_output
    ctx.ensure_object(dict)
    ctx.obj["json"] = json_output
    ctx.obj["container"] = container

    if ctx.invoked_subcommand is None:
        echo(f"XFoil harness (CLI wrapper)")
        echo(f"Container: {container}")
        try:
            xb.find_xfoil()
            echo("XFoil: found")
        except RuntimeError as e:
            echo(f"XFoil: not found ({xb.XFOIL_VERSION})")
        echo("Use --help with a subcommand for details")


# ==================================================================
# analyze command
# ==================================================================

@cli.command("analyze")
@click.option("--airfoil", "-a", required=True,
              help="Airfoil name (e.g., 4412, NACA0012) or path to .dat file")
@click.option("--alpha", type=float, required=True,
              help="Angle of attack (degrees)")
@click.option("--Re", "reynolds", type=float, required=True,
              help="Reynolds number (e.g., 3e6)")
@click.option("--mach", type=float, default=0.0,
              help="Mach number (default: 0.0)")
@click.option("--file", "is_file", is_flag=True,
              help="Treat --airfoil as a path to coordinate file")
@click.pass_context
def cmd_analyze(ctx, airfoil: str, alpha: float, reynolds: float,
                 mach: float, is_file: bool):
    """Analyze a single operating point (CL, CD, CM at given alpha).

    Example:
      xfoil analyze --airfoil 4412 --alpha 5 --Re 3e6
      xfoil analyze --airfoil ./naca4412.dat --alpha 3 --Re 1e6 --file
    """
    global JSON_MODE
    container = ctx.obj.get("container")

    if is_file:
        result = xb.load_airfoil_from_file(Path(airfoil), container=container)
    else:
        result = xb.analyze(
            airfoil=airfoil,
            alpha=alpha,
            reynolds=reynolds,
            mach=mach,
            container=container,
        )

    if JSON_MODE:
        json_out(result)
    else:
        if result.get("success"):
            cl = result.get("CL")
            cd = result.get("CD")
            cm = result.get("CM")
            ld = result.get("L_D")
            echo(f"Airfoil: {airfoil}")
            echo(f"Alpha = {alpha}° | Re = {reynolds:.0e} | Mach = {mach}")
            if cl is not None:
                echo(f"  CL   = {cl:.6f}")
            if cd is not None:
                echo(f"  CD   = {cd:.6f}")
            if cm is not None:
                echo(f"  CM   = {cm:.6f}")
            if ld is not None:
                echo(f"  L/D  = {ld:.4f}")
            if result.get("CP_min"):
                echo(f"  CPmin = {result['CP_min']:.4f}")
        else:
            error("Analysis failed")
            echo(f"  {result.get('raw_output', result.get('error', ''))[:200]}")


# ==================================================================
# polar command
# ==================================================================

@cli.command("polar")
@click.option("--airfoil", "-a", required=True,
              help="Airfoil name or path to .dat file")
@click.option("--Re", "reynolds", type=float, required=True,
              help="Reynolds number")
@click.option("--alpha-start", type=float, default=-5.0,
              help="Start angle of attack (degrees, default: -5)")
@click.option("--alpha-end", type=float, default=15.0,
              help="End angle of attack (degrees, default: 15)")
@click.option("--alpha-step", type=float, default=0.5,
              help="Angle increment (degrees, default: 0.5)")
@click.option("--mach", type=float, default=0.0,
              help="Mach number (default: 0.0)")
@click.option("--file", "is_file", is_flag=True,
              help="Treat --airfoil as a path to coordinate file")
@click.option("--output", "-o", type=click.Path(),
              help="Output polar file path")
@click.pass_context
def cmd_polar(ctx, airfoil: str, reynolds: float,
               alpha_start: float, alpha_end: float, alpha_step: float,
               mach: float, is_file: bool, output: Optional[str]):
    """Compute a polar (CL, CD vs alpha sweep).

    Example:
      xfoil polar --airfoil 4412 --Re 3e6 --alpha-start -5 --alpha-end 20
      xfoil polar --airfoil 4412 --Re 6e6 --alpha-step 1.0 --output polar.csv
    """
    global JSON_MODE
    container = ctx.obj.get("container")

    if is_file:
        result = xb.compute_polar_file(
            airfoil_file=Path(airfoil),
            reynolds=reynolds,
            mach=mach,
            alpha_start=alpha_start,
            alpha_end=alpha_end,
            alpha_step=alpha_step,
            container=container,
        )
    else:
        result = xb.compute_polar(
            airfoil=airfoil,
            reynolds=reynolds,
            mach=mach,
            alpha_start=alpha_start,
            alpha_end=alpha_end,
            alpha_step=alpha_step,
            container=container,
        )

    parsed = xb.parse_polar_output(result.output)

    if JSON_MODE:
        json_out({
            "status": "success" if result.success else "error",
            "airfoil": airfoil,
            "reynolds": reynolds,
            "mach": mach,
            "alpha_range": [alpha_start, alpha_end, alpha_step],
            "n_points": parsed.get("n_points", 0),
            "data": parsed.get("data", []),
            "error": result.error[-300:] if result.error else "",
        })
    else:
        if parsed.get("n_points", 0) > 0:
            success(f"Polar computed: {parsed['n_points']} points")
            echo(f"Airfoil: {airfoil} | Re = {reynolds:.0e} | Mach = {mach}")
            echo(f"Alpha: {alpha_start}° to {alpha_end}° by {alpha_step}°")
            echo(f"\n{'Alpha':>8} {'CL':>10} {'CD':>12} {'L/D':>10} {'CDp':>12} {'CM':>10}")
            echo("-" * 65)
            for row in parsed["data"]:
                ld = row["CL"] / row["CD"] if row["CD"] != 0 else 0
                echo(f"{row['alpha']:>8.2f} {row['CL']:>10.5f} {row['CD']:>12.6f} "
                     f"{ld:>10.4f} {row.get('CDp', 0):>12.6f} {row.get('CM', 0):>10.5f}")
        else:
            error("Polar computation failed or produced no data")
            echo(f"  {result.output[-300:]}")


# ==================================================================
# sweep command (alias for polar)
# ==================================================================

@cli.command("sweep")
@click.option("--airfoil", "-a", required=True,
              help="Airfoil name")
@click.option("--Re", "reynolds", type=float, required=True,
              help="Reynolds number")
@click.option("--alpha-start", type=float, default=-5.0)
@click.option("--alpha-end", type=float, default=15.0)
@click.option("--alpha-step", type=float, default=0.5)
@click.option("--mach", type=float, default=0.0)
@click.pass_context
def cmd_sweep(ctx, airfoil: str, reynolds: float,
               alpha_start: float, alpha_end: float, alpha_step: float, mach: float):
    """Sweep alpha and return polar data (alias for polar command)."""
    global JSON_MODE
    container = ctx.obj.get("container")

    result = xb.alpha_sweep(
        airfoil=airfoil,
        reynolds=reynolds,
        alpha_start=alpha_start,
        alpha_end=alpha_end,
        alpha_step=alpha_step,
        mach=mach,
        container=container,
    )

    if JSON_MODE:
        json_out(result)
    else:
        if result.get("n_points", 0) > 0:
            success(f"Sweep complete: {result['n_points']} points")
            for row in result["data"]:
                echo(f"  alpha={row['alpha']:.2f} CL={row['CL']:.5f} CD={row['CD']:.6f}")
        else:
            error("Sweep produced no data")


# ==================================================================
# check command
# ==================================================================

@cli.command("check")
@click.option("--airfoil", "-a", required=True,
              help="Airfoil name (e.g., 4412, NACA0012)")
@click.pass_context
def cmd_check(ctx, airfoil: str):
    """Show airfoil geometric parameters (thickness, camber, LE radius).

    Example:
      xfoil check --airfoil 4412
    """
    global JSON_MODE
    container = ctx.obj.get("container")

    info = xb.check_airfoil(airfoil, container=container)

    if JSON_MODE:
        json_out(info)
    else:
        echo(f"Airfoil: {airfoil}")
        if info.get("LE_radius"):
            echo(f"  LE radius:     {info['LE_radius']:.6f}")
        if info.get("thickness_pct"):
            echo(f"  Thickness:     {info['thickness_pct']:.2f}% at x={info.get('thickness_x', '?'):.3f}")
        if info.get("camber_pct"):
            echo(f"  Camber:       {info['camber_pct']:.2f}% at x={info.get('camber_x', '?'):.3f}")
        if not info.get("LE_radius") and not info.get("thickness_pct"):
            echo("  (Could not parse geometric parameters from XFoil output)")


# ==================================================================
# presets command
# ==================================================================

@cli.command("presets")
@click.pass_context
def cmd_presets(ctx):
    """List available preset airfoil configurations.

    Example:
      xfoil presets
    """
    global JSON_MODE

    if JSON_MODE:
        json_out({"presets": xb.AIRFOIL_PRESETS})
    else:
        echo("Available airfoil presets:")
        for name, info in xb.AIRFOIL_PRESETS.items():
            echo(f"  {name}: {info['description']}")
            echo(f"    Type: {info['type']} {info['series']}")


# ==================================================================
# Entry point
# ==================================================================

def main():
    cli(obj={})


if __name__ == "__main__":
    main()
