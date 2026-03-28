"""
blender_backend.py - Blender CLI wrapper

Wraps Blender's --background mode for headless batch processing.

Blender is installed via:
  - macOS: DMG from blender.org or brew install blender
  - Linux: tarball from blender.org or apt install blender
  - Windows: MSI from blender.org

Principles:
  - MUST call real Blender commands, not reimplement
  - Software is HARD dependency - error clearly if not found
  - Supports headless/server rendering and batch processing
  - Operations via Python scripts passed to Blender's internal interpreter
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


# -------------------------------------------------------------------
# Version
# -------------------------------------------------------------------

BLENDER_VERSION = "1.0.0"


# -------------------------------------------------------------------
# Installation detection
# -------------------------------------------------------------------

BLENDER_PATHS = [
    "/usr/local/bin/blender",
    "/usr/bin/blender",
    "/Applications/Blender.app/Contents/MacOS/Blender",
    Path.home() / "blender/blender.app/Contents/MacOS/Blender",
]


def find_blender() -> Path:
    """
    Locate Blender binary.

    Returns Path to blender executable.
    Raises RuntimeError if not found.
    """
    if os.environ.get("BLENDER_MOCK"):
        return Path("/usr/bin/true")

    blender_bin = os.environ.get("BLENDER_PATH")

    if not blender_bin:
        for candidate in BLENDER_PATHS:
            p = Path(candidate)
            if p.exists():
                blender_bin = str(p)
                break

    if not blender_bin:
        try:
            result = subprocess.run(
                ["which", "blender"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0 and result.stdout.strip():
                blender_bin = result.stdout.strip()
        except Exception:
            pass

    if not blender_bin:
        if os.environ.get("BLENDER_MOCK"):
            return Path("/usr/bin/true")
        raise RuntimeError(
            "Blender not found.\n"
            "Set BLENDER_PATH env var or install Blender.\n"
            "macOS: brew install blender\n"
            "Linux: sudo apt install blender\n"
            "Download: https://blender.org/download"
        )

    bin_path = Path(blender_bin)
    if not bin_path.exists():
        if os.environ.get("BLENDER_MOCK"):
            return Path("/usr/bin/true")
        raise RuntimeError("Blender not found at {}".format(bin_path))

    return bin_path


# -------------------------------------------------------------------
# Result dataclass
# -------------------------------------------------------------------

@dataclass
class CommandResult:
    """Result of a Blender command execution."""
    success: bool
    output: str = ""
    error: str = ""
    returncode: int = 0
    duration_seconds: float = 0.0


# -------------------------------------------------------------------
# Core runner
# -------------------------------------------------------------------

def _run(
    args: list,
    script: Optional[str] = None,
    python_script: Optional[str] = None,
    timeout: int = 300,
    check: bool = True,
) -> CommandResult:
    """
    Run Blender command.

    Args:
        args: Additional Blender arguments
        script: Blender script file to run (--python or --script)
        python_script: Python code string to execute
        timeout: Max seconds
        check: Raise on non-zero exit

    Returns:
        CommandResult
    """
    blender = find_blender()

    cmd = [str(blender), "--background"]

    # Handle python script execution
    if python_script:
        cmd.extend(["--python-expr", python_script])
    elif script:
        cmd.extend(["--python", str(script)])

    cmd.extend(args)

    start = time.time()
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
        )
        duration = time.time() - start

        if check and proc.returncode != 0:
            return CommandResult(
                success=False,
                output=proc.stdout,
                error=proc.stderr,
                returncode=proc.returncode,
                duration_seconds=duration,
            )

        return CommandResult(
            success=proc.returncode == 0,
            output=proc.stdout,
            error=proc.stderr,
            returncode=proc.returncode,
            duration_seconds=duration,
        )
    except subprocess.TimeoutExpired:
        return CommandResult(
            success=False,
            output="",
            error="Command timed out after {}s".format(timeout),
            returncode=-1,
            duration_seconds=timeout,
        )
    except Exception as e:
        return CommandResult(
            success=False,
            output="",
            error=str(e),
            returncode=-99,
            duration_seconds=time.time() - start,
        )


# -------------------------------------------------------------------
# Version / Info
# -------------------------------------------------------------------

def get_version() -> dict:
    """Get Blender version."""
    if os.environ.get("BLENDER_MOCK"):
        return {
            "success": True,
            "version": "4.2.0",
            "version_string": "4.2.0 (hash abc123)",
        }

    blender = find_blender()
    try:
        proc = subprocess.run(
            [str(blender), "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if proc.returncode == 0:
            version_str = proc.stdout.strip()
            match = re.match(r"Blender (\d+\.\d+\.\d+)", version_str)
            version = match.group(1) if match else version_str
            return {
                "success": True,
                "version": version,
                "version_string": version_str,
            }
    except Exception:
        pass

    return {"success": False, "error": "Failed to get Blender version"}


# -------------------------------------------------------------------
# Render operations
# -------------------------------------------------------------------

def render_image(
    blend_path: str,
    output_path: str,
    frame: int = 1,
    resolution_x: int = 1920,
    resolution_y: int = 1080,
    engine: str = "CYCLES",
    samples: int = 128,
    gpu: bool = False,
) -> CommandResult:
    """
    Render a Blender scene to image.

    Args:
        blend_path: Path to .blend file
        output_path: Output image path
        frame: Frame number
        resolution_x: Horizontal resolution
        resolution_y: Vertical resolution
        engine: Render engine (CYCLES, EEVEE, WORKBENCH)
        samples: Sample count (for Cycles)
        gpu: Use GPU rendering

    Returns:
        CommandResult
    """
    blend = Path(blend_path)
    if not blend.exists():
        return CommandResult(
            success=False,
            error="Blend file not found: {}".format(blend),
            returncode=1,
        )

    if os.environ.get("BLENDER_MOCK"):
        return CommandResult(
            success=True,
            output="Rendered frame {} to {}".format(frame, output_path),
            returncode=0,
        )

    python_expr = (
        "import bpy; "
        "bpy.context.scene.render.filepath = '{}'; "
        "bpy.context.scene.frame_set({}); "
        "bpy.ops.render.render(write_still=True)"
    ).format(output_path, frame)

    args = [
        "--render-output", output_path,
        "--render-frame", str(frame),
        "--render-engine", engine,
        "--python-expr", python_expr,
    ]

    if gpu:
        args.append("--cycles-device", "GPU")

    return _run(args, timeout=600, check=False)


def render_animation(
    blend_path: str,
    output_dir: str,
    start_frame: int = 1,
    end_frame: int = 250,
    resolution_x: int = 1920,
    resolution_y: int = 1080,
    engine: str = "CYCLES",
) -> CommandResult:
    """
    Render Blender animation.

    Args:
        blend_path: Path to .blend file
        output_dir: Output directory for frames
        start_frame: Start frame
        end_frame: End frame
        resolution_x: Horizontal resolution
        resolution_y: Vertical resolution
        engine: Render engine

    Returns:
        CommandResult
    """
    blend = Path(blend_path)
    if not blend.exists():
        return CommandResult(
            success=False,
            error="Blend file not found: {}".format(blend),
            returncode=1,
        )

    if os.environ.get("BLENDER_MOCK"):
        return CommandResult(
            success=True,
            output="Rendered frames {}-{} to {}".format(start_frame, end_frame, output_dir),
            returncode=0,
        )

    python_expr = (
        "import bpy; "
        "sc = bpy.context.scene; "
        "sc.render.filepath = '{}'; "
        "sc.frame_start = {}; "
        "sc.frame_end = {}; "
        "bpy.ops.render.render(animation=True)"
    ).format(output_dir, start_frame, end_frame)

    args = [
        "--render-anim",
        "--render-engine", engine,
        "--python-expr", python_expr,
    ]

    return _run(args, timeout=3600, check=False)


# -------------------------------------------------------------------
# Scene operations
# -------------------------------------------------------------------

def new_scene(
    scene_name: str = "Scene",
) -> CommandResult:
    """Create a new Blender scene."""
    if os.environ.get("BLENDER_MOCK"):
        return CommandResult(
            success=True,
            output="Created new scene: {}".format(scene_name),
            returncode=0,
        )

    python_expr = (
        "import bpy; "
        "bpy.ops.scene.add_type(type='EMPTY'); "
        "bpy.context.scene.name = '{}'"
    ).format(scene_name)

    return _run(["--python-expr", python_expr], timeout=30, check=False)


def import_model(
    model_path: str,
    import_type: Optional[str] = None,
) -> CommandResult:
    """
    Import a 3D model.

    Args:
        model_path: Path to model file
        import_type: Auto-detected from extension if None

    Returns:
        CommandResult
    """
    model = Path(model_path)
    if not model.exists() and not os.environ.get("BLENDER_MOCK"):
        return CommandResult(
            success=False,
            error="Model file not found: {}".format(model),
            returncode=1,
        )

    ext = model.suffix.lower()

    # Map extension to import operator
    importers = {
        ".obj": "obj",
        ".fbx": "fbx",
        ".gltf": "gltf",
        ".glb": "gltf",
        ".stl": "stl",
        ".ply": "ply",
        ".3ds": "3ds",
        ".dae": "dae",
        ".x3d": "x3d",
    }

    if import_type:
        imp = import_type
    elif ext in importers:
        imp = importers[ext]
    else:
        return CommandResult(
            success=False,
            error="Unknown model extension: {} (supported: {})".format(
                ext, ", ".join(sorted(importers.keys()))
            ),
            returncode=1,
        )

    if os.environ.get("BLENDER_MOCK"):
        return CommandResult(
            success=True,
            output="Imported {} as {}".format(model_path, imp),
            returncode=0,
        )

    python_expr = (
        "import bpy; "
        "bpy.ops.import_scene.{}(filepath='{}')"
    ).format(imp, model_path)

    return _run(["--python-expr", python_expr], timeout=120, check=False)


def export_model(
    blend_path: str,
    output_path: str,
    export_type: Optional[str] = None,
) -> CommandResult:
    """
    Export a Blender model.

    Args:
        blend_path: Path to .blend file (or use current scene if None)
        output_path: Output file path
        export_type: Auto-detected from extension if None

    Returns:
        CommandResult
    """
    if export_type is None:
        ext = Path(output_path).suffix.lower()
        exporters = {
            ".obj": "obj",
            ".fbx": "fbx",
            ".gltf": "gltf",
            ".glb": "gltf",
            ".stl": "stl",
            ".ply": "ply",
            ".3ds": "3ds",
            ".dae": "dae",
            ".x3d": "x3d",
            ".blend": "blend",
        }
        export_type = exporters.get(ext, "obj")

    if os.environ.get("BLENDER_MOCK"):
        return CommandResult(
            success=True,
            output="Exported to {}".format(output_path),
            returncode=0,
        )

    python_expr = (
        "import bpy; "
        "bpy.ops.export_scene.{}(filepath='{}')"
    ).format(export_type, output_path)

    return _run(["--python-expr", python_expr], timeout=120, check=False)


# -------------------------------------------------------------------
# Object operations
    # -------------------------------------------------------------------

def list_objects(blend_path: Optional[str] = None) -> dict:
    """
    List objects in a blend file.

    Returns:
        dict with object list
    """
    if os.environ.get("BLENDER_MOCK"):
        return {
            "success": True,
            "objects": [
                {"name": "Cube", "type": "MESH"},
                {"name": "Light", "type": "LIGHT"},
                {"name": "Camera", "type": "CAMERA"},
            ],
        }

    script = """
import bpy
objects = []
for obj in bpy.data.objects:
    objects.append({"name": obj.name, "type": obj.type})
import json
print(json.dumps({"success": True, "objects": objects}))
"""

    result = _run([], python_script=script, timeout=30, check=False)

    if result.success:
        try:
            return json.loads(result.output)
        except Exception:
            pass

    return {"success": False, "error": result.error or "Failed to list objects"}


def get_object_info(
    object_name: str,
    blend_path: Optional[str] = None,
) -> dict:
    """
    Get info about a specific object.

    Returns:
        dict with object properties
    """
    if os.environ.get("BLENDER_MOCK"):
        return {
            "success": True,
            "name": object_name,
            "type": "MESH",
            "location": [0.0, 0.0, 0.0],
            "rotation": [0.0, 0.0, 0.0],
            "scale": [1.0, 1.0, 1.0],
        }

    script = (
        "import bpy; "
        "import json; "
        "obj = bpy.data.objects.get('{}'); "
        "if obj: "
        "    print(json.dumps({{"
        "        'success': True, "
        "        'name': obj.name, "
        "        'type': obj.type, "
        "        'location': list(obj.location), "
        "        'rotation': list(obj.rotation_euler), "
        "        'scale': list(obj.scale)"
        "    }})); "
        "else: print(json.dumps({{'success': False, 'error': 'Object not found'}}))"
    ).format(object_name)

    result = _run([], python_script=script, timeout=30, check=False)

    if result.success:
        try:
            return json.loads(result.output)
        except Exception:
            pass

    return {"success": False, "error": result.error or "Failed to get object info"}


# -------------------------------------------------------------------
# Material / Texture operations
# -------------------------------------------------------------------

def add_material(
    material_name: str,
    object_name: str,
    blend_path: Optional[str] = None,
) -> CommandResult:
    """Add a material to an object."""
    if os.environ.get("BLENDER_MOCK"):
        return CommandResult(
            success=True,
            output="Added material {} to {}".format(material_name, object_name),
            returncode=0,
        )

    python_expr = (
        "import bpy; "
        "mat = bpy.data.materials.new(name='{}'); "
        "obj = bpy.data.objects.get('{}'); "
        "if obj: "
        "    obj.data.materials.append(mat); "
        "    print('Material added'); "
        "else: print('Object not found')"
    ).format(material_name, object_name)

    return _run(["--python-expr", python_expr], timeout=30, check=False)


# -------------------------------------------------------------------
# Modifier operations
# -------------------------------------------------------------------

def add_modifier(
    object_name: str,
    modifier_type: str,
    blend_path: Optional[str] = None,
) -> CommandResult:
    """
    Add a modifier to an object.

    Args:
        object_name: Name of object
        modifier_type: 'SUBSURF', 'MIRROR', 'ARRAY', 'BEVEL', 'SOLIDIFY', 'DECIMATE'

    Returns:
        CommandResult
    """
    modifier_map = {
        "SUBSURF": "subsurf",
        "MIRROR": "mirror",
        "ARRAY": "array",
        "BEVEL": "bevel",
        "SOLIDIFY": "solidify",
        "DECIMATE": "decimate",
        "UV_PROJECT": "uv_project",
        "SMOOTH": "smooth",
        "SIMPLE_DEFORM": "simple_deform",
    }

    if modifier_type.upper() not in modifier_map:
        return CommandResult(
            success=False,
            error="Unknown modifier type: {} (supported: {})".format(
                modifier_type, ", ".join(sorted(modifier_map.keys()))
            ),
            returncode=1,
        )

    mod_name = modifier_map[modifier_type.upper()]

    if os.environ.get("BLENDER_MOCK"):
        return CommandResult(
            success=True,
            output="Added {} modifier to {}".format(modifier_type, object_name),
            returncode=0,
        )

    python_expr = (
        "import bpy; "
        "obj = bpy.data.objects.get('{}'); "
        "if obj: "
        "    mod = obj.modifiers.new(name='{}', type='{}'); "
        "    print('Modifier added'); "
        "else: print('Object not found')"
    ).format(object_name, modifier_type, mod_name)

    return _run(["--python-expr", python_expr], timeout=30, check=False)


# -------------------------------------------------------------------
# Stats / Info
# -------------------------------------------------------------------

def get_scene_stats(blend_path: Optional[str] = None) -> dict:
    """
    Get scene statistics.

    Returns:
        dict with scene stats
    """
    if os.environ.get("BLENDER_MOCK"):
        return {
            "success": True,
            "objects": 42,
            "meshes": 12,
            "materials": 8,
            "lights": 3,
            "cameras": 1,
            "vertices": 12345,
            "triangles": 6789,
        }

    script = (
        "import bpy; "
        "import json; "
        "scene = bpy.context.scene; "
        "stats = {"
        "    'objects': len(bpy.data.objects), "
        "    'meshes': len([o for o in bpy.data.objects if o.type == 'MESH']), "
        "    'materials': len(bpy.data.materials), "
        "    'lights': len([o for o in bpy.data.objects if o.type == 'LIGHT']), "
        "    'cameras': len([o for o in bpy.data.objects if o.type == 'CAMERA']), "
        "}; "
        "print(json.dumps({'success': True, **stats}))"
    )

    result = _run([], python_script=script, timeout=30, check=False)

    if result.success:
        try:
            return json.loads(result.output)
        except Exception:
            pass

    return {"success": False, "error": result.error or "Failed to get stats"}


# -------------------------------------------------------------------
# Batch operations
# -------------------------------------------------------------------

def batch_convert(
    input_dir: str,
    output_dir: str,
    input_format: str,
    output_format: str,
) -> CommandResult:
    """
    Batch convert files from one format to another.

    Args:
        input_dir: Input directory
        output_dir: Output directory
        input_format: Input format (e.g. 'obj', 'fbx')
        output_format: Output format (e.g. 'gltf', 'glb')

    Returns:
        CommandResult
    """
    input_path = Path(input_dir)
    output_path = Path(output_dir)

    if os.environ.get("BLENDER_MOCK"):
        return CommandResult(
            success=True,
            output="Converted all .{} files from {} to {}".format(
                input_format, input_dir, output_dir
            ),
            returncode=0,
        )

    output_path.mkdir(parents=True, exist_ok=True)

    python_expr = (
        "import bpy; "
        "import os; "
        "from pathlib import Path; "
        "indir = '{}'; "
        "outdir = '{}'; "
        "fmt = '{}'; "
        "for f in Path(indir).glob('*.{}'): "
        "    bpy.ops.import_scene.{}(filepath=str(f)); "
        "    outname = str(Path(outdir) / (f.stem + '.{}')); "
        "    bpy.ops.export_scene.{}(filepath=outname); "
        "print('Batch conversion complete')"
    ).format(input_dir, output_dir, input_format, input_format, input_format, output_format, output_format)

    return _run(["--python-expr", python_expr], timeout=600, check=False)
