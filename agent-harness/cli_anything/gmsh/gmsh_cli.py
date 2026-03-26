"""Gmsh CLI harness — mesh generation for CFD workflows."""
from __future__ import annotations
import json
import sys
from pathlib import Path
from typing import Optional

import click

from .utils import gmsh_backend as gb

JSON_MODE = False


def echo(msg): click.echo(msg, err=True)
def success(msg): click.echo(click.style(f"✓ {msg}", fg="green"), err=True)
def warn(msg): click.echo(click.style(f"⚠ {msg}", fg="yellow"), err=True)
def error(msg): click.echo(click.style(f"✗ {msg}", fg="red"), err=True)
def json_out(data): click.echo(json.dumps(data, indent=2))


@click.group()
@click.option("--json", "use_json", is_flag=True, help="JSON output mode")
@click.option("--container", default="cfd-openfoam", help="Docker container name")
@click.pass_context
def cli(ctx, use_json: bool, container: str):
    """Gmsh CLI harness — mesh generation for CFD."""
    global JSON_MODE
    JSON_MODE = use_json
    ctx.ensure_object(dict)
    ctx.obj["container"] = container


# ---- geo group ----

@cli.group()
def geo():
    """Create geometry (.geo) files."""
    pass


@geo.command("create-box")
@click.option("--x", type=float, required=True, help="Length in X")
@click.option("--y", type=float, required=True, help="Length in Y")
@click.option("--z", type=float, required=True, help="Length in Z")
@click.option("--mesh-size", type=float, default=0.5, help="Max element size")
@click.option("-o", "--output", required=True, help="Output .geo file")
def geo_box(x, y, z, mesh_size, output):
    """Create a box geometry."""
    content = gb.create_geo_box(x, y, z, mesh_size)
    Path(output).write_text(content)
    success(f"Box geometry → {output}")
    if JSON_MODE:
        json_out({"status": "ok", "file": output, "dimensions": [x, y, z]})


@geo.command("create-cylinder")
@click.option("--radius", type=float, required=True)
@click.option("--length", type=float, required=True)
@click.option("--mesh-size", type=float, default=0.3)
@click.option("-o", "--output", required=True)
def geo_cylinder(radius, length, mesh_size, output):
    """Create a cylinder geometry."""
    content = gb.create_geo_cylinder(radius, length, mesh_size)
    Path(output).write_text(content)
    success(f"Cylinder geometry → {output}")
    if JSON_MODE:
        json_out({"status": "ok", "file": output})


@geo.command("create-channel")
@click.option("--length", type=float, required=True)
@click.option("--height", type=float, required=True)
@click.option("--depth", type=float, default=0.1)
@click.option("--mesh-size", type=float, default=0.2)
@click.option("-o", "--output", required=True)
def geo_channel(length, height, depth, mesh_size, output):
    """Create a 2D channel with inlet/outlet/walls boundaries."""
    content = gb.create_geo_channel(length, height, depth, mesh_size)
    Path(output).write_text(content)
    success(f"Channel geometry → {output}")
    if JSON_MODE:
        json_out({"status": "ok", "file": output})


# ---- mesh group ----

@cli.group()
def mesh():
    """Generate and manipulate meshes."""
    pass


@mesh.command("generate")
@click.option("--input", "input_file", required=True, help="Input .geo file")
@click.option("--dim", type=int, default=3, help="Mesh dimension (2 or 3)")
@click.option("--format", "fmt", default="msh2", help="Output format (msh2, openfoam)")
@click.option("-o", "--output", default=None, help="Output mesh file")
@click.option("--case", default=None, help="OpenFOAM case dir (when format=openfoam)")
@click.pass_context
def mesh_generate(ctx, input_file, dim, fmt, output, case):
    """Generate mesh from .geo file."""
    container = ctx.obj["container"]

    if fmt == "openfoam":
        # Two-step: gmsh → .msh → gmshToFoam
        import subprocess, tempfile
        msh_tmp = f"/tmp/gmsh_temp_{Path(input_file).stem}.msh"
        # Copy .geo to container
        container_geo = f"/tmp/{Path(input_file).name}"
        subprocess.run(["docker", "cp", input_file, f"{container}:{container_geo}"],
                       check=True, timeout=10)
        r = gb.mesh_generate(Path(container_geo), Path(msh_tmp), dim, "msh2", container)
        if not r.success:
            error(f"Mesh generation failed: {r.error[-200:]}")
            if JSON_MODE: json_out({"status": "failed", "error": r.error[-200:]})
            sys.exit(1)
        # Parse mesh stats from gmsh output
        text = r.output + r.error
        import re
        nodes = elements = 0
        m = re.search(r'(\d+)\s+vertices', text)
        if m: nodes = int(m.group(1))
        m = re.search(r'(\d+)\s+elements', text)
        if m: elements = int(m.group(1))

        case_dir = case or "./gmshCase"
        container_case = f"/home/openfoam/{Path(case_dir).name}"
        r2 = gb.convert_to_openfoam(Path(msh_tmp), Path(container_case), container)
        if not r2.success:
            error(f"gmshToFoam failed: {r2.error[-200:]}")
            if JSON_MODE: json_out({"status": "failed", "error": r2.error[-200:]})
            sys.exit(1)
        # Copy result back
        Path(case_dir).mkdir(parents=True, exist_ok=True)
        subprocess.run(["docker", "cp", f"{container}:{container_case}/.", case_dir + "/."],
                       check=True, timeout=30)
        success(f"Mesh → OpenFOAM case: {case_dir} ({nodes} nodes, {elements} elements)")
        if JSON_MODE:
            json_out({"status": "ok", "case": case_dir, "nodes": nodes, "elements": elements})
    else:
        import subprocess
        container_geo = f"/tmp/{Path(input_file).name}"
        subprocess.run(["docker", "cp", input_file, f"{container}:{container_geo}"],
                       check=True, timeout=10)
        out = output or f"/tmp/{Path(input_file).stem}.msh"
        container_out = f"/tmp/{Path(out).name}"
        r = gb.mesh_generate(Path(container_geo), Path(container_out), dim, fmt, container)
        if not r.success:
            error(f"Mesh generation failed: {r.error[-200:]}")
            sys.exit(1)
        subprocess.run(["docker", "cp", f"{container}:{container_out}", out],
                       check=True, timeout=30)
        text = r.output + r.error
        import re
        nodes = elements = 0
        m = re.search(r'(\d+)\s+vertices', text)
        if m: nodes = int(m.group(1))
        m = re.search(r'(\d+)\s+elements', text)
        if m: elements = int(m.group(1))
        success(f"Mesh → {out} ({nodes} nodes, {elements} elements)")
        if JSON_MODE:
            json_out({"status": "ok", "file": out, "nodes": nodes, "elements": elements})


@mesh.command("info")
@click.option("--input", "input_file", required=True)
@click.pass_context
def mesh_info_cmd(ctx, input_file):
    """Show mesh statistics."""
    container = ctx.obj["container"]
    import subprocess
    container_msh = f"/tmp/{Path(input_file).name}"
    subprocess.run(["docker", "cp", input_file, f"{container}:{container_msh}"],
                   check=True, timeout=10)
    info = gb.mesh_info(Path(container_msh), container)
    echo(f"Nodes: {info['nodes']}, Elements: {info['elements']}")
    if JSON_MODE:
        json_out(info)


# ---- convert ----

@cli.command("convert")
@click.option("--input", "input_file", required=True, help="Input .msh file")
@click.option("--format", "fmt", default="openfoam", help="Target format")
@click.option("--case", required=True, help="OpenFOAM case directory")
@click.pass_context
def convert(ctx, input_file, fmt, case):
    """Convert mesh to OpenFOAM format."""
    container = ctx.obj["container"]
    import subprocess
    container_msh = f"/tmp/{Path(input_file).name}"
    subprocess.run(["docker", "cp", input_file, f"{container}:{container_msh}"],
                   check=True, timeout=10)
    container_case = f"/home/openfoam/{Path(case).name}"
    r = gb.convert_to_openfoam(Path(container_msh), Path(container_case), container)
    if not r.success:
        error(f"Conversion failed: {r.error[-200:]}")
        sys.exit(1)
    Path(case).mkdir(parents=True, exist_ok=True)
    subprocess.run(["docker", "cp", f"{container}:{container_case}/.", case + "/."],
                   check=True, timeout=30)
    success(f"Converted → {case}")
    if JSON_MODE:
        json_out({"status": "ok", "case": case})


def main():
    cli(obj={})
