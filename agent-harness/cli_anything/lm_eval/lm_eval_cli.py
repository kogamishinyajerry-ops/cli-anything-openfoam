"""
lm_eval_cli.py - Click CLI entry point for cli-anything-lm-eval

Command groups:
  evaluate    - Run LLM evaluation on benchmarks
  tasks       - List available benchmark tasks
  models      - List supported model types

All commands support --json for machine-readable output.

Follows HARNESS.md principles:
  - Real lm-evaluation-harness CLI/API calls
  - Standardized result output
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

import click

from .utils import lm_eval_backend as lb

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
    """LM Evaluation Harness CLI — benchmark LLM capabilities across standard tasks.

    Supports 60+ benchmarks including:
    - MMLU, HellaSwag, TruthfulQA, GSM8K, HumanEval, ARC, and more

    Supports multiple model types:
    - HuggingFace Transformers, OpenAI, Anthropic, vLLM, Llama.cpp

    Examples:
      lm-eval evaluate --model hf --model-args "pretrained=microsoft/phi-2" --tasks mmlu hellaswag
      lm-eval tasks --list
      lm-eval evaluate --model openai --model-args "model=gpt-4" --tasks gsm8k --output results.json
    """
    global JSON_MODE
    JSON_MODE = json_output
    ctx.ensure_object(dict)
    ctx.obj["json"] = json_output


# ==================================================================
# evaluate command
# ==================================================================

@cli.command("evaluate")
@click.option("--model", "-m", type=str, default="hf",
              help="Model type (hf, openai, anthropic, llama.cpp, vllm)")
@click.option("--model-args", type=str,
              help="Model arguments (e.g. 'pretrained=microsoft/phi-2')")
@click.option("--tasks", "-t", multiple=True, required=True,
              help="Benchmark tasks (e.g. mmlu hellaswag)")
@click.option("--task-args", type=str, help="Additional task arguments")
@click.option("--num-fewshot", type=int, help="Number of few-shot examples")
@click.option("--batch-size", type=int, default=16, help="Batch size")
@click.option("--limit", type=int, help="Limit examples per task")
@click.option("--output", "-o", type=str, help="Output results JSON file")
@click.option("--predict-only", is_flag=True, help="Only generate predictions")
@click.option("--seed", type=int, default=42, help="Random seed")
def cmd_evaluate(
    model: str,
    model_args: Optional[str],
    tasks: tuple,
    task_args: Optional[str],
    num_fewshot: Optional[int],
    batch_size: int,
    limit: Optional[int],
    output: Optional[str],
    predict_only: bool,
    seed: int,
):
    """Evaluate an LLM on benchmark tasks."""
    global JSON_MODE

    task_list = list(tasks)

    if JSON_MODE:
        result = lb.evaluate(
            model=model,
            model_args=model_args,
            tasks=task_list,
            task_args=task_args,
            num_fewshot=num_fewshot,
            batch_size=batch_size,
            limit=limit,
            output_path=output,
            predict_only=predict_only,
            seed=seed,
        )
        json_out(result)
    else:
        echo(f"Evaluating: model={model}, tasks={', '.join(task_list)}")

        result = lb.evaluate(
            model=model,
            model_args=model_args,
            tasks=task_list,
            task_args=task_args,
            num_fewshot=num_fewshot,
            batch_size=batch_size,
            limit=limit,
            output_path=output,
            predict_only=predict_only,
            seed=seed,
        )

        if result.get("success"):
            success("Evaluation complete")

            if result.get("scores"):
                table = lb.format_results_table(result)
                echo(table)

                # Summary
                n_tasks = len(result.get("tasks", []))
                echo(f"Tasks: {n_tasks}, Model: {result.get('model', model)}")
                if num_fewshot is not None:
                    echo(f"Few-shot: {num_fewshot}")
            else:
                warn("No scores returned")

            if output:
                echo(f"\nResults saved to: {output}")
        else:
            error(f"Evaluation failed: {result.get('error', 'unknown error')}")


# ==================================================================
# tasks command
# ==================================================================

@cli.group("tasks")
def cmd_tasks():
    """List and query available benchmark tasks."""
    pass


@cmd_tasks.command("list")
@click.option("--type", type=str, help="Filter by task type")
def cmd_tasks_list(type: Optional[str]):
    """List all available benchmark tasks."""
    global JSON_MODE

    result = lb.list_tasks()

    if JSON_MODE:
        if type:
            filtered = {
                k: v for k, v in result.get("tasks", {}).items()
                if v.get("type") == type
            }
            json_out({"success": True, "tasks": filtered})
        else:
            json_out(result)
    else:
        tasks = result.get("tasks", {})
        if type:
            tasks = {k: v for k, v in tasks.items() if v.get("type") == type}
            echo(f"Tasks of type '{type}':")
        else:
            echo("Available benchmark tasks:")
            echo("")

        for name, info in sorted(tasks.items()):
            task_type = info.get("type", "unknown")
            desc = info.get("description", "")
            echo(f"  {name:<20} [{task_type}]")
            if desc:
                echo(f"    {desc}")


@cmd_tasks.command("info")
@click.argument("task_name")
def cmd_tasks_info(task_name: str):
    """Show detailed information about a task."""
    global JSON_MODE

    result = lb.get_task_info(task_name)

    if JSON_MODE:
        json_out(result)
    else:
        if result.get("success"):
            echo(f"Task: {task_name}")
            echo(f"  Type: {result.get('type', 'unknown')}")
            echo(f"  Description: {result.get('description', '')}")
        else:
            error(f"Task not found: {task_name}")


# ==================================================================
# models command
# ==================================================================

@cli.group("models")
def cmd_models():
    """List supported model types."""
    pass


@cmd_models.command("list")
def cmd_models_list():
    """List all supported model types."""
    global JSON_MODE

    if JSON_MODE:
        json_out({"models": lb.MODEL_CONFIGS})
    else:
        echo("Supported model types:")
        echo("")
        for model_type, info in lb.MODEL_CONFIGS.items():
            echo(f"  {model_type}")
            echo(f"    Name: {info['name']}")
            echo(f"    Args: {info['args']}")


# ==================================================================
# Entry point
# ==================================================================

def main():
    cli(obj={})


if __name__ == "__main__":
    main()
