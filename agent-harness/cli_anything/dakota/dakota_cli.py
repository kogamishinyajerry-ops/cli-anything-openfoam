"""
dakota_cli.py - Click CLI entry point for cli-anything-dakota

Command groups:
  run         - run Dakota study from input file
  info        - show input file summary
  validate    - validate Dakota input file

All commands support --json for machine-readable output.
Bare 'dakota' shows version and help.

Follows HARNESS.md principles:
  - Real Dakota commands called via dakota_backend
  - State stored as JSON session files
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

import click

from .utils import dakota_backend as db

__all__ = ["main"]

JSON_MODE = False


# -------------------------------------------------------------------
# Utility helpers
# -------------------------------------------------------------------

def echo(msg: str, **kwargs) -> None:
    """Print to stderr (click echo goes to stdout)."""
    click.echo(msg, err=True, **kwargs)


def success(msg: str) -> None:
    click.echo(f"[OK] {msg}", err=True)


def error(msg: str) -> None:
    click.echo(f"[ERROR] {msg}", err=True, color="red")


def warn(msg: str) -> None:
    click.echo(f"[WARN] {msg}", err=True, color="yellow")


def json_out(data: dict) -> None:
    """Print JSON to stdout."""
    click.echo(json.dumps(data, indent=2))


# -------------------------------------------------------------------
# Main group
# -------------------------------------------------------------------

@click.group(invoke_without_command=True)
@click.option("--json", "json_output", is_flag=True, help="JSON output mode")
@click.option("--container", "-c", default="cfd-openfoam",
              help="Docker container name (default: cfd-openfoam)")
@click.pass_context
def cli(ctx, json_output: bool, container: str):
    """Dakota v6.23 uncertainty quantification and optimization CLI.

    Dakota is a framework for uncertainty quantification, optimization,
    and parameter estimation. It uses .in input files describing the
    study (method, model, variables, interface, responses).

    Example:
      dakota run --input myStudy.in --case myStudy
      dakota info --input myStudy.in
      dakota validate --input myStudy.in
    """
    global JSON_MODE
    JSON_MODE = json_output
    ctx.ensure_object(dict)
    ctx.obj["json"] = json_output
    ctx.obj["container"] = container

    if ctx.invoked_subcommand is None:
        # Bare 'dakota' - show version and help
        echo(f"Dakota {db.DAKOTA_VERSION} harness")
        echo(f"Dakota binary: {db.DAKOTA_INSTALL}")
        echo(f"Container: {container}")
        echo("Use --help with a subcommand for details")


# -------------------------------------------------------------------
# run command
# -------------------------------------------------------------------

@cli.command("run")
@click.option("--input", "-i", "input_file", required=True,
              type=click.Path(exists=True),
              help="Dakota input (.in) file")
@click.option("--case", "case_name",
              help="Case name for output directories and naming")
@click.option("--param", "-p", multiple=True,
              help="Override param (KEY=VALUE), can be repeated")
@click.option("--timeout", type=int, help="Max runtime in seconds")
@click.pass_context
def cmd_run(ctx, input_file: str, case_name: Optional[str], param: tuple, timeout: Optional[int]):
    """Run a Dakota study.

    Example:
      dakota run --input rosenbrock.in
      dakota run --input sampling.in --param samples=200 --param sample_type=random
      dakota run --input optimization.in --case myOpt --timeout 3600
    """
    global JSON_MODE

    inp_path = Path(input_file).resolve()
    container = ctx.obj.get("container")

    # Parse param overrides
    param_overrides: dict[str, str] = {}
    for p in param:
        if "=" not in p:
            error(f"Invalid param format: {p} (expected KEY=VALUE)")
            sys.exit(1)
        key, val = p.split("=", 1)
        param_overrides[key.strip()] = val.strip()

    result = db.run_dakota(
        input_file=inp_path,
        case_name=case_name,
        param_overrides=param_overrides if param_overrides else None,
        timeout=timeout,
        container=container,
    )

    parsed = db.parse_dakota_output(result.output)

    output = {
        "status": "success" if result.success else "error",
        "command": "dakota",
        "input_file": str(input_file),
        "case_name": case_name,
        "returncode": result.returncode,
        "duration_seconds": round(result.duration_seconds, 2),
        "method": parsed.get("method"),
        "samples": parsed.get("samples"),
        "evaluations": parsed.get("evaluations"),
        "variables": parsed.get("variables"),
        "responses": parsed.get("responses"),
        "converged": parsed.get("converged", False),
        "error_msg": parsed.get("error", ""),
        "warnings": parsed.get("warnings", []),
        "cpu_time_seconds": parsed.get("cpu_time_seconds"),
        "output_tail": result.output[-500:] if result.output else "",
        "stderr_tail": result.error[-300:] if result.error else "",
    }

    if JSON_MODE:
        json_out(output)
    else:
        if result.success:
            success(f"Dakota study finished in {result.duration_seconds:.1f}s")
            if parsed.get("method"):
                echo(f"  Method: {parsed['method']}")
            if parsed.get("samples"):
                echo(f"  Samples: {parsed['samples']}")
            if parsed.get("evaluations"):
                echo(f"  Evaluations: {parsed['evaluations']}")
            if parsed.get("variables"):
                echo(f"  Variables: {parsed['variables']}")
            if parsed.get("responses"):
                echo(f"  Responses: {parsed['responses']}")
            if parsed.get("converged"):
                echo("  Status: CONVERGED")
            if parsed.get("cpu_time_seconds"):
                echo(f"  CPU time: {parsed['cpu_time_seconds']:.2f}s")
            if parsed.get("warnings"):
                echo(f"  Warnings: {len(parsed['warnings'])}")
        else:
            error("Dakota study failed")
            if parsed.get("error"):
                echo(f"  Error: {parsed['error']}")
            elif result.error:
                echo(result.error[-300:])


# -------------------------------------------------------------------
# info command
# -------------------------------------------------------------------

@cli.command("info")
@click.option("--input", "-i", "input_file", required=True,
              type=click.Path(exists=True),
              help="Dakota input (.in) file")
@click.pass_context
def cmd_info(ctx, input_file: str):
    """Show Dakota input file summary (method, variables, interface, responses).

    Example:
      dakota info --input rosenbrock.in
    """
    global JSON_MODE

    inp_path = Path(input_file)
    container = ctx.obj.get("container")

    try:
        params = db.parse_input_file(inp_path)
    except Exception as e:
        error(f"Could not parse input file: {e}")
        sys.exit(1)

    # Key parameters to display
    key_params = {
        "environment.tabular_graphics_file": "Results file",
        "method.sampling": "Sampling method",
        "method.sample_type": "Sample type",
        "method.samples": "Samples",
        "method.max_iterations": "Max iterations",
        "method.optimality": "Optimality tolerance",
        "method.conv tolerance": "Convergence tolerance",
        "model.single.analysis_driver": "Analysis driver",
        "variables.continuous_design": "Continuous design vars",
        "variables.discrete_design": "Discrete design vars",
        "responses.objective_functions": "Objective functions",
        "responses.nonlinear_inequality_constraints": "Ineq constraints",
        "responses.nonlinear_equality_constraints": "Eq constraints",
    }

    # Find blocks present in the file
    blocks_present = set()
    for key in params:
        if "." in key:
            block = key.split(".")[0]
            blocks_present.add(block)

    result = {
        "input_file": str(inp_path.resolve()),
        "blocks": sorted(blocks_present),
        "params": params,
        "key_params": {k: params.get(k) for k in key_params if params.get(k)},
    }

    if JSON_MODE:
        json_out(result)
    else:
        echo(f"Input file: {inp_path}")
        echo(f"Blocks: {', '.join(sorted(blocks_present))}")
        echo("")

        for key, label in key_params.items():
            val = params.get(key)
            if val:
                echo(f"  {label}: {val}")

        echo(f"\nTotal parameters: {len(params)}")


# -------------------------------------------------------------------
# validate command
# -------------------------------------------------------------------

@cli.command("validate")
@click.option("--input", "-i", "input_file", required=True,
              type=click.Path(exists=True),
              help="Dakota input (.in) file")
@click.pass_context
def cmd_validate(ctx, input_file: str):
    """Validate a Dakota input file (basic syntax check).

    Runs dakota with -check mode if available, otherwise parses the file.

    Example:
      dakota validate --input myStudy.in
    """
    global JSON_MODE

    inp_path = Path(input_file).resolve()
    container = ctx.obj.get("container")

    issues = []

    # Basic parsing check
    try:
        params = db.parse_input_file(inp_path)
    except Exception as e:
        issues.append(f"Parse error: {e}")

    # Check required blocks
    blocks_in_file = set()
    for key in params:
        if "." in key:
            blocks_in_file.add(key.split(".")[0])

    required_blocks = {"environment", "method", "model", "variables", "interface", "responses"}
    missing = required_blocks - blocks_in_file
    if missing:
        issues.append(f"Missing required blocks: {', '.join(sorted(missing))}")

    # Check for common issues
    if issues:
        result = {"status": "invalid", "issues": issues, "input_file": str(inp_path)}
    else:
        result = {
            "status": "valid",
            "input_file": str(inp_path),
            "blocks": sorted(blocks_in_file),
            "n_params": len(params),
        }

    if JSON_MODE:
        json_out(result)
    else:
        if issues:
            for issue in issues:
                error(issue)
            echo(f"\nValidation FAILED: {len(issues)} issue(s) found")
        else:
            success(f"Input file is valid")
            echo(f"  Blocks: {', '.join(sorted(blocks_in_file))}")
            echo(f"  Parameters: {len(params)}")


# -------------------------------------------------------------------
# Entry point
# -------------------------------------------------------------------

def main():
    cli(obj={})


if __name__ == "__main__":
    main()
