"""
promptfoo_backend.py - Promptfoo CLI wrapper

Wraps real Promptfoo commands for use by the cli-anything harness.

Promptfoo is installed via:
  - npm: npm install -g promptfoo
  - Docker: docker pull promptfoo/promptfoo

Principles:
  - MUST call real Promptfoo commands, not reimplement
  - Software is HARD dependency - error clearly if not found
  - Supports headless/remote evaluation
  - Operations via Promptfoo CLI + config files
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional


# -------------------------------------------------------------------
# Version
# -------------------------------------------------------------------

PROMPTFOO_VERSION = "1.0.0"


# -------------------------------------------------------------------
# Installation detection
# -------------------------------------------------------------------

PROMPTFOO_DEFAULT_PATHS = [
    "/usr/local/bin/promptfoo",
    "/usr/bin/promptfoo",
    Path.home() / ".local/bin/promptfoo",
    Path.home() / "node_modules/.bin/promptfoo",
]


def find_promptfoo() -> Path:
    """
    Locate Promptfoo binary.

    Returns Path to promptfoo executable.
    Raises RuntimeError if not found.
    """
    promptfoo_bin = os.environ.get("PROMPTFOO_PATH")

    if not promptfoo_bin:
        for candidate in PROMPTFOO_DEFAULT_PATHS:
            p = Path(candidate)
            if p.exists():
                promptfoo_bin = str(p)
                break

    if not promptfoo_bin:
        try:
            result = subprocess.run(
                ["which", "promptfoo"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0 and result.stdout.strip():
                promptfoo_bin = result.stdout.strip()
        except Exception:
            pass

    if not promptfoo_bin:
        if os.environ.get("PROMPTFOO_MOCK"):
            return Path("/usr/bin/true")
        raise RuntimeError(
            f"Promptfoo not found.\n"
            f"Set PROMPTFOO_PATH env var or install Promptfoo.\n"
            f"npm install -g promptfoo\n"
            f"Docker: docker pull promptfoo/promptfoo"
        )

    bin_path = Path(promptfoo_bin)
    if not bin_path.exists():
        if os.environ.get("PROMPTFOO_MOCK"):
            return Path("/usr/bin/true")
        raise RuntimeError(f"Promptfoo not found at {bin_path}")

    return bin_path


# -------------------------------------------------------------------
# Result dataclass
# -------------------------------------------------------------------

@dataclass
class CommandResult:
    """Result of a Promptfoo command execution."""
    success: bool
    output: str = ""
    error: str = ""
    returncode: int = 0
    duration_seconds: float = 0.0


# -------------------------------------------------------------------
# Core runner
# -------------------------------------------------------------------

def _run(
    cmd: list[str],
    cwd: Optional[Path] = None,
    timeout: Optional[int] = None,
    check: bool = True,
    env_extra: Optional[dict] = None,
) -> CommandResult:
    """
    Run Promptfoo command.

    Args:
        cmd: Command as list of strings
        cwd: Working directory
        timeout: Max seconds (None = no limit)
        check: Raise on non-zero exit
        env_extra: Extra env vars

    Returns:
        CommandResult
    """
    promptfoo = find_promptfoo()

    actual_cmd = [str(promptfoo)] + cmd

    env = os.environ.copy()
    if env_extra:
        env.update(env_extra)

    start = time.time()
    try:
        proc = subprocess.run(
            actual_cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
            env=env,
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
            error=f"Command timed out after {timeout}s",
            returncode=-1,
            duration_seconds=timeout or 0,
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
    """
    Get Promptfoo version information.

    Returns:
        dict with version info
    """
    if os.environ.get("PROMPTFOO_MOCK"):
        return {
            "success": True,
            "version": "0.80.0",
            "latestVersion": "0.80.0",
        }

    result = _run(["--version"], timeout=15, check=False)

    if result.success:
        version_str = result.output.strip()
        return {
            "success": True,
            "version": version_str,
            "latestVersion": version_str,
        }

    return {
        "success": False,
        "error": result.error or "Failed to get version",
    }


# -------------------------------------------------------------------
# Config operations
# -------------------------------------------------------------------

DEFAULT_PROMPTFOO_CONFIG = """prompts:
  - id: prompt1
    label: Default Prompt
    prompt: "{{query}}"

providers:
  - id: openai:chat:gpt-4o-mini
    label: GPT-4o Mini

tests:
  - vars:
      query: "Hello world"
"""

DEFAULT_TEST_CASE = """- vars:
    query: "What is 2+2?"
  assert:
    - type: contains
      value: "4"
"""


def init_config(
    config_path: str,
    prompts: Optional[list] = None,
    providers: Optional[list] = None,
    tests: Optional[list] = None,
) -> CommandResult:
    """
    Create a new promptfoofile config.

    Args:
        config_path: Path to create config file
        prompts: Optional list of prompt configs
        providers: Optional list of provider configs
        tests: Optional list of test configs

    Returns:
        CommandResult
    """
    path = Path(config_path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)

    if os.environ.get("PROMPTFOO_MOCK"):
        path.write_text(DEFAULT_PROMPTFOO_CONFIG)
        return CommandResult(success=True, output=f"Config created at {path}", returncode=0)

    # Build config content
    config_lines = ["prompts:"]

    if prompts:
        for p in prompts:
            if isinstance(p, dict):
                config_lines.append(f"  - id: {p.get('id', 'prompt1')}")
                config_lines.append(f"    label: {p.get('label', 'Prompt')}")
                config_lines.append(f"    prompt: \"{p.get('prompt', '')}\"")
            else:
                config_lines.append(f"  - \"{p}\"")
    else:
        config_lines.append("  - id: prompt1")
        config_lines.append("    label: Default Prompt")
        config_lines.append("    prompt: \"{{query}}\"")

    config_lines.append("\nproviders:")
    if providers:
        for pr in providers:
            config_lines.append(f"  - \"{pr}\"")
    else:
        config_lines.append("  - id: openai:chat:gpt-4o-mini")
        config_lines.append("    label: GPT-4o Mini")

    config_lines.append("\ntests:")
    if tests:
        for t in tests:
            config_lines.append(f"  - {t}")
    else:
        config_lines.append("  - vars:")
        config_lines.append("    query: \"Hello world\"")

    content = "\n".join(config_lines)
    path.write_text(content)

    return CommandResult(
        success=True,
        output=f"Config created at {path}",
        returncode=0,
    )


def read_config(config_path: str) -> dict:
    """
    Read and parse a promptfoofile.

    Returns:
        dict with config contents
    """
    path = Path(config_path)
    if not path.exists():
        return {"success": False, "error": f"Config not found: {config_path}"}

    try:
        content = path.read_text()
        # Simple YAML-like parsing
        prompts = []
        providers = []
        tests = []
        current_section = None

        for line in content.split("\n"):
            stripped = line.strip()
            if stripped == "prompts:":
                current_section = "prompts"
            elif stripped == "providers:":
                current_section = "providers"
            elif stripped == "tests:":
                current_section = "tests"
            elif stripped.startswith("- id:"):
                if current_section == "prompts":
                    parts = stripped[5:].strip().split("label:", 1)
                    prompts.append({"id": parts[0].strip().strip('"')})
            elif stripped.startswith("prompt:"):
                if current_section == "prompts" and prompts:
                    val = stripped[7:].strip().strip('"')
                    prompts[-1]["prompt"] = val
            elif stripped.startswith("label:"):
                if current_section == "prompts" and prompts:
                    prompts[-1]["label"] = stripped[6:].strip().strip('"')
                elif current_section == "providers" and providers:
                    providers[-1]["label"] = stripped[6:].strip().strip('"')
            elif stripped.startswith("- id:"):
                if current_section == "providers":
                    providers.append({"id": stripped[4:].strip().strip('"')})
            elif stripped.startswith("- "):
                if current_section == "tests":
                    tests.append(stripped[2:])

        return {
            "success": True,
            "prompts": prompts,
            "providers": providers,
            "tests": tests,
            "path": str(path),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# -------------------------------------------------------------------
# Evaluation
# -------------------------------------------------------------------

def run_eval(
    config_path: Optional[str] = None,
    output_path: Optional[str] = None,
    filter_pattern: Optional[str] = None,
    prompt_labels: Optional[list] = None,
    provider_labels: Optional[list] = None,
    no_cache: bool = False,
    temperature: Optional[float] = None,
    max_concurrency: Optional[int] = None,
    project: Optional[str] = None,
    timeout: Optional[int] = None,
) -> CommandResult:
    """
    Run promptfoo evaluation.

    Args:
        config_path: Path to promptfoofile
        output_path: Path for results JSON
        filter_pattern: Filter test cases by pattern
        prompt_labels: Only run specific prompts
        provider_labels: Only run specific providers
        no_cache: Disable cache
        temperature: Set temperature
        max_concurrency: Set max concurrency
        project: Project name for grouping
        timeout: Max seconds

    Returns:
        CommandResult
    """
    if os.environ.get("PROMPTFOO_MOCK"):
        # Generate realistic mock output
        mock_result = {
            "results": {
                "version": "0.80.0",
                "timestamp": "2026-03-28T12:00:00Z",
                "providers": [{"id": "openai:chat:gpt-4o-mini", "label": "GPT-4o Mini"}],
                "prompts": [{"id": "prompt1", "label": "Default Prompt"}],
                "tests": [
                    {
                        "vars": {"query": "What is 2+2?"},
                        "response": {"output": "4"},
                        "success": True,
                        "score": 1.0,
                        "gradedAssertions": [],
                    }
                ],
                "summary": {
                    "total": 1,
                    "successes": 1,
                    "failures": 0,
                    "score": 100.0,
                },
            }
        }
        if output_path:
            Path(output_path).write_text(json.dumps(mock_result, indent=2))
        return CommandResult(
            success=True,
            output=json.dumps(mock_result, indent=2),
            returncode=0,
        )

    cmd = ["eval"]

    if config_path:
        cmd.extend(["--config", config_path])

    if output_path:
        cmd.extend(["--output", output_path])
    else:
        # Default output path
        default_output = "promptfoo-output.json"
        cmd.extend(["--output", default_output])

    if filter_pattern:
        cmd.extend(["--filter", filter_pattern])

    if prompt_labels:
        for label in prompt_labels:
            cmd.extend(["--prompt-label", label])

    if provider_labels:
        for label in provider_labels:
            cmd.extend(["--provider-label", label])

    if no_cache:
        cmd.append("--no-cache")

    if temperature is not None:
        cmd.extend(["--temperature", str(temperature)])

    if max_concurrency is not None:
        cmd.extend(["--max-concurrency", str(max_concurrency)])

    if project:
        cmd.extend(["--project", project])

    cwd = Path(config_path).parent if config_path else Path.cwd()
    result = _run(cmd, cwd=cwd, timeout=timeout or 300, check=False)
    return result


def get_eval_results(result_path: str) -> dict:
    """
    Read evaluation results from JSON output.

    Args:
        result_path: Path to results JSON

    Returns:
        dict with parsed results
    """
    path = Path(result_path)
    if not path.exists():
        return {"success": False, "error": f"Results not found: {result_path}"}

    try:
        data = json.loads(path.read_text())
        results = data.get("results", data)

        # Extract summary metrics
        summary = results.get("summary", {})
        tests = results.get("tests", [])

        # Parse per-test metrics
        test_results = []
        for test in tests:
            test_results.append({
                "vars": test.get("vars", {}),
                "success": test.get("success", False),
                "score": test.get("score", 0.0),
                "response": test.get("response", {}),
                "assertions": test.get("gradedAssertions", []),
            })

        return {
            "success": True,
            "version": results.get("version", "unknown"),
            "timestamp": results.get("timestamp", ""),
            "summary": {
                "total": summary.get("total", 0),
                "successes": summary.get("successes", 0),
                "failures": summary.get("failures", 0),
                "score": summary.get("score", 0.0),
            },
            "tests": test_results,
            "providers": results.get("providers", []),
            "prompts": results.get("prompts", []),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def describe_result(result_path: str) -> CommandResult:
    """
    Show summary of evaluation results.

    Args:
        result_path: Path to results JSON

    Returns:
        CommandResult
    """
    if os.environ.get("PROMPTFOO_MOCK"):
        info = get_eval_results(result_path)
        if info.get("success"):
            summary = info["summary"]
            output = f"""Evaluation Summary
==================
Total:   {summary['total']}
Passed:  {summary['successes']}
Failed:  {summary['failures']}
Score:   {summary['score']:.1f}%"""
            return CommandResult(success=True, output=output, returncode=0)
        return CommandResult(success=False, error=info.get("error", ""))

    result = _run(["describe", result_path], timeout=30, check=False)

    if result.success and not result.output:
        # Fallback to parsing JSON
        info = get_eval_results(result_path)
        if info.get("success"):
            summary = info["summary"]
            output = f"""Evaluation Summary
==================
Total:   {summary['total']}
Passed:  {summary['successes']}
Failed:  {summary['failures']}
Score:   {summary['score']:.1f}%"""
            return CommandResult(success=True, output=output, returncode=0)

    return result


# -------------------------------------------------------------------
# Export
# -------------------------------------------------------------------

def export_results(
    result_path: str,
    format: str = "json",
    output_path: Optional[str] = None,
) -> CommandResult:
    """
    Export evaluation results.

    Args:
        result_path: Path to results JSON
        format: 'json', 'csv', or 'table'
        output_path: Optional output file

    Returns:
        CommandResult
    """
    if os.environ.get("PROMPTFOO_MOCK"):
        info = get_eval_results(result_path)
        if not info.get("success"):
            return CommandResult(success=False, error=info.get("error", ""))

        if format == "json":
            content = json.dumps(info, indent=2)
        elif format == "csv":
            lines = ["test,score,success"]
            for test in info.get("tests", []):
                vars_str = str(test.get("vars", {})).replace(",", ";")
                lines.append(f'"{vars_str}",{test.get("score", 0)},{test.get("success", False)}')
            content = "\n".join(lines)
        else:
            content = "Test,Score,Success\n"
            for test in info.get("tests", []):
                vars_str = str(test.get("vars", {})).replace(",", ";")
                content += f'"{vars_str}",{test.get("score", 0)},{test.get("success", False)}\n'

        if output_path:
            Path(output_path).write_text(content)
            return CommandResult(success=True, output=f"Exported to {output_path}", returncode=0)
        return CommandResult(success=True, output=content, returncode=0)

    cmd = ["export", "--input", result_path, "--format", format]
    if output_path:
        cmd.extend(["--out", output_path])

    result = _run(cmd, timeout=30, check=False)
    return result


# -------------------------------------------------------------------
# Config modification helpers
# -------------------------------------------------------------------

def add_test_case(
    config_path: str,
    vars_dict: dict,
    assertions: Optional[list] = None,
) -> CommandResult:
    """
    Add a test case to config.

    Args:
        config_path: Path to promptfoofile
        vars_dict: Variables for the test (e.g. {"query": "What is 2+2?"})
        assertions: Optional list of assertion dicts

    Returns:
        CommandResult
    """
    path = Path(config_path).resolve()
    if not path.exists():
        return CommandResult(success=False, error=f"Config not found: {path}", returncode=1)

    if os.environ.get("PROMPTFOO_MOCK"):
        return CommandResult(success=True, output=f"Test case added to {path}", returncode=0)

    # Read existing content
    content = path.read_text()

    # Build new test entry
    test_lines = ["  - vars:"]
    for key, val in vars_dict.items():
        test_lines.append(f'      {key}: "{val}"')

    if assertions:
        for assertion in assertions:
            if isinstance(assertion, dict):
                test_lines.append("    assert:")
                test_lines.append(f'      - type: {assertion.get("type", "contains")}')
                if "value" in assertion:
                    test_lines.append(f'        value: "{assertion.get("value")}"')
                if "threshold" in assertion:
                    test_lines.append(f'        threshold: {assertion.get("threshold")}')

    # Find last test entry and append
    lines = content.split("\n")
    tests_idx = None
    for i, line in enumerate(lines):
        if line.strip() == "tests:":
            tests_idx = i
            break

    if tests_idx is not None:
        # Find insertion point (after all existing tests)
        insert_idx = tests_idx + 1
        while insert_idx < len(lines) and (lines[insert_idx].startswith("  -") or lines[insert_idx].startswith("    ")):
            insert_idx += 1
        lines.insert(insert_idx, "\n".join(test_lines))
    else:
        lines.extend(["\ntests:"] + test_lines)

    path.write_text("\n".join(lines))
    return CommandResult(success=True, output=f"Test case added to {path}", returncode=0)


def get_test_cases(config_path: str) -> dict:
    """
    List test cases in config.

    Returns:
        dict with test cases list
    """
    info = read_config(config_path)
    if not info.get("success"):
        return info

    tests = info.get("tests", [])
    return {
        "success": True,
        "count": len(tests),
        "tests": tests,
    }


# -------------------------------------------------------------------
# Metrics parsing
# -------------------------------------------------------------------

def get_metrics(result_path: str) -> dict:
    """
    Extract metrics from evaluation results.

    Args:
        result_path: Path to results JSON

    Returns:
        dict with metrics summary
    """
    info = get_eval_results(result_path)
    if not info.get("success"):
        return info

    summary = info.get("summary", {})
    tests = info.get("tests", [])

    # Calculate per-assertion-type stats
    assertion_stats = {}
    for test in tests:
        for assertion in test.get("assertions", []):
            atype = assertion.get("type", "unknown")
            passed = assertion.get("passed", False)
            if atype not in assertion_stats:
                assertion_stats[atype] = {"total": 0, "passed": 0}
            assertion_stats[atype]["total"] += 1
            if passed:
                assertion_stats[atype]["passed"] += 1

    return {
        "success": True,
        "summary": summary,
        "assertion_stats": assertion_stats,
        "providers": info.get("providers", []),
        "prompts": info.get("prompts", []),
    }
