"""
test_core.py - Unit tests for cli-anything-godot

Tests Godot backend with synthetic data.
No real Godot installation required.

Run:
  cd cli-anything-openfoam/agent-harness
  GODOT_MOCK=1 python -m pytest cli_anything/godot/tests/test_core.py -v
"""

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from cli_anything.godot.utils import godot_backend as gb


# -------------------------------------------------------------------
# Test: CommandResult dataclass
# -------------------------------------------------------------------

class TestCommandResult:
    def test_fields(self):
        r = gb.CommandResult(success=True, output="test", returncode=0)
        assert r.success is True
        assert r.output == "test"
        assert r.returncode == 0

    def test_failure(self):
        r = gb.CommandResult(success=False, error="err", returncode=1)
        assert r.success is False
        assert r.returncode == 1
        assert r.error == "err"


# -------------------------------------------------------------------
# Test: find_godot with mock
# -------------------------------------------------------------------

class TestFindGodot:
    def test_find_godot_mock(self, monkeypatch):
        monkeypatch.setenv("GODOT_MOCK", "1")
        path = gb.find_godot()
        assert path == Path("/usr/bin/true")


# -------------------------------------------------------------------
# Test: Version
# -------------------------------------------------------------------

class TestVersion:
    def test_get_version_mock(self, monkeypatch):
        monkeypatch.setenv("GODOT_MOCK", "1")
        info = gb.get_version()
        assert info["success"] is True
        assert info["version"] == "4.2.2"
        assert info["version_major"] == 4


# -------------------------------------------------------------------
# Test: Project operations (mock)
# -------------------------------------------------------------------

class TestProjectMock:
    def test_new_project_mock(self, monkeypatch, tmp_path):
        monkeypatch.setenv("GODOT_MOCK", "1")
        proj_path = str(tmp_path / "testgame")
        result = gb.new_project(proj_path, project_name="TestGame")
        assert result.success is True
        # Check project.godot was created
        assert (Path(proj_path) / "project.godot").exists()

    def test_new_project_creates_files(self, monkeypatch, tmp_path):
        monkeypatch.setenv("GODOT_MOCK", "1")
        proj_path = str(tmp_path / "myproject")
        gb.new_project(proj_path)
        assert (Path(proj_path) / "project.godot").exists()
        assert (Path(proj_path) / "main.tscn").exists()

    def test_clean_project_mock(self, monkeypatch, tmp_path):
        monkeypatch.setenv("GODOT_MOCK", "1")
        proj_path = str(tmp_path / "cleanme")
        gb.new_project(proj_path)
        result = gb.clean_project(proj_path)
        assert result.success is True


# -------------------------------------------------------------------
# Test: Script generation
# -------------------------------------------------------------------

class TestScriptGeneration:
    def test_generate_basic_node(self, tmp_path):
        out = str(tmp_path / "test_script.gd")
        result = gb.generate_script("basic_node", output_path=out)
        assert result["success"] is True
        assert "extends Node2D" in result["content"]
        assert Path(out).exists()

    def test_generate_character_controller(self, tmp_path):
        out = str(tmp_path / "char.gd")
        result = gb.generate_script("character_controller", output_path=out)
        assert result["success"] is True
        assert "CharacterBody2D" in result["content"]
        assert "SPEED" in result["content"]

    def test_generate_state_machine(self, tmp_path):
        out = str(tmp_path / "state.gd")
        result = gb.generate_script("state_machine", output_path=out)
        assert result["success"] is True
        assert "state_changed" in result["content"]

    def test_generate_unknown_type(self):
        result = gb.generate_script("nonexistent_type")
        assert result["success"] is False

    def test_list_script_types(self):
        result = gb.list_script_types()
        assert result["success"] is True
        assert "basic_node" in result["types"]
        assert "character_controller" in result["types"]
        assert "state_machine" in result["types"]


# -------------------------------------------------------------------
# Test: Export presets parsing
# -------------------------------------------------------------------

class TestExportPresets:
    def test_list_presets(self, tmp_path):
        # Create a mock project with presets
        proj = tmp_path / "testproj"
        proj.mkdir()
        project_file = proj / "project.godot"
        project_file.write_text("""
[preset_0]
name="Linux/X11"
Runnable=true

[preset_1]
name="Windows Desktop"
Runnable=true

[preset_2]
name="Web"
Runnable=false
""")
        result = gb.list_export_presets(str(proj))
        assert result["success"] is True
        presets = result["presets"]
        assert len(presets) == 3
        assert presets[0]["name"] == "Linux/X11"
        assert presets[0]["runnable"] is True
        assert presets[2]["runnable"] is False


# -------------------------------------------------------------------
# Test: Script execution (mock)
# -------------------------------------------------------------------

class TestScriptExecution:
    def test_run_script_mock(self, monkeypatch, tmp_path):
        monkeypatch.setenv("GODOT_MOCK", "1")
        script = tmp_path / "test.gd"
        script.write_text("# test")
        result = gb.run_script(str(script), project_path=str(tmp_path))
        assert result.success is True

    def test_run_script_missing(self, monkeypatch):
        monkeypatch.setenv("GODOT_MOCK", "1")
        result = gb.run_script("/nonexistent/script.gd")
        assert result.success is False
        assert "not found" in result.error.lower()


# -------------------------------------------------------------------
# Test: Run scene (mock)
# -------------------------------------------------------------------

class TestRunScene:
    def test_run_scene_mock(self, monkeypatch, tmp_path):
        monkeypatch.setenv("GODOT_MOCK", "1")
        scene = tmp_path / "main.tscn"
        scene.write_text('[gd_scene format=3]\n')
        result = gb.run_scene(str(scene), project_path=str(tmp_path))
        assert result.success is True

    def test_run_scene_missing(self, monkeypatch):
        monkeypatch.delenv("GODOT_MOCK", raising=False)
        result = gb.run_scene("/nonexistent/main.tscn")
        assert result.success is False


# -------------------------------------------------------------------
# Test: Export project (mock)
# -------------------------------------------------------------------

class TestExport:
    def test_export_project_mock(self, monkeypatch, tmp_path):
        monkeypatch.setenv("GODOT_MOCK", "1")
        result = gb.export_project("linux", project_path=str(tmp_path))
        assert result.success is True

    def test_export_project_with_output_mock(self, monkeypatch, tmp_path):
        monkeypatch.setenv("GODOT_MOCK", "1")
        result = gb.export_project("web", output_path=str(tmp_path / "build"), project_path=str(tmp_path))
        assert result.success is True


# -------------------------------------------------------------------
# Test: CLI module import
# -------------------------------------------------------------------

class TestCLIModule:
    def test_cli_module_imports(self):
        from cli_anything.godot import godot_cli
        assert hasattr(godot_cli, "cli")
        assert hasattr(godot_cli, "main")

    def test_backend_module_imports(self):
        from cli_anything.godot import utils
        assert hasattr(utils, "godot_backend")
        b = utils.godot_backend
        assert hasattr(b, "GODOT_VERSION")
        assert hasattr(b, "new_project")
        assert hasattr(b, "export_project")
        assert hasattr(b, "run_script")
        assert hasattr(b, "generate_script")
