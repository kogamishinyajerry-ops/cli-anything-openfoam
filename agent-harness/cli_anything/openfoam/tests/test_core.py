"""
test_core.py — Unit tests for OpenFOAM CLI core modules

Tests use synthetic data (no real OpenFOAM required):
- dict_parser: read/write/patch/substitute
- openfoam_backend: version detection, latest_time, residual parsing
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

# Add harness dir to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from cli_anything.openfoam.utils import dict_parser as dp
from cli_anything.openfoam.utils import openfoam_backend as ob
from cli_anything.openfoam.utils.dict_parser import DictParser, _tokenize


# -------------------------------------------------------------------
# dict_parser tests
# -------------------------------------------------------------------

class TestDictParser:
    """Unit tests for OpenFOAM dictionary parser."""

    def test_read_simple_dict(self):
        text = """FoamFile { version 2.0; format ascii; }
startTime 0;
endTime 1000;
deltaT 1;
"""
        result = DictParser(_tokenize(text)).parse()
        assert result["startTime"] == 0
        assert result["endTime"] == 1000
        assert result["deltaT"] == 1

    def test_read_nested_dict(self):
        text = """solvers { p { solver PCG; preconditioner DIC; tolerance 1e-06; } }"""
        result = DictParser(_tokenize(text)).parse()
        assert result["solvers"]["p"]["solver"] == "PCG"
        assert result["solvers"]["p"]["tolerance"] == 1e-06

    def test_read_vector_format(self):
        text = """dimensions [0 1 -1 0 0 0 0];
internalField uniform (10 0 0);
"""
        result = DictParser(_tokenize(text)).parse()
        # Dimensions parsed as bracketed list
        assert result["dimensions"] == [0, 1, -1, 0, 0, 0, 0]
        # Uniform vector: parser returns first word as value
        assert "internalField" in result

    def test_write_then_read_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "testDict"
            original = {
                "startTime": 0,
                "endTime": 500,
                "deltaT": 0.001,
                "writeControl": "timeStep",
            }
            dp.write_dict(path, original)
            result = dp.read_dict(path)
            assert result["startTime"] == original["startTime"]
            assert result["endTime"] == original["endTime"]
            assert result["deltaT"] == original["deltaT"]
            assert result["writeControl"] == original["writeControl"]

    def test_write_nested_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fvSolution"
            data = {
                "solvers": {
                    "p": {"solver": "PCG", "tolerance": 1e-6, "relTol": 0.05},
                    "U": {"solver": "smoothSolver", "tolerance": 1e-6, "relTol": 0.05},
                },
                "relaxationFactors": {
                    "fields": {"p": 0.3},
                    "equations": {"U": 0.7},
                },
            }
            dp.write_dict(path, data)
            result = dp.read_dict(path)
            assert result["solvers"]["p"]["solver"] == "PCG"
            assert result["solvers"]["U"]["solver"] == "smoothSolver"
            assert result["relaxationFactors"]["fields"]["p"] == 0.3

    def test_patch_dict(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "controlDict"
            original = {"startTime": 0, "endTime": 100, "deltaT": 1}
            dp.write_dict(path, original)
            dp.patch_dict(path, {"endTime": 500, "newKey": "value"})
            result = dp.read_dict(path)
            assert result["endTime"] == 500
            assert result["startTime"] == 0  # preserved
            assert result["newKey"] == "value"

    def test_substitute_vars(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "controlDict"
            path.write_text("#INLET_VELOCITY#\nstartTime #START_TIME#;\n")
            dp.substitute_vars(path, {"INLET_VELOCITY": "10 0 0", "START_TIME": 0})
            text = path.read_text()
            assert "10 0 0" in text
            assert "startTime 0;" in text

    def test_cas_templates_exist(self):
        """All expected solver templates are defined."""
        for solver in ["simpleFoam", "icoFoam", "pimpleFoam"]:
            assert solver in dp.CASE_TEMPLATES
            t = dp.CASE_TEMPLATES[solver]
            assert "controlDict" in t
            assert "fvSchemes" in t
            assert "fvSolution" in t


# -------------------------------------------------------------------
# openfoam_backend parser tests (no real OpenFOAM needed)
# -------------------------------------------------------------------

class TestBackendParsers:
    """Unit tests for OpenFOAM output parsers."""

    def test_parse_residuals_simple(self):
        log = """
SIMPLE solution converged in 5 iterations
Solving for Ux, Initial residual = 0.000123, Final residual = 0.000045, No Iterations 3
Solving for Uy, Initial residual = 0.000234, Final residual = 0.000067, No Iterations 4
ExecutionTime = 12.5s
"""
        residuals = ob.parse_residuals(log)
        assert residuals["Ux"] == pytest.approx(0.000045)
        assert residuals["Uy"] == pytest.approx(0.000067)

    def test_parse_residuals_empty(self):
        residuals = ob.parse_residuals("no residuals here")
        assert residuals == {}

    def test_parse_final_time(self):
        log = """
Time = 0
Time = 100
smoothSolver:  Solving for Ux, Initial residual = 1e-5
Time = 500
smoothSolver:  Solving for Ux, Initial residual = 1e-6
ExecutionTime = 45s
"""
        t = ob.parse_final_time(log)
        assert t == 500.0

    def test_parse_final_time_none(self):
        t = ob.parse_final_time("")
        assert t == 0.0

    def test_parse_checkmesh_quality(self):
        log = """
Mesh stats
    cells:           1234567
    points:           2345678
    faces:            9876543
Max aspect ratio = 12.34
"""
        quality = ob.parse_checkmesh_quality(log)
        assert quality["cells"] == 1234567
        assert quality["points"] == 2345678
        assert quality["max_aspect_ratio"] == pytest.approx(12.34)

    def test_parse_checkmesh_quality_minimal(self):
        log = "no mesh stats here"
        quality = ob.parse_checkmesh_quality(log)
        assert quality["cells"] == 0
        assert quality["max_aspect_ratio"] == 0.0


# -------------------------------------------------------------------
# Case structure creation tests (uses subprocess)
# -------------------------------------------------------------------

class TestCaseStructure:
    """Test case directory structure creation (no OpenFOAM required)."""

    HARNESS_ROOT = Path(__file__).parent.parent.parent.parent

    def _run_cli(self, args, check=True):
        env = dict(os.environ)
        env["PYTHONPATH"] = str(self.HARNESS_ROOT)
        result = subprocess.run(
            [sys.executable, "-m", "cli_anything.openfoam"] + args,
            capture_output=True,
            text=True,
            env=env,
            cwd=str(self.HARNESS_ROOT),
        )
        if check and result.returncode != 0:
            print(f"STDERR: {result.stderr}", file=sys.stderr)
        return result.returncode, result.stdout, result.stderr

    def test_case_new_creates_structure(self):
        with tempfile.TemporaryDirectory() as tmp:
            ret, out, err = self._run_cli([
                "--json", "case", "new",
                "--output", str(Path(tmp) / "testCase"),
                "--template", "simpleFoam", "testCase"
            ])
            assert ret == 0, f"stdout={out} stderr={err}"
            case_path = Path(tmp) / "testCase"
            assert (case_path / "system" / "controlDict").exists()
            assert (case_path / "system" / "fvSchemes").exists()
            assert (case_path / "system" / "fvSolution").exists()
            assert (case_path / "constant").exists()
            assert (case_path / "0" / "U").exists()

    def test_case_new_icofoam(self):
        with tempfile.TemporaryDirectory() as tmp:
            ret, out, err = self._run_cli([
                "--json", "case", "new",
                "--output", str(Path(tmp) / "icoCase"),
                "--template", "icoFoam", "icoCase"
            ])
            assert ret == 0
            d = dp.read_dict(Path(tmp) / "icoCase" / "system" / "controlDict")
            assert d.get("application") == "icoFoam"

    def test_case_validate_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._run_cli(["case", "new", "--output", str(Path(tmp) / "c"), "c"])
            ret, out, err = self._run_cli([
                "--json", "--project", str(Path(tmp) / "c"), "case", "validate"
            ])
            assert ret == 0
            data = json.loads(out)
            assert data["status"] == "valid"

    def test_case_validate_missing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "badCase" / "system").mkdir(parents=True)
            ret, out, err = self._run_cli([
                "--json", "--project", str(Path(tmp) / "badCase"), "case", "validate"
            ])
            assert ret == 0
            data = json.loads(out)
            assert data["status"] == "invalid"
            assert len(data["issues"]) > 0

    def test_case_info(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._run_cli(["case", "new", "--output", str(Path(tmp) / "c"), "c"])
            ret, out, err = self._run_cli([
                "--json", "--project", str(Path(tmp) / "c"), "case", "info"
            ])
            assert ret == 0
            data = json.loads(out)
            assert data["solver"] == "simpleFoam"

    def test_setup_boundary_modifies_field(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._run_cli(["case", "new", "--output", str(Path(tmp) / "c"), "c"])
            ret, out, err = self._run_cli([
                "--project", str(Path(tmp) / "c"),
                "setup", "boundary",
                "--patch", "inlet", "--type", "fixedValue",
                "--value", "5 0 0", "--field", "U"
            ])
            assert ret == 0, err
            u_file = Path(tmp) / "c" / "0" / "U"
            data = dp.read_dict(u_file)
            assert "inlet" in data.get("boundaryField", {})

    def test_setup_properties_writes_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._run_cli(["case", "new", "--output", str(Path(tmp) / "c"), "c"])
            ret, out, err = self._run_cli([
                "--project", str(Path(tmp) / "c"),
                "setup", "properties",
                "--turbulence", "kOmegaSST", "--nu", "1e-6"
            ])
            assert ret == 0, err
            turb = dp.read_dict(Path(tmp) / "c" / "constant" / "turbulenceProperties")
            assert turb.get("turbulenceModel") == "kOmegaSST"

    def test_solve_status_with_initial_time(self):
        """Case has '0/' initial directory which is a valid time directory."""
        with tempfile.TemporaryDirectory() as tmp:
            self._run_cli(["case", "new", "--output", str(Path(tmp) / "c"), "c"])
            ret, out, err = self._run_cli([
                "--json", "--project", str(Path(tmp) / "c"), "solve", "status"
            ])
            assert ret == 0
            data = json.loads(out)
            # '0/' directory is parsed as time 0.0 (initial conditions)
            assert data["latest_time"] == 0.0


# -------------------------------------------------------------------
# CLI subprocess tests (requires PYTHONPATH set)
# -------------------------------------------------------------------

class TestCLISubprocess:
    """Test the CLI via subprocess."""

    HARNESS_ROOT = Path(__file__).parent.parent.parent.parent

    def _resolve_cli(self, name):
        import shutil
        force = os.environ.get("CLI_ANYTHING_FORCE_INSTALLED", "").strip() == "1"
        path = shutil.which(name)
        if path:
            return [path]
        if force:
            raise RuntimeError(f"{name} not found in PATH")
        module = name.replace("cli-anything-", "cli_anything.") + "." + name.split("-")[-1] + "_cli"
        return [sys.executable, "-m", module]

    def _run(self, args, check=True):
        env = dict(os.environ)
        env["PYTHONPATH"] = str(self.HARNESS_ROOT)
        base = self._resolve_cli("cli-anything-openfoam")
        return subprocess.run(
            base + args,
            capture_output=True,
            text=True,
            env=env,
            cwd=str(self.HARNESS_ROOT),
            check=check,
        )

    def test_help(self):
        result = self._run(["--help"], check=True)
        assert result.returncode == 0
        assert "OpenFOAM" in result.stdout

    def test_case_new_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self._run([
                "--json", "case", "new",
                "--output", str(Path(tmp) / "cj"), "--template", "simpleFoam", "cj"
            ], check=False)
            assert result.returncode == 0
            data = json.loads(result.stdout)
            assert data["status"] == "success"
            assert data["solver"] == "simpleFoam"

    def test_case_info_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._run(["case", "new", "--output", str(Path(tmp) / "ci"), "ci"], check=True)
            result = self._run([
                "--json", "--project", str(Path(tmp) / "ci"), "case", "info"
            ], check=True)
            assert result.returncode == 0
            data = json.loads(result.stdout)
            assert data["solver"] == "simpleFoam"
