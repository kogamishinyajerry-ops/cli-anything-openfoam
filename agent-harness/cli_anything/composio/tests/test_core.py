"""
test_core.py - Unit tests for cli-anything-composio

Tests Composio backend and CLI with synthetic data.
No real Composio installation required.

Run:
  cd cli-anything-openfoam/agent-harness
  COMPOSIO_MOCK=1 python -m pytest cli_anything/composio/tests/test_core.py -v
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from cli_anything.composio.utils import composio_backend as cb


# -------------------------------------------------------------------
# Test: CommandResult dataclass
# -------------------------------------------------------------------

class TestCommandResult:
    def test_fields(self):
        r = cb.CommandResult(success=True, output="test", returncode=0)
        assert r.success is True
        assert r.output == "test"
        assert r.returncode == 0

    def test_failure(self):
        r = cb.CommandResult(success=False, error="err", returncode=1)
        assert r.success is False
        assert r.returncode == 1
        assert r.error == "err"


# -------------------------------------------------------------------
# Test: Tool categories
# -------------------------------------------------------------------

class TestToolCategories:
    def test_categories_exist(self):
        expected = ["browser", "code", "communication", "productivity", "database", "file", "web", "ml"]
        for c in expected:
            assert c in cb.TOOL_CATEGORIES, f"Missing category: {c}"

    def test_category_structure(self):
        for name, info in cb.TOOL_CATEGORIES.items():
            assert "description" in info
            assert "examples" in info


# -------------------------------------------------------------------
# Test: Tool operations (mock)
# -------------------------------------------------------------------

class TestToolsMock:
    def test_list_tools_mock(self, monkeypatch):
        monkeypatch.setenv("COMPOSIO_MOCK", "1")
        result = cb.list_tools()
        assert result["success"] is True
        assert len(result["tools"]) > 0
        assert result["tools"][0]["name"] == "github"

    def test_list_tools_by_category_mock(self, monkeypatch):
        monkeypatch.setenv("COMPOSIO_MOCK", "1")
        result = cb.list_tools(category="code")
        assert result["success"] is True
        for tool in result["tools"]:
            assert tool["category"] == "code"

    def test_add_tool_mock(self, monkeypatch):
        monkeypatch.setenv("COMPOSIO_MOCK", "1")
        result = cb.add_tool("github")
        assert result.success is True

    def test_remove_tool_mock(self, monkeypatch):
        monkeypatch.setenv("COMPOSIO_MOCK", "1")
        result = cb.remove_tool("github")
        assert result.success is True

    def test_get_tool_mock(self, monkeypatch):
        monkeypatch.setenv("COMPOSIO_MOCK", "1")
        result = cb.get_tool("github")
        assert result["success"] is True
        assert result["tool"] == "github"
        assert result["category"] == "code"

    def test_get_tool_unknown_mock(self, monkeypatch):
        monkeypatch.setenv("COMPOSIO_MOCK", "1")
        result = cb.get_tool("nonexistent_tool_xyz")
        assert result["success"] is False


# -------------------------------------------------------------------
# Test: Action operations (mock)
# -------------------------------------------------------------------

class TestActionsMock:
    def test_list_actions_mock(self, monkeypatch):
        monkeypatch.setenv("COMPOSIO_MOCK", "1")
        result = cb.list_actions()
        assert result["success"] is True
        assert len(result["actions"]) > 0

    def test_list_actions_by_tool_mock(self, monkeypatch):
        monkeypatch.setenv("COMPOSIO_MOCK", "1")
        result = cb.list_actions(tool="github")
        assert result["success"] is True
        for action in result["actions"]:
            assert action["tool"] == "github"

    def test_execute_action_mock(self, monkeypatch):
        monkeypatch.setenv("COMPOSIO_MOCK", "1")
        result = cb.execute_action("github_create_issue", {"title": "Bug"})
        assert result["success"] is True
        assert result["action"] == "github_create_issue"
        assert result["result"]["mock"] is True


# -------------------------------------------------------------------
# Test: Agent operations (mock)
# -------------------------------------------------------------------

class TestAgentsMock:
    def test_list_agents_mock(self, monkeypatch):
        monkeypatch.setenv("COMPOSIO_MOCK", "1")
        result = cb.list_agents()
        assert result["success"] is True
        assert len(result["agents"]) > 0
        assert result["agents"][0]["name"] == "default"

    def test_init_project_mock(self, monkeypatch):
        monkeypatch.setenv("COMPOSIO_MOCK", "1")
        result = cb.init_project("/tmp/test_project")
        assert result.success is True


# -------------------------------------------------------------------
# Test: Auth operations (mock)
# -------------------------------------------------------------------

class TestAuthMock:
    def test_login_mock(self, monkeypatch):
        monkeypatch.setenv("COMPOSIO_MOCK", "1")
        result = cb.login()
        assert result.success is True

    def test_logout_mock(self, monkeypatch):
        monkeypatch.setenv("COMPOSIO_MOCK", "1")
        result = cb.logout()
        assert result.success is True

    def test_whoami_mock(self, monkeypatch):
        monkeypatch.setenv("COMPOSIO_MOCK", "1")
        result = cb.whoami()
        assert result["success"] is True
        assert result["user"]["email"] == "user@example.com"
        assert result["user"]["plan"] == "free"


# -------------------------------------------------------------------
# Test: CLI module import
# -------------------------------------------------------------------

class TestCLIModule:
    def test_cli_module_imports(self):
        from cli_anything.composio import composio_cli
        assert hasattr(composio_cli, "cli")
        assert hasattr(composio_cli, "main")

    def test_backend_module_imports(self):
        from cli_anything.composio import utils
        assert hasattr(utils, "composio_backend")
        b = utils.composio_backend
        assert hasattr(b, "COMPOSIO_VERSION")
        assert hasattr(b, "list_tools")
        assert hasattr(b, "add_tool")
        assert hasattr(b, "execute_action")
        assert hasattr(b, "TOOL_CATEGORIES")
