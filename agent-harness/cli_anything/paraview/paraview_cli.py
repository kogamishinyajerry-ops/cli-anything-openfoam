"""ParaView CLI harness — CFD post-processing and visualization."""
from __future__ import annotations
import json
import re
import subprocess
import sys
from pathlib import Path

import click

from .utils import paraview_backend as pb

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
    """ParaView CLI harness — CFD post-processing."""
    global JSON_MODE
    JSON_MODE = use_json
    ctx.ensure_object(dict)
    ctx.obj["container"] = container


@cli.command("screenshot")
@click.option("--case", required=True, help="OpenFOAM case directory (in container)")
@click.option("--field", default="U", help="Field to visualize")
@click.option("--time", "time_val", default="latest")
@click.option("--view", default="iso", help="View angle: iso, top, front, side")
@click.option("--width", type=int, default=1200)
@click.option("--height", type=int, default=800)
@click.option("-o", "--output", required=True, help="Output PNG file (host path)")
@click.pass_context
def screenshot(ctx, case, field, time_val, view, width, height, output):
    """Take a screenshot of a field from an OpenFOAM case."""
    container = ctx.obj["container"]
    container_out = f"/tmp/{Path(output).name}"
    r = pb.screenshot(case, field, container_out, time_val, view, width, height, container)
    if "SCREENSHOT_OK" not in r.output:
        error(f"Screenshot failed: {r.output[-200:]}{r.error[-200:]}")
        if JSON_MODE: json_out({"status": "failed", "error": r.error[-200:]})
        sys.exit(1)
    subprocess.run(["docker", "cp", f"{container}:{container_out}", output],
                   check=True, timeout=30)
    t = re.search(r'TIME=([\d.eE+-]+)', r.output)
    success(f"Screenshot → {output} (field={field}, t={t.group(1) if t else '?'})")
    if JSON_MODE:
        json_out({"status": "ok", "file": output, "field": field,
                  "time": float(t.group(1)) if t else None})


@cli.command("extract")
@click.option("--case", required=True, help="OpenFOAM case directory (in container)")
@click.option("--field", default="U")
@click.option("--line", default=None, help="Line endpoints: 'x1,y1,z1 x2,y2,z2'")
@click.option("--slice", "slice_spec", default=None, help="Slice: 'origin:x,y,z normal:x,y,z'")
@click.option("--points", type=int, default=100)
@click.option("-o", "--output", required=True, help="Output CSV file (host path)")
@click.pass_context
def extract(ctx, case, field, line, slice_spec, points, output):
    """Extract field data along a line or slice."""
    container = ctx.obj["container"]
    container_out = f"/tmp/{Path(output).name}"

    if line:
        parts = line.split()
        if len(parts) != 2:
            error("Line format: 'x1,y1,z1 x2,y2,z2'")
            sys.exit(1)
        r = pb.extract_line(case, field, parts[0], parts[1], container_out, points, container)
        if "EXTRACT_OK" not in r.output:
            error(f"Extract failed: {r.output[-200:]}{r.error[-200:]}")
            sys.exit(1)
    elif slice_spec:
        m = re.match(r'origin:([\d.,eE+-]+)\s+normal:([\d.,eE+-]+)', slice_spec)
        if not m:
            error("Slice format: 'origin:x,y,z normal:x,y,z'")
            sys.exit(1)
        r = pb.extract_slice(case, field, m.group(1), m.group(2), container_out, container)
        if "SLICE_OK" not in r.output:
            error(f"Slice failed: {r.output[-200:]}{r.error[-200:]}")
            sys.exit(1)
    else:
        error("Specify --line or --slice")
        sys.exit(1)

    subprocess.run(["docker", "cp", f"{container}:{container_out}", output],
                   check=True, timeout=30)
    success(f"Extracted → {output}")
    if JSON_MODE:
        json_out({"status": "ok", "file": output})


@cli.command("info")
@click.option("--case", required=True, help="OpenFOAM case directory (in container)")
@click.pass_context
def info_cmd(ctx, case):
    """Show case info: time steps, fields, boundaries."""
    container = ctx.obj["container"]
    r = pb.get_case_info(case, container)
    if "INFO_OK" not in r.output:
        error(f"Failed: {r.output[-200:]}{r.error[-200:]}")
        sys.exit(1)
    info = {}
    for key in ["TIMES", "CELL_FIELDS", "POINT_FIELDS", "REGIONS"]:
        m = re.search(rf'{key}=(.+)', r.output)
        if m: info[key.lower()] = m.group(1)
    for k, v in info.items():
        echo(f"  {k}: {v}")
    if JSON_MODE:
        json_out(info)


def main():
    cli(obj={})
