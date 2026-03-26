"""
test_full_e2e.py — E2E tests for OpenFOAM CLI harness

Tests run on the HOST machine, using Docker container 'cfd-openfoam' for real OpenFOAM.
Run with:
  PYTHONPATH=/path/to/harness python3 -m pytest cli_anything/openfoam/tests/test_full_e2e.py -v
"""

import json
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from cli_anything.openfoam.utils import dict_parser as dp
from cli_anything.openfoam.utils import openfoam_backend as ob


CONTAINER = "cfd-openfoam"
HARNESS_ROOT = Path(__file__).parent.parent.parent.parent


# -------------------------------------------------------------------
# Constants
# -------------------------------------------------------------------

MINIMAL_CONTROLDICT = textwrap.dedent("""\
    FoamFile
    {
        version     2.0;
        format      ascii;
        class       dictionary;
        object      controlDict;
    }
    application     blockMesh;
    startFrom       startTime;
    startTime       0;
    stopAt          endTime;
    endTime         1;
    deltaT          1;
    writeControl    timeStep;
    writeInterval   1;
    runTimeModifiable yes;
    """)


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------

def docker_cp(src_path: Path, container_path: str):
    """Copy a directory into the container's /home/openfoam area.

    docker cp preserves host UID 502 ownership; inside the container this UID
    appears as "openfoam" via nss_wrapper but isn't the openfoam user's numeric
    UID (98765), so openfoam can't chmod or rm the files. Workaround:
    - rm/mkdir as root (container root maps to host root)
    - docker cp (files owned by UID 502)
    - chmod as root to make everything writable for openfoam
    """
    # Remove any stale directory (may be owned by UID 502, needs root to rm)
    subprocess.run(
        ["docker", "exec", "-u", "root", CONTAINER, "bash", "-c",
         f"rm -rf {container_path} && mkdir -p {container_path}"],
        check=True, timeout=10,
    )
    # docker cp preserves host UID 502 ownership inside the container
    subprocess.run(
        ["docker", "cp", str(src_path) + "/.", f"{CONTAINER}:{container_path}"],
        check=True, timeout=30,
    )
    # chmod as root so openfoam user can read/write everything
    subprocess.run(
        ["docker", "exec", "-u", "root", CONTAINER, "bash", "-c",
         f"chmod -R a+rwX {container_path}"],
        check=True, timeout=10,
    )


# -------------------------------------------------------------------
# True backend tests (real OpenFOAM commands via container)
# -------------------------------------------------------------------

class TestTrueBackend:
    """Tests that run real OpenFOAM commands via cfd-openfoam container."""

    def test_blockmesh_simple_cube(self):
        """Run blockMesh on a simple cube case."""
        with tempfile.TemporaryDirectory() as tmp:
            case_name = "cubeCase"
            case = Path(tmp) / case_name
            case.mkdir()
            system = case / "system"
            system.mkdir()
            (system / "controlDict").write_text(MINIMAL_CONTROLDICT)
            (system / "blockMeshDict").write_text(textwrap.dedent("""\
                FoamFile
                {
                    version     2.0;
                    format      ascii;
                    class       dictionary;
                    object      blockMeshDict;
                }
                convertToMeters 1;
                vertices
                (
                    (0 0 0)
                    (1 0 0)
                    (1 1 0)
                    (0 1 0)
                    (0 0 1)
                    (1 0 1)
                    (1 1 1)
                    (0 1 1)
                );
                blocks
                (
                    hex (0 1 2 3 4 5 6 7) (10 10 10) simpleGrading (1 1 1)
                );
                edges
                ();
                boundary
                (
                    walls
                    {
                        type wall;
                        faces ((3 7 6 2));
                    }
                    empty
                    {
                        type empty;
                        faces ((0 4 5 1));
                    }
                );
                """))

            docker_cp(case, f"/home/openfoam/{case_name}")

            r = ob.run_blockmesh(Path(f"/home/openfoam/{case_name}"), container=CONTAINER)
            assert r.success, f"blockMesh failed: {r.error}"

    def test_checkmesh_quality(self):
        """Run checkMesh and parse quality output."""
        with tempfile.TemporaryDirectory() as tmp:
            case_name = "meshCase"
            case = Path(tmp) / case_name
            case.mkdir()
            system = case / "system"
            system.mkdir()
            (system / "controlDict").write_text(MINIMAL_CONTROLDICT)
            (system / "blockMeshDict").write_text(textwrap.dedent("""\
                FoamFile
                {
                    version     2.0;
                    format      ascii;
                    class       dictionary;
                    object      blockMeshDict;
                }
                convertToMeters 1;
                vertices
                (
                    (0 0 0) (1 0 0) (1 1 0) (0 1 0)
                    (0 0 1) (1 0 1) (1 1 1) (0 1 1)
                );
                blocks
                (
                    hex (0 1 2 3 4 5 6 7) (5 5 5) simpleGrading (1 1 1)
                );
                edges
                ();
                boundary
                (
                    wall
                    {
                        type wall;
                        faces ((3 7 6 2));
                    }
                );
                """))

            docker_cp(case, f"/home/openfoam/{case_name}")

            ret1 = ob._run(
                ["blockMesh"],
                cwd=Path(f"/home/openfoam/{case_name}"),
                container=CONTAINER,
            )
            assert ret1.success, f"blockMesh failed: {ret1.error}"

            r = ob.run_checkmesh(Path(f"/home/openfoam/{case_name}"), container=CONTAINER)
            assert r.success, f"checkMesh failed: {r.error}"
            quality = ob.parse_checkmesh_quality(r.output)
            assert quality["cells"] > 0, "No cells in mesh"

    def test_latest_time_detection(self):
        """Verify get_latest_time finds correct time directory."""
        with tempfile.TemporaryDirectory() as tmp:
            case_name = "timeCase"
            case = Path(tmp) / case_name
            case.mkdir()
            (case / "0").mkdir()
            (case / "0.5").mkdir()
            (case / "1.0").mkdir()

            t = ob.get_latest_time(case)
            assert t == 1.0

    def test_full_workflow(self):
        """Complete workflow: blockMesh -> checkMesh via backend."""
        with tempfile.TemporaryDirectory() as tmp:
            case_name = "fullWorkflow"
            case = Path(tmp) / case_name
            case.mkdir()
            system = case / "system"
            constant = case / "constant"
            zero = case / "0"
            system.mkdir()
            constant.mkdir()
            zero.mkdir()

            (system / "controlDict").write_text(MINIMAL_CONTROLDICT)
            (system / "blockMeshDict").write_text(textwrap.dedent("""\
                FoamFile { version 2.0; format ascii; class dictionary; object blockMeshDict; }
                convertToMeters 1;
                vertices
                (
                    (0 0 0) (1 0 0) (1 1 0) (0 1 0)
                    (0 0 1) (1 0 1) (1 1 1) (0 1 1)
                );
                blocks
                (
                    hex (0 1 2 3 4 5 6 7) (8 8 8) simpleGrading (1 1 1)
                );
                edges ();
                boundary
                (
                    wall { type wall; faces ((3 7 6 2)); }
                    frontAndBack { type empty; faces ((0 4 5 1)); }
                );
                """))

            docker_cp(case, f"/home/openfoam/{case_name}")

            r1 = ob.run_blockmesh(Path(f"/home/openfoam/{case_name}"), container=CONTAINER)
            assert r1.success, f"blockMesh failed: {r1.error}"

            r2 = ob.run_checkmesh(Path(f"/home/openfoam/{case_name}"), container=CONTAINER)
            assert r2.success, f"checkMesh failed: {r2.error}"
            quality = ob.parse_checkmesh_quality(r2.output)
            assert quality["cells"] > 0


# -------------------------------------------------------------------
# Native E2E tests (no real OpenFOAM, just harness logic)
# -------------------------------------------------------------------

class TestNativeE2E:
    """Tests that use synthetic data and don't require real OpenFOAM."""

    def test_case_new_all_templates(self):
        """Create cases with all three templates."""
        templates = ["simpleFoam", "icoFoam", "pimpleFoam"]
        for tmpl in templates:
            with tempfile.TemporaryDirectory() as tmp:
                result = subprocess.run(
                    [sys.executable, "-m", "cli_anything.openfoam",
                     "--json", "case", "new",
                     "--output", str(Path(tmp) / f"{tmpl}Case"),
                     "--template", tmpl, f"{tmpl}Case"],
                    capture_output=True,
                    text=True,
                    env={**__import__("os").environ, "PYTHONPATH": str(HARNESS_ROOT)},
                    cwd=str(HARNESS_ROOT),
                    timeout=30,
                )
                assert result.returncode == 0, f"template {tmpl} failed: {result.stderr}"
                data = json.loads(result.stdout)
                assert data["solver"] == tmpl

    def test_parameters_substitution(self):
        """Test #VAR# substitution in case files."""
        with tempfile.TemporaryDirectory() as tmp:
            case = Path(tmp) / "subCase"
            case.mkdir()
            system = case / "system"
            system.mkdir()

            control = system / "controlDict"
            dp.write_dict(control, {
                "startTime": 0,
                "endTime": "#END_TIME#",
                "deltaT": "#DT#",
            })

            dp.substitute_vars(control, {"END_TIME": 500, "DT": 0.001})
            result = dp.read_dict(control)
            assert result["endTime"] == 500
            assert result["deltaT"] == 0.001

    def test_parallel_decomp_dict(self):
        """Verify decomposeParDict is created for parallel."""
        with tempfile.TemporaryDirectory() as tmp:
            case = Path(tmp) / "parCase"
            case.mkdir()
            system = case / "system"
            system.mkdir()
            constant = case / "constant"
            constant.mkdir()

            (system / "controlDict").write_text(textwrap.dedent("""\
                FoamFile { version 2.0; format ascii; class dictionary; object controlDict; }
                application simpleFoam;
                startFrom startTime; startTime 0;
                stopAt endTime; endTime 100;
                deltaT 1;
                """))
            (constant / "turbulenceProperties").write_text(textwrap.dedent("""\
                FoamFile { version 2.0; format ascii; class dictionary; object turbulenceProperties; }
                simulationType laminar;
                """))

            decomp = system / "decomposeParDict"
            dp.write_dict(decomp, {
                "numberOfSubdomains": 4,
                "method": "simple",
                "simpleCoeffs": {"n": "(2 2 1)"},
            })
            assert decomp.exists()
            data = dp.read_dict(decomp)
            assert data["numberOfSubdomains"] == 4
