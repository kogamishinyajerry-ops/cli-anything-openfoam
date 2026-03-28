"""
promptfoo_cli.py - Click CLI entry point for cli-anything-promptfoo

Command groups:
  eval        - Run prompt evaluation
  config      - Config file operations (init, add-test, list-tests)
  result      - View and export evaluation results
  info        - Version information

All commands support --json for machine-readable output.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

import click

from .utils import promptfoo_backend as pb

__all__ = ["main"]

JSON_MODE = False


# -------------------------------------------------------------------
# Utility helpers
# -------------------------------------------------------------------

def echo(msg: str, **kwargs) -> None:
    click.echo(msg, err=True, **kwargs)


def success(msg: str) -> None:
    click.echo(f"[OK] {msg}", err=True)


def error(msg: str) -> None:
    click.echo(f"[ERROR] {msg}", err=True, color="red")


def warn(msg: str) -> None:
    click.echo(f"[WARN] {msg}", err=True, color="yellow")


def json_out(data: dict) -> None:
    click.echo(json.dumps(data, indent=2))


# -------------------------------------------------------------------
# Main group
# -------------------------------------------------------------------

@click.group(invoke_without_command=True)
@click.option("--json", "json_output", is_flag=True, help="JSON output mode")
@click.pass_context
def cli(ctx, json_output: bool):
    """Promptfoo AI Prompt Evaluation — evaluate and compare LLM prompts from the CLI.

    Promptfoo lets you evaluate prompts against multipleLLMs with assertions,
    generate test datasets, and measure performance.

    Examples:
      promptfoo eval --config promptfoofile.yaml
      promptfoo config init --path ./promptfoofile.yaml
      promptfoo result metrics --result ./output.json
    """
    global JSON_MODE
    JSON_MODE = json_output
    ctx.ensure_object(dict)
    ctx.obj["json"] = json_output

    if ctx.invoked_subcommand is None:
        echo("Promptfoo harness (CLI wrapper)")
        version_info = pb.get_version()
        if version_info.get("success"):
            echo(f"Version: {version_info['version']}")
        else:
            echo("Promptfoo: not found")


# ==================================================================
# info command
# ==================================================================

@cli.group("info")
def cmd_info():
    """Version and settings information."""
    pass


@cmd_info.command("version")
def cmd_version():
    """Show Promptfoo version."""
    global JSON_MODE
    info = pb.get_version()

    if JSON_MODE:
        json_out(info)
    else:
        if info.get("success"):
            echo(f"Promptfoo {info['version']}")
        else:
            error("Failed to get version")
            echo(f"  {info.get('error', '')}")


# ==================================================================
# config command
# ==================================================================

@cli.group("config")
def cmd_config():
    """Config file operations."""
    pass


@cmd_config.command("init")
@click.option("--path", "-p", required=True, help="Config file path")
@click.option("--prompt", "-pr", multiple=True, help="Prompt string (can repeat)")
@click.option("--provider", "-pv", multiple=True, help="Provider ID (can repeat)")
def cmd_init(path: str, prompt: tuple, provider: tuple):
    """Create a new promptfoofile config."""
    global JSON_MODE

    prompts_list = None
    if prompt:
        prompts_list = [{"id": f"prompt{i+1}", "label": f"Prompt {i+1}", "prompt": p} for i, p in enumerate(prompt)]

    providers_list = list(provider) if provider else None

    result = pb.init_config(path, prompts=prompts_list, providers=providers_list)

    if JSON_MODE:
        json_out({"success": result.success, "path": path, "output": result.output})
    else:
        if result.success:
            success(f"Config created: {path}")
        else:
            error("Failed to create config")
            echo(f"  {result.error[:200]}")


@cmd_config.command("add-test")
@click.option("--config", "-c", required=True, help="Config file path")
@click.option("--var", "-v", multiple=True, help="Variable as key=value (can repeat)")
@click.option("--assert-type", "-at", help="Assertion type (e.g. contains)")
@click.option("--assert-value", "-av", help="Assertion expected value")
@click.option("--assert-threshold", "-ath", type=float, help="Assertion threshold")
def cmd_add_test(config: str, var: tuple, assert_type: Optional[str], assert_value: Optional[str], assert_threshold: Optional[float]):
    """Add a test case to config."""
    global JSON_MODE

    vars_dict = {}
    for v in var:
        if "=" in v:
            key, val = v.split("=", 1)
            vars_dict[key.strip()] = val.strip()

    assertions = None
    if assert_type:
        assertion = {"type": assert_type}
        if assert_value:
            assertion["value"] = assert_value
        if assert_threshold is not None:
            assertion["threshold"] = assert_threshold
        assertions = [assertion]

    result = pb.add_test_case(config, vars_dict, assertions=assertions)

    if JSON_MODE:
        json_out({"success": result.success, "output": result.output})
    else:
        if result.success:
            success("Test case added")
        else:
            error("Failed to add test case")
            echo(f"  {result.error[:200]}")


@cmd_config.command("list-tests")
@click.option("--config", "-c", required=True, help="Config file path")
def cmd_list_tests(config: str):
    """List test cases in config."""
    global JSON_MODE

    info = pb.get_test_cases(config)

    if JSON_MODE:
        json_out(info)
    else:
        if info.get("success"):
            echo(f"Test cases: {info.get('count', 0)}")
            for i, test in enumerate(info.get("tests", [])):
                echo(f"  {i+1}. {test}")
        else:
            error("Failed to list tests")
            echo(f"  {info.get('error', '')}")


@cmd_config.command("read")
@click.option("--config", "-c", required=True, help="Config file path")
def cmd_read_config(config: str):
    """Read and display config contents."""
    global JSON_MODE

    info = pb.read_config(config)

    if JSON_MODE:
        json_out(info)
    else:
        if info.get("success"):
            echo(f"Prompts: {len(info.get('prompts', []))}")
            for p in info.get("prompts", []):
                echo(f"  - {p.get('id', '?')}: {p.get('label', '?')}")
            echo(f"Providers: {len(info.get('providers', []))}")
            for p in info.get("providers", []):
                echo(f"  - {p.get('id', '?')}")
            echo(f"Tests: {len(info.get('tests', []))}")
        else:
            error("Failed to read config")
            echo(f"  {info.get('error', '')}")


# ==================================================================
# eval command
# ==================================================================

@cli.group("eval")
def cmd_eval():
    """Run prompt evaluation."""
    pass


@cmd_eval.command("run")
@click.option("--config", "-c", help="Config file path")
@click.option("--output", "-o", help="Results output path (JSON)")
@click.option("--filter", "-f", help="Filter test cases by pattern")
@click.option("--prompt-label", "-pl", multiple=True, help="Run only specific prompts")
@click.option("--provider-label", "-pvl", multiple=True, help="Run only specific providers")
@click.option("--no-cache", is_flag=True, help="Disable caching")
@click.option("--temperature", "-t", type=float, help="Set temperature")
@click.option("--max-concurrency", "-m", type=int, help="Max concurrency")
@click.option("--project", "-p", help="Project name for grouping")
def cmd_run(
    config: Optional[str],
    output: Optional[str],
    filter: Optional[str],
    prompt_label: tuple,
    provider_label: tuple,
    no_cache: bool,
    temperature: Optional[float],
    max_concurrency: Optional[int],
    project: Optional[str],
):
    """Run evaluation."""
    global JSON_MODE

    result = pb.run_eval(
        config_path=config,
        output_path=output,
        filter_pattern=filter,
        prompt_labels=list(prompt_label) if prompt_label else None,
        provider_labels=list(provider_label) if provider_label else None,
        no_cache=no_cache,
        temperature=temperature,
        max_concurrency=max_concurrency,
        project=project,
    )

    if JSON_MODE:
        json_out({"success": result.success, "output": result.output})
    else:
        if result.success:
            success("Evaluation complete")
            if output:
                echo(f"  Results: {output}")
            elif result.output:
                echo(f"  {result.output[:200]}")
        else:
            error("Evaluation failed")
            echo(f"  {result.error[:200]}")


# ==================================================================
# result command
# ==================================================================

@cli.group("result")
def cmd_result():
    """View and export evaluation results."""
    pass


@cmd_result.command("describe")
@click.option("--result", "-r", required=True, help="Results JSON path")
def cmd_describe(result: str):
    """Show summary of evaluation results."""
    global JSON_MODE

    res = pb.describe_result(result)

    if JSON_MODE:
        json_out({"success": res.success, "output": res.output})
    else:
        if res.success:
            echo(res.output)
        else:
            error("Failed to describe results")
            echo(f"  {res.error[:200]}")


@cmd_result.command("metrics")
@click.option("--result", "-r", required=True, help="Results JSON path")
def cmd_metrics(result: str):
    """Extract and show metrics from results."""
    global JSON_MODE

    info = pb.get_metrics(result)

    if JSON_MODE:
        json_out(info)
    else:
        if info.get("success"):
            summary = info.get("summary", {})
            echo(f"Evaluation Metrics")
            echo(f"==================")
            echo(f"Total:    {summary.get('total', 0)}")
            echo(f"Passed:   {summary.get('successes', 0)}")
            echo(f"Failed:   {summary.get('failures', 0)}")
            echo(f"Score:    {summary.get('score', 0):.1f}%")
            echo(f"")
            echo(f"Providers: {len(info.get('providers', []))}")
            for p in info.get("providers", []):
                echo(f"  - {p.get('id', '?')}")
            echo(f"Prompts: {len(info.get('prompts', []))}")
            for p in info.get("prompts", []):
                echo(f"  - {p.get('id', '?')}: {p.get('label', '?')}")
            assertion_stats = info.get("assertion_stats", {})
            if assertion_stats:
                echo(f"")
                echo(f"Assertion Stats:")
                for atype, stats in assertion_stats.items():
                    pct = (stats["passed"] / stats["total"] * 100) if stats["total"] > 0 else 0
                    echo(f"  {atype}: {stats['passed']}/{stats['total']} ({pct:.0f}%)")
        else:
            error("Failed to get metrics")
            echo(f"  {info.get('error', '')}")


@cmd_result.command("export")
@click.option("--result", "-r", required=True, help="Results JSON path")
@click.option("--format", "-f", type=click.Choice(["json", "csv", "table"]), default="json", help="Export format")
@click.option("--output", "-o", help="Output file path")
def cmd_export(result: str, format: str, output: Optional[str]):
    """Export evaluation results."""
    global JSON_MODE

    res = pb.export_results(result, format=format, output_path=output)

    if JSON_MODE:
        json_out({"success": res.success, "output": res.output})
    else:
        if res.success:
            success(f"Exported to {output or 'stdout'}")
            if res.output and not output:
                echo(res.output[:500])
        else:
            error("Export failed")
            echo(f"  {res.error[:200]}")


# ==================================================================
# Entry point
# ==================================================================

def main():
    cli(obj={})


if __name__ == "__main__":
    main()
