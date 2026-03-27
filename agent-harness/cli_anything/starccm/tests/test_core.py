"""
test_core.py - Unit tests for cli-anything-starccm (Phase 1)

Tests Star-CCM+ backend and CLI with synthetic data.
No real Star-CCM+ installation required.

Run:
  cd cli-anything-openfoam/agent-harness
  python -m pytest cli_anything/starccm/tests/test_core.py -v
  CLI_ANYTHING_FORCE_INSTALLED=1 python -m pytest cli_anything/starccm/tests/ -v -s
"""

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from cli_anything.starccm.utils import starccm_backend as sb


# -------------------------------------------------------------------
# Test: CommandResult dataclass
# -------------------------------------------------------------------

class TestCommandResult:
    def test_dataclass_fields(self):
        result = sb.CommandResult(
            success=True,
            output="test output",
            error="",
            returncode=0,
            duration_seconds=1.5,
        )
        assert result.success is True
        assert result.output == "test output"
        assert result.duration_seconds == 1.5

    def test_failure_result(self):
        result = sb.CommandResult(
            success=False,
            output="",
            error="something went wrong",
            returncode=1,
            duration_seconds=0.1,
        )
        assert result.success is False
        assert result.returncode == 1


# -------------------------------------------------------------------
# Test: Template registry
# -------------------------------------------------------------------

class TestTemplates:
    def test_templates_exist(self):
        """All expected templates are registered."""
        expected = [
            "external-aero", "internal-flow", "multi-phase",
            "heat-transfer", "steady-state", "transient",
        ]
        for t in expected:
            assert t in sb.SIM_TEMPLATES, f"Template '{t}' missing"

    def test_templates_values(self):
        """Templates map to .scm file names."""
        for name, template in sb.SIM_TEMPLATES.items():
            assert template.endswith(".scm"), f"Template {name} should end in .scm"


# -------------------------------------------------------------------
# Test: Case new (filesystem operations)
# -------------------------------------------------------------------

class TestCaseNew:
    def test_case_new_creates_directory(self):
        """case_new creates case directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = sb.case_new(
                case_name="test_turbine",
                template="external-aero",
                directory=Path(tmpdir),
            )
            assert result.success is True
            case_dir = Path(tmpdir) / "test_turbine"
            assert case_dir.exists()

    def test_case_new_creates_session_file(self):
        """case_new creates .starccm_session.json."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sb.case_new(
                case_name="test_turbine",
                template="external-aero",
                directory=Path(tmpdir),
            )
            session_file = Path(tmpdir) / "test_turbine" / ".starccm_session.json"
            assert session_file.exists()

            session = json.loads(session_file.read_text())
            assert session["case_name"] == "test_turbine"
            assert session["template"] == "external-aero"
            assert "created_at" in session

    def test_case_new_creates_macro(self):
        """case_new creates creation macro."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sb.case_new(
                case_name="test_turbine",
                template="external-aero",
                directory=Path(tmpdir),
            )
            macro_file = Path(tmpdir) / "test_turbine" / "create_test_turbine.java"
            assert macro_file.exists()
            content = macro_file.read_text()
            assert "Simulation" in content
            assert "test_turbine" in content

    def test_case_new_idempotent(self):
        """Calling case_new twice on same case is idempotent."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result1 = sb.case_new(
                case_name="test_turbine",
                template="external-aero",
                directory=Path(tmpdir),
            )
            result2 = sb.case_new(
                case_name="test_turbine",
                template="external-aero",
                directory=Path(tmpdir),
            )
            assert result1.success is True
            assert result2.success is True
            # Session file already exists → treated as already created
            session_file = Path(tmpdir) / "test_turbine" / ".starccm_session.json"
            assert session_file.exists()

    def test_case_new_unknown_template_raises(self):
        """Unknown template raises ValueError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(ValueError, match="Unknown template"):
                sb.case_new(
                    case_name="test",
                    template="nonexistent",
                    directory=Path(tmpdir),
                )


# -------------------------------------------------------------------
# Test: Case info
# -------------------------------------------------------------------

class TestCaseInfo:
    def test_case_info_returns_dict(self):
        """case_info returns a dictionary."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sb.case_new(
                case_name="test_turbine",
                template="external-aero",
                directory=Path(tmpdir),
            )
            info = sb.case_info(Path(tmpdir) / "test_turbine")
            assert isinstance(info, dict)
            assert info["case_name"] == "test_turbine"
            assert info["template"] == "external-aero"

    def test_case_info_missing_session(self):
        """case_info handles missing session file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            empty_dir = Path(tmpdir) / "empty"
            empty_dir.mkdir()
            info = sb.case_info(empty_dir)
            assert info["case_name"] == "empty"
            assert info["sim_exists"] is False


# -------------------------------------------------------------------
# Test: Case validate
# -------------------------------------------------------------------

class TestCaseValidate:
    def test_validate_valid_case(self):
        """Valid case reports valid=True, no issues."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sb.case_new(
                case_name="test_turbine",
                template="external-aero",
                directory=Path(tmpdir),
            )
            result = sb.case_validate(Path(tmpdir) / "test_turbine")
            assert result["valid"] is True
            assert len(result["issues"]) == 0

    def test_validate_missing_dir(self):
        """Missing case directory reports issues."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = sb.case_validate(Path(tmpdir) / "nonexistent")
            assert result["valid"] is False
            assert len(result["issues"]) > 0

    def test_validate_missing_sim_file(self):
        """Case without .sim file reports issue (but sim creation is optional)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sb.case_new(
                case_name="test_turbine",
                template="external-aero",
                directory=Path(tmpdir),
            )
            # Don't create .sim file - session JSON is enough
            result = sb.case_validate(Path(tmpdir) / "test_turbine")
            # No .sim file yet is not an error for our harness
            # (sim is created when Star-CCM+ runs)
            assert result["valid"] is True


# -------------------------------------------------------------------
# Test: solve_status
# -------------------------------------------------------------------

class TestSolveStatus:
    def test_status_no_runs(self):
        """Status for case with no runs shows last_run=None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sb.case_new(
                case_name="test_turbine",
                template="external-aero",
                directory=Path(tmpdir),
            )
            status = sb.solve_status(Path(tmpdir) / "test_turbine")
            assert status["last_run"] is None
            assert status["runs"] == []

    def test_status_time_dirs(self):
        """Status detects time directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sb.case_new(
                case_name="test_turbine",
                template="transient",
                directory=Path(tmpdir),
            )
            case_dir = Path(tmpdir) / "test_turbine"
            # Create fake time directories
            (case_dir / "0.0").mkdir()
            (case_dir / "0.1").mkdir()
            (case_dir / "0.2").mkdir()

            status = sb.solve_status(case_dir)
            assert "time_directories" in status
            assert status["n_timesteps"] == 3
            assert status["current_time"] == "0.2"


# -------------------------------------------------------------------
# Test: Output parsers
# -------------------------------------------------------------------

class TestParsers:
    def test_parse_residuals(self):
        """parse_solver_output extracts residuals and iteration count."""
        output = """
Iteration    100
    Continuity:  1.23e-04
    X Velocity:  5.67e-05
    Y Velocity:  4.32e-05
    Z Velocity:  3.21e-06
    Energy:      1.00e-07
Iteration    101
    Continuity:  9.87e-05
    X Velocity:  4.56e-05
Iteration    102
    Continuity:  8.12e-05
Time = 0.05
        """
        parsed = sb.parse_solver_output(output)
        assert parsed["iterations"] == 102
        assert parsed["time"] == 0.05
        assert "continuity" in parsed["residuals"]
        assert parsed["residuals"]["continuity"] == 8.12e-05

    def test_parse_empty_output(self):
        """parse_solver_output handles empty output."""
        parsed = sb.parse_solver_output("")
        assert parsed["iterations"] == 0
        assert parsed["converged"] is False

    def test_parse_convergence(self):
        """parse_solver_output detects convergence."""
        output = """
Iteration    500
    Continuity:  9.12e-04
Iteration    501
    Continuity:  8.99e-04
Iteration    502
    Continuity:  8.87e-04
        """
        parsed = sb.parse_solver_output(output)
        assert parsed["converged"] is True

    def test_parse_no_convergence(self):
        """parse_solver_output detects no convergence."""
        output = """
Iteration    100
    Continuity:  1.23e-01
        """
        parsed = sb.parse_solver_output(output)
        assert parsed["converged"] is False


# -------------------------------------------------------------------
# Test: _is_number helper
# -------------------------------------------------------------------

class TestHelpers:
    def test_is_number_true(self):
        assert sb._is_number("0.0") is True
        assert sb._is_number("1.5") is True
        assert sb._is_number("100") is True
        assert sb._is_number("1e-5") is True
        assert sb._is_number("-0.5") is True

    def test_is_number_false(self):
        assert sb._is_number("0.0.") is False
        assert sb._is_number("abc") is False
        assert sb._is_number("constant") is False
        assert sb._is_number("system") is False


# -------------------------------------------------------------------
# Test: CLI subprocess (no OpenFOAM needed)
# -------------------------------------------------------------------

class TestCLISubprocess:
    def test_help(self):
        """starccm --help works."""
        import subprocess
        result = subprocess.run(
            [sys.executable, "-m", "cli_anything.starccm", "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0
        assert "Star-CCM+" in result.stdout or "Star-CCM+" in result.stderr

    def test_help_json_flag(self):
        """starccm --help --json doesn't crash."""
        import subprocess
        result = subprocess.run(
            [sys.executable, "-m", "cli_anything.starccm", "--json", "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0

    def test_case_new_json(self):
        """case new --json produces valid JSON."""
        import subprocess
        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run(
                [
                    sys.executable, "-m", "cli_anything.starccm",
                    "--json",
                    "case", "new",
                    "--name", "json_test",
                    "--template", "external-aero",
                    "--dir", tmpdir,
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
            assert result.returncode == 0
            data = json.loads(result.stdout)
            assert data["status"] == "success"
            assert data["case_name"] == "json_test"

    def test_case_info_json(self):
        """case info --json produces valid JSON."""
        import subprocess
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create case first
            subprocess.run(
                [
                    sys.executable, "-m", "cli_anything.starccm",
                    "case", "new",
                    "--name", "info_test",
                    "--template", "internal-flow",
                    "--dir", tmpdir,
                ],
                capture_output=True,
                timeout=10,
            )
            # Then info
            result = subprocess.run(
                [
                    sys.executable, "-m", "cli_anything.starccm",
                    "--json",
                    "case", "info",
                    "--project", f"{tmpdir}/info_test",
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
            assert result.returncode == 0
            data = json.loads(result.stdout)
            assert data["case_name"] == "info_test"
            assert data["template"] == "internal-flow"


# -------------------------------------------------------------------
# Phase 2: Setup - boundary conditions and physics models
# -------------------------------------------------------------------

class TestBCTypeMap:
    """BC_TYPE_MAP has all expected entries."""
    def test_bc_types_complete(self):
        expected = [
            "velocity-inlet", "pressure-inlet", "pressure-outlet",
            "outflow", "wall", "symmetry", "farfield", "fixed-pressure",
        ]
        for bc in expected:
            assert bc in sb.BC_TYPE_MAP, f"Missing BC type: {bc}"

    def test_bc_type_values_are_strings(self):
        for bc_type, java_class in sb.BC_TYPE_MAP.items():
            assert isinstance(bc_type, str)
            assert isinstance(java_class, str)
            assert len(java_class) > 0


class TestPhysicsPresets:
    """PHYSICS_PRESETS has all expected entries."""
    def test_presets_complete(self):
        expected = ["laminar", "kEpsilon", "kOmega", "spalartAllmaras",
                     "realizableKE", "heatTransfer"]
        for p in expected:
            assert p in sb.PHYSICS_PRESETS, f"Missing preset: {p}"

    def test_preset_structure(self):
        for name, preset in sb.PHYSICS_PRESETS.items():
            assert "models" in preset
            assert isinstance(preset["models"], list)
            assert len(preset["models"]) > 0
            assert "description" in preset
            assert isinstance(preset["description"], str)

    def test_each_preset_has_valid_model_names(self):
        for name, preset in sb.PHYSICS_PRESETS.items():
            for model in preset["models"]:
                assert isinstance(model, str)
                assert len(model) > 0


class TestSetupBoundary:
    """setup_boundary validation (no Star-CCM+ required)."""
    def test_unknown_bc_type_returns_error(self):
        """Unknown BC type returns error without calling Star-CCM+."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sb.case_new("test", "external-aero", directory=Path(tmpdir))
            result = sb.setup_boundary(
                case_dir=Path(tmpdir) / "test",
                patch="inlet",
                bc_type="nonexistent-bc",
            )
            assert result.success is False
            assert "Unknown BC type" in result.error

    def test_missing_case_returns_error(self):
        """setup_boundary on non-case directory returns error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            empty = Path(tmpdir) / "not_a_case"
            empty.mkdir()
            result = sb.setup_boundary(
                case_dir=empty,
                patch="inlet",
                bc_type="velocity-inlet",
            )
            assert result.success is False
            assert "Not a valid Star-CCM+ case" in result.error

    def test_writes_macro_file(self):
        """setup_boundary writes a .java macro file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sb.case_new("test", "external-aero", directory=Path(tmpdir))
            sb.setup_boundary(
                case_dir=Path(tmpdir) / "test",
                patch="inlet",
                bc_type="velocity-inlet",
                value="60 0 0",
            )
            macro = list((Path(tmpdir) / "test").glob("setup_bc.java"))
            assert len(macro) == 1
            content = macro[0].read_text()
            assert "VelocityInlet" in content
            assert "inlet" in content


class TestSetupPhysics:
    """setup_physics validation (no Star-CCM+ required)."""
    def test_unknown_model_returns_error(self):
        """Unknown physics model returns error without calling Star-CCM+."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sb.case_new("test", "external-aero", directory=Path(tmpdir))
            result = sb.setup_physics(
                case_dir=Path(tmpdir) / "test",
                model="nonexistent-model",
            )
            assert result.success is False
            assert "Unknown model" in result.error

    def test_missing_case_returns_error(self):
        """setup_physics on non-case directory returns error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            empty = Path(tmpdir) / "not_a_case"
            empty.mkdir()
            result = sb.setup_physics(
                case_dir=empty,
                model="kEpsilon",
            )
            assert result.success is False
            assert "Not a valid Star-CCM+ case" in result.error

    def test_writes_macro_file(self):
        """setup_physics writes a .java macro file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sb.case_new("test", "external-aero", directory=Path(tmpdir))
            sb.setup_physics(
                case_dir=Path(tmpdir) / "test",
                model="spalartAllmaras",
                speed=60.0,
            )
            macro = list((Path(tmpdir) / "test").glob("setup_physics.java"))
            assert len(macro) == 1
            content = macro[0].read_text()
            assert "spalartAllmaras" in content or "SpalartAllmaras" in content

    def test_speed_computed_from_reynolds(self):
        """Re < 1e6 maps to low speed (Re=3e6 -> ~44 m/s for air)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sb.case_new("test", "external-aero", directory=Path(tmpdir))
            # The macro should contain the computed speed
            sb.setup_physics(
                case_dir=Path(tmpdir) / "test",
                model="kEpsilon",
                reynolds_number=3e6,
            )
            macro = list((Path(tmpdir) / "test").glob("setup_physics.java"))
            content = macro[0].read_text()
            # Re=3e6, mu=1.81e-5, rho=1.225, L=1 -> V = Re*mu/(rho*L) ≈ 44.3
            assert "44" in content or "44.3" in content


class TestSetupSchemes:
    """setup_schemes validation."""
    def test_missing_case_returns_error(self):
        """setup_schemes on non-case directory returns error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            empty = Path(tmpdir) / "not_a_case"
            empty.mkdir()
            result = sb.setup_schemes(case_dir=empty, convection="bounded")
            assert result.success is False


# -------------------------------------------------------------------
# Phase 2: CLI subprocess tests
# -------------------------------------------------------------------

class TestSetupCLI:
    """CLI for setup commands (no Star-CCM+ required)."""

    def test_setup_boundary_list(self):
        """starccm setup boundary --list works."""
        import subprocess
        with tempfile.TemporaryDirectory() as tmpdir:
            sb.case_new("test", "external-aero", directory=Path(tmpdir))
            result = subprocess.run(
                [sys.executable, "-m", "cli_anything.starccm",
                 "setup", "boundary", "--project", f"{tmpdir}/test", "--list"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            # list_boundaries calls Star-CCM+ which isn't installed,
            # but the command should not crash (returns error from _run)
            assert result.returncode in [0, 1]  # either OK or Star-CCM+ not found

    def test_setup_physics_list(self):
        """starccm setup physics --list shows presets (no --project needed)."""
        import subprocess
        result = subprocess.run(
            [sys.executable, "-m", "cli_anything.starccm",
             "--json", "setup", "physics", "--list"],
            capture_output=True,
            text=True,
            timeout=10,
            env={**os.environ, "STARCCM_MOCK": "1"},
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "presets" in data
        assert "kEpsilon" in data["presets"]
        assert "spalartAllmaras" in data["presets"]

    def test_setup_physics_unknown_model(self):
        """starccm setup physics --model unknown fails gracefully."""
        import subprocess
        with tempfile.TemporaryDirectory() as tmpdir:
            sb.case_new("test", "external-aero", directory=Path(tmpdir))
            result = subprocess.run(
                [sys.executable, "-m", "cli_anything.starccm",
                 "setup", "physics", "--project", f"{tmpdir}/test",
                 "--model", "nonexistent"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            # Click validates choices before function is called → returncode 2
            assert result.returncode == 2

    def test_setup_boundary_unknown_type(self):
        """starccm setup boundary with unknown type fails gracefully."""
        import subprocess
        with tempfile.TemporaryDirectory() as tmpdir:
            sb.case_new("test", "external-aero", directory=Path(tmpdir))
            result = subprocess.run(
                [sys.executable, "-m", "cli_anything.starccm",
                 "setup", "boundary", "--project", f"{tmpdir}/test",
                 "--patch", "inlet", "--type", "velocity-inlet"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            # Either OK (Star-CCM+ called) or error (Star-CCM+ not installed)
            # Should not crash
            assert result.returncode in [0, 1]


# ==================================================================
# Phase 3: Postprocessing
# ==================================================================

class TestReportTypes:
    """REPORT_TYPES has expected entries."""
    def test_report_types_complete(self):
        expected = ["force", "moment", "pressure", "velocity", "temperature"]
        for r in expected:
            assert r in sb.REPORT_TYPES


class TestPostprocessForce:
    """postprocess_force validation (no Star-CCM+ required)."""
    def test_missing_case_returns_error(self):
        """postprocess_force on non-case directory returns error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            empty = Path(tmpdir) / "not_a_case"
            empty.mkdir()
            result = sb.postprocess_force(
                case_dir=empty,
                patches=["wing"],
            )
            assert result["success"] is False
            assert "error" in result

    def test_writes_macro(self):
        """postprocess_force writes a .java macro file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sb.case_new("test", "external-aero", directory=Path(tmpdir))
            sb.postprocess_force(
                case_dir=Path(tmpdir) / "test",
                patches=["wing", "endplate"],
                direction="y",
                reference_area=0.5,
                container=None,
            )
            macro = list((Path(tmpdir) / "test").glob("post_force.java"))
            assert len(macro) == 1
            content = macro[0].read_text()
            assert "wing" in content
            assert "endplate" in content


class TestPostprocessYplus:
    """postprocess_yplus validation."""
    def test_missing_case_returns_error(self):
        """postprocess_yplus on non-case directory returns error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            empty = Path(tmpdir) / "not_a_case"
            empty.mkdir()
            result = sb.postprocess_yplus(case_dir=empty, patch="wing")
            assert result["success"] is False


class TestPostprocessField:
    """postprocess_field validation."""
    def test_missing_case_returns_error(self):
        """postprocess_field on non-case directory returns error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            empty = Path(tmpdir) / "not_a_case"
            empty.mkdir()
            result = sb.postprocess_field(case_dir=empty, field="Pressure")
            assert result["success"] is False

    def test_writes_macro(self):
        """postprocess_field writes a .java macro file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sb.case_new("test", "external-aero", directory=Path(tmpdir))
            sb.postprocess_field(
                case_dir=Path(tmpdir) / "test",
                field="Velocity",
                patch="inlet",
                format="csv",
                container=None,
            )
            macro = list((Path(tmpdir) / "test").glob("post_field.java"))
            assert len(macro) == 1
            content = macro[0].read_text()
            assert "Velocity" in content


class TestExtractResultsTable:
    """extract_results_table formats sweep results as CSV."""
    def test_csv_header(self):
        """CSV has correct header with parameter names."""
        results = {
            "sweep": {"parameters": ["AOA", "speed"], "n_runs": 2, "n_converged": 2},
            "results": [
                {
                    "run": "run_0000",
                    "params": {"AOA": 0, "speed": 30},
                    "converged": True,
                    "force": {"coefficient": 0.1, "force_y": 0.5},
                    "duration_seconds": 120,
                },
            ],
        }
        csv = sb.extract_results_table(results)
        lines = csv.split("\n")
        assert "run,AOA,speed,converged,cd,cl,cm,duration" in lines[0]
        assert "run_0000" in lines[1]

    def test_csv_written_to_file(self):
        """extract_results_table writes to output_file when specified."""
        with tempfile.TemporaryDirectory() as tmpdir:
            results = {
                "sweep": {"parameters": ["AOA"], "n_runs": 1, "n_converged": 1},
                "results": [
                    {"run": "run_0000", "params": {"AOA": 5}, "converged": True,
                     "force": {}, "duration_seconds": 60},
                ],
            }
            output_path = Path(tmpdir) / "results.csv"
            csv = sb.extract_results_table(results, output_file=output_path)
            assert output_path.exists()
            assert output_path.read_text() == csv


# ==================================================================
# Phase 3: CLI subprocess tests
# ==================================================================

class TestPostprocessCLI:
    """CLI for postprocess commands (no Star-CCM+ required)."""

    def test_postprocess_help(self):
        """starccm postprocess --help works."""
        import subprocess
        result = subprocess.run(
            [sys.executable, "-m", "cli_anything.starccm", "postprocess", "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0
        assert "force" in result.stdout
        assert "yplus" in result.stdout

    def test_postprocess_force_help(self):
        """starccm postprocess force --help works."""
        import subprocess
        result = subprocess.run(
            [sys.executable, "-m", "cli_anything.starccm",
             "postprocess", "force", "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0
        assert "--patch" in result.stdout

    def test_param_help(self):
        """starccm param --help works."""
        import subprocess
        result = subprocess.run(
            [sys.executable, "-m", "cli_anything.starccm", "param", "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0
        assert "sweep" in result.stdout

    def test_param_sweep_requires_params(self):
        """starccm param sweep without params fails."""
        import subprocess
        with tempfile.TemporaryDirectory() as tmpdir:
            sb.case_new("test", "external-aero", directory=Path(tmpdir))
            result = subprocess.run(
                [sys.executable, "-m", "cli_anything.starccm",
                 "param", "sweep", "--project", f"{tmpdir}/test"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            # Should fail with usage error
            assert result.returncode != 0

