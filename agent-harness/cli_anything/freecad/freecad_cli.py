"""FreeCAD CLI harness — parametric CAD for CFD workflows."""
from __future__ import annotations
import json
import re
import subprocess
import sys
from pathlib import Path

import click

from .utils import freecad_backend as fb

JSON_MODE = False

def echo(msg): click.echo(msg, err=True)
def success(msg): click.echo(click.style(f"✓ {msg}", fg="green"), err=True)
def error(msg): click.echo(click.style(f"✗ {msg}", fg="red"), err=True)
def json_out(data): click.echo(json.dumps(data, indent=2))


@click.group()
@click.option("--json", "use_json", is_flag=True)
@click.option("--container", default="cfd-openfoam")
@click.pass_context
def cli(ctx, use_json, container):
    """FreeCAD CLI harness — parametric CAD for CFD."""
    global JSON_MODE
    JSON_MODE = use_json
    ctx.ensure_object(dict)
    ctx.obj["container"] = container


@cli.group()
def create():
    """Create parametric geometry."""
    pass


def _copy_back(container, container_path, host_path):
    subprocess.run(["docker", "cp", f"{container}:{container_path}", host_path],
                   check=True, timeout=30)


@create.command("box")
@click.option("--length", type=float, required=True)
@click.option("--width", type=float, required=True)
@click.option("--height", type=float, required=True)
@click.option("-o", "--output", required=True)
@click.pass_context
def create_box(ctx, length, width, height, output):
    """Create a box and export as STL."""
    container = ctx.obj["container"]
    container_out = f"/tmp/{Path(output).name}"
    r = fb.create_box(length, width, height, container_out, container)
    if "EXPORT_OK" not in r.output:
        error(f"Failed: {r.error[:200]}")
        sys.exit(1)
    _copy_back(container, container_out, output)
    vol = re.search(r'VOLUME=([\d.eE+-]+)', r.output)
    success(f"Box {length}×{width}×{height} → {output}" +
            (f" (V={float(vol.group(1)):.1f})" if vol else ""))
    if JSON_MODE:
        json_out({"status": "ok", "file": output,
                  "volume": float(vol.group(1)) if vol else None})


@create.command("cylinder")
@click.option("--radius", type=float, required=True)
@click.option("--height", type=float, required=True)
@click.option("-o", "--output", required=True)
@click.pass_context
def create_cylinder(ctx, radius, height, output):
    """Create a cylinder and export as STL."""
    container = ctx.obj["container"]
    container_out = f"/tmp/{Path(output).name}"
    r = fb.create_cylinder(radius, height, container_out, container)
    if "EXPORT_OK" not in r.output:
        error(f"Failed: {r.error[:200]}")
        sys.exit(1)
    _copy_back(container, container_out, output)
    success(f"Cylinder r={radius} h={height} → {output}")
    if JSON_MODE:
        json_out({"status": "ok", "file": output})


@create.command("pipe")
@click.option("--outer-radius", type=float, required=True)
@click.option("--inner-radius", type=float, required=True)
@click.option("--length", type=float, required=True)
@click.option("-o", "--output", required=True)
@click.pass_context
def create_pipe(ctx, outer_radius, inner_radius, length, output):
    """Create a pipe (hollow cylinder) and export as STL."""
    container = ctx.obj["container"]
    container_out = f"/tmp/{Path(output).name}"
    r = fb.create_pipe(outer_radius, inner_radius, length, container_out, container)
    if "EXPORT_OK" not in r.output:
        error(f"Failed: {r.error[:200]}")
        sys.exit(1)
    _copy_back(container, container_out, output)
    success(f"Pipe R={outer_radius} r={inner_radius} L={length} → {output}")
    if JSON_MODE:
        json_out({"status": "ok", "file": output})


@cli.command("info")
@click.option("--input", "input_file", required=True)
@click.pass_context
def info_cmd(ctx, input_file):
    """Show geometry info (points, facets, volume, bounding box)."""
    container = ctx.obj["container"]
    container_in = f"/tmp/{Path(input_file).name}"
    subprocess.run(["docker", "cp", input_file, f"{container}:{container_in}"],
                   check=True, timeout=10)
    r = fb.get_info(container_in, container)
    if "INFO_OK" not in r.output:
        error(f"Failed: {r.error[:200]}")
        sys.exit(1)
    info = {}
    for key in ["POINTS", "FACETS", "VOLUME", "AREA"]:
        m = re.search(rf'{key}=([\d.eE+-]+)', r.output)
        if m: info[key.lower()] = float(m.group(1))
    m = re.search(r'BBOX=\[([\d.eE+,\s-]+)\]', r.output)
    if m: info["bbox"] = [float(x) for x in m.group(1).split(",")]
    for k, v in info.items():
        echo(f"  {k}: {v}")
    if JSON_MODE:
        json_out(info)


@cli.command("script")
@click.option("--file", "script_file", required=True)
@click.pass_context
def script_cmd(ctx, script_file):
    """Run an arbitrary FreeCAD Python script."""
    container = ctx.obj["container"]
    container_script = f"/tmp/{Path(script_file).name}"
    subprocess.run(["docker", "cp", script_file, f"{container}:{container_script}"],
                   check=True, timeout=10)
    r = fb.run_script(container_script, container)
    echo(r.output)
    if r.error: echo(r.error)
    if JSON_MODE:
        json_out({"status": "ok" if r.success else "failed", "output": r.output})


def main():
    cli(obj={})
