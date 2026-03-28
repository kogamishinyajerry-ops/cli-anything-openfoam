"""
test_core.py - Unit tests for cli-anything-ink

Tests Ink backend with synthetic data.
No real Inklecate installation required.

Run:
  cd cli-anything-openfoam/agent-harness
  INK_MOCK=1 python -m pytest cli_anything/ink/tests/test_core.py -v
"""

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from cli_anything.ink.utils import ink_backend as ib


# -------------------------------------------------------------------
# Test: CommandResult dataclass
# -------------------------------------------------------------------

class TestCommandResult:
    def test_fields(self):
        r = ib.CommandResult(success=True, output="test", returncode=0)
        assert r.success is True
        assert r.output == "test"
        assert r.returncode == 0

    def test_failure(self):
        r = ib.CommandResult(success=False, error="err", returncode=1)
        assert r.success is False
        assert r.returncode == 1
        assert r.error == "err"


# -------------------------------------------------------------------
# Test: find_inklecate with mock
# -------------------------------------------------------------------

class TestFindInklecate:
    def test_find_inklecate_mock(self, monkeypatch):
        monkeypatch.setenv("INK_MOCK", "1")
        path = ib.find_inklecate()
        assert path == Path("/usr/bin/true")


# -------------------------------------------------------------------
# Test: Version
# -------------------------------------------------------------------

class TestVersion:
    def test_get_version_mock(self, monkeypatch):
        monkeypatch.setenv("INK_MOCK", "1")
        info = ib.get_version()
        assert info["success"] is True
        assert info["version"] == "1.2.0"


# -------------------------------------------------------------------
# Test: Script generation
# -------------------------------------------------------------------

class TestScriptGeneration:
    def test_generate_hello(self, tmp_path):
        out = str(tmp_path / "hello.ink")
        result = ib.generate_script("hello", output_path=out)
        assert result["success"] is True
        assert "Hello, world!" in result["content"]
        assert Path(out).exists()

    def test_generate_choice(self, tmp_path):
        out = str(tmp_path / "choice.ink")
        result = ib.generate_script("choice", output_path=out)
        assert result["success"] is True
        assert "choice" in result["content"].lower() or "Choice" in result["content"]
        assert Path(out).exists()

    def test_generate_branching(self, tmp_path):
        out = str(tmp_path / "branch.ink")
        result = ib.generate_script("branching", output_path=out)
        assert result["success"] is True
        assert "VAR" in result["content"]
        assert Path(out).exists()

    def test_generate_variable(self, tmp_path):
        out = str(tmp_path / "var.ink")
        result = ib.generate_script("variable", output_path=out)
        assert result["success"] is True
        assert "VAR" in result["content"]
        assert "health" in result["content"]
        assert Path(out).exists()

    def test_generate_unknown_type(self):
        result = ib.generate_script("nonexistent")
        assert result["success"] is False

    def test_list_script_types(self):
        result = ib.list_script_types()
        assert result["success"] is True
        assert "hello" in result["types"]
        assert "choice" in result["types"]
        assert "branching" in result["types"]
        assert "variable" in result["types"]


# -------------------------------------------------------------------
# Test: Compile (mock)
# -------------------------------------------------------------------

class TestCompileMock:
    def test_compile_mock(self, monkeypatch, tmp_path):
        monkeypatch.setenv("INK_MOCK", "1")
        ink_path = tmp_path / "story.ink"
        ink_path.write_text("Hello, world!\n== END ==")
        result = ib.compile_ink(str(ink_path))
        assert result.success is True
        json_path = ink_path.with_suffix(".json")
        assert json_path.exists()

    def test_compile_with_output_mock(self, monkeypatch, tmp_path):
        monkeypatch.setenv("INK_MOCK", "1")
        ink_path = tmp_path / "story.ink"
        ink_path.write_text("Test story\n== END ==")
        output_path = tmp_path / "output.json"
        result = ib.compile_ink(str(ink_path), output_path=str(output_path))
        assert result.success is True
        assert output_path.exists()

    def test_compile_missing_file(self, monkeypatch):
        monkeypatch.setenv("INK_MOCK", "1")
        result = ib.compile_ink("/nonexistent/story.ink")
        assert result.success is False
        assert "not found" in result.error.lower()


# -------------------------------------------------------------------
# Test: Stats
# -------------------------------------------------------------------

class TestStats:
    def test_get_stats_mock(self, monkeypatch, tmp_path):
        monkeypatch.setenv("INK_MOCK", "1")
        ink_path = tmp_path / "story.ink"
        ink_path.write_text("Hello\n== END ==")
        info = ib.get_stats(str(ink_path))
        assert info["success"] is True
        assert "stats" in info
        assert info["stats"]["words"] == 150  # mock value

    def test_get_stats_missing(self):
        info = ib.get_stats("/nonexistent/story.ink")
        assert info["success"] is False


# -------------------------------------------------------------------
# Test: Run story
# -------------------------------------------------------------------

class TestRunStory:
    def test_run_story_mock(self, monkeypatch, tmp_path):
        monkeypatch.setenv("INK_MOCK", "1")
        story_path = tmp_path / "story.json"
        story_path.write_text('{"inkVersion": 1}')
        result = ib.run_story(str(story_path))
        assert result.success is True
        assert "Adventurer" in result.output or "choice" in result.output.lower()

    def test_run_story_with_choices_mock(self, monkeypatch, tmp_path):
        monkeypatch.setenv("INK_MOCK", "1")
        story_path = tmp_path / "story.json"
        story_path.write_text('{"inkVersion": 1}')
        result = ib.run_story(str(story_path), choices=[1, 2])
        assert result.success is True

    def test_run_story_missing(self):
        result = ib.run_story("/nonexistent/story.json")
        assert result.success is False


# -------------------------------------------------------------------
# Test: Validate
# -------------------------------------------------------------------

class TestValidate:
    def test_validate_mock(self, monkeypatch, tmp_path):
        monkeypatch.setenv("INK_MOCK", "1")
        ink_path = tmp_path / "story.ink"
        ink_path.write_text("Hello\n== END ==")
        info = ib.validate_ink(str(ink_path))
        assert info["success"] is True
        assert info["valid"] is True

    def test_validate_missing(self):
        info = ib.validate_ink("/nonexistent/story.ink")
        assert info["success"] is False


# -------------------------------------------------------------------
# Test: New script
# -------------------------------------------------------------------

class TestNewScript:
    def test_new_script_mock(self, monkeypatch, tmp_path):
        monkeypatch.setenv("INK_MOCK", "1")
        out = str(tmp_path / "new.ink")
        result = ib.new_script(out, script_type="choice")
        assert result.success is True
        assert Path(out).exists()

    def test_new_script_unknown_type(self, monkeypatch, tmp_path):
        monkeypatch.setenv("INK_MOCK", "1")
        out = str(tmp_path / "new.ink")
        result = ib.new_script(out, script_type="nonexistent")
        assert result.success is False


# -------------------------------------------------------------------
# Test: CLI module import
# -------------------------------------------------------------------

class TestCLIModule:
    def test_cli_module_imports(self):
        from cli_anything.ink import ink_cli
        assert hasattr(ink_cli, "cli")
        assert hasattr(ink_cli, "main")

    def test_backend_module_imports(self):
        from cli_anything.ink import utils
        assert hasattr(utils, "ink_backend")
        b = utils.ink_backend
        assert hasattr(b, "INK_VERSION")
        assert hasattr(b, "compile_ink")
        assert hasattr(b, "run_story")
        assert hasattr(b, "get_stats")
        assert hasattr(b, "generate_script")
        assert hasattr(b, "validate_ink")
        assert hasattr(b, "new_script")
