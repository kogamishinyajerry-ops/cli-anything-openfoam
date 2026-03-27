"""
ragas_cli.py - Click CLI entry point for cli-anything-ragas

Command groups:
  evaluate    - Run RAG evaluation on dataset
  metrics    - List available metrics
  export     - Export results to CSV

All commands support --json for machine-readable output.

Follows HARNESS.md principles:
  - Real RAGAS library calls
  - Supports multiple LLM backends
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

import click

from .utils import ragas_backend as rb

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
    """RAGAS RAG pipeline evaluation CLI — measure quality of retrieval and generation.

    RAGAS provides standardized metrics for evaluating RAG pipelines:
    faithfulness, answer_relevancy, context_relevancy, context_precision,
    context_recall, answer_correctness, answer_similarity.

    Supports OpenAI, Azure OpenAI, Ollama, and Anthropic backends.

    Examples:
      ragas evaluate --file data.json --metrics faithfulness answer_relevancy
      ragas metrics --json
      ragas evaluate --file data.csv --metrics all --output results.json
    """
    global JSON_MODE
    JSON_MODE = json_output
    ctx.ensure_object(dict)
    ctx.obj["json"] = json_output


# ==================================================================
# evaluate command
# ==================================================================

@cli.command("evaluate")
@click.option("--file", "-f", required=True, help="Dataset file (.json or .csv)")
@click.option("--metrics", "-m", multiple=True, required=True,
              help="Metrics to compute (e.g., faithfulness answer_relevancy)")
@click.option("--metrics-all", "metrics_all", is_flag=True,
              help="Use all available metrics")
@click.option("--llm", type=click.Choice(["openai", "azure", "ollama", "anthropic"]),
              default="openai", help="LLM provider")
@click.option("--model", help="Model name (provider-specific)")
@click.option("--api-key", help="API key (or set via env var)")
@click.option("--api-base", help="API base URL (for Azure/Ollama)")
@click.option("--embedder", type=click.Choice(["openai", "ollama"]),
              default="openai", help="Embedding model provider")
@click.option("--output", "-o", help="Output file for results JSON")
@click.option("--csv", "export_csv", help="Also export results to CSV")
def cmd_evaluate(
    file: str,
    metrics: tuple,
    metrics_all: bool,
    llm: str,
    model: Optional[str],
    api_key: Optional[str],
    api_base: Optional[str],
    embedder: str,
    output: Optional[str],
    export_csv: Optional[str],
):
    """Evaluate a RAG dataset with specified metrics."""
    global JSON_MODE

    # Resolve metrics
    if metrics_all:
        metric_list = list(rb.RAGAS_METRICS.keys())
    else:
        metric_list = list(metrics)

    # Determine file type
    file_path = Path(file)
    if not file_path.exists():
        if JSON_MODE:
            json_out({"success": False, "error": f"File not found: {file}"})
        else:
            error(f"File not found: {file}")
        return

    try:
        if file_path.suffix == ".json":
            result = rb.evaluate_from_json(
                json_file=str(file_path),
                metrics=metric_list,
                llm_provider=llm,
                model=model,
                api_key=api_key,
                api_base=api_base,
                embedder_provider=embedder,
                output_file=output,
            )
        elif file_path.suffix == ".csv":
            result = rb.evaluate_from_csv(
                csv_file=str(file_path),
                metrics=metric_list,
                llm_provider=llm,
                model=model,
                api_key=api_key,
                api_base=api_base,
                embedder_provider=embedder,
                output_file=output,
            )
        else:
            if JSON_MODE:
                json_out({"success": False, "error": "Unsupported file format. Use .json or .csv"})
            else:
                error("Unsupported file format. Use .json or .csv")
            return

        if JSON_MODE:
            json_out(result)
        else:
            if result.get("success"):
                success(f"Evaluation complete: {result['n_samples']} samples")
                echo(f"Metrics: {', '.join(metric_list)}")
                echo(f"Duration: {result.get('duration_seconds', 0):.1f}s")
                echo("")

                scores = result.get("scores", {})
                for metric_name, score_data in scores.items():
                    mean = score_data.get("mean", 0)
                    echo(f"  {metric_name:25s} {mean:.4f}")

                if output:
                    echo(f"\nResults saved to: {output}")

                if export_csv:
                    csv_result = rb.export_results_csv(result, export_csv)
                    if csv_result.success:
                        success(f"CSV exported to: {export_csv}")
                    else:
                        warn(f"CSV export failed: {csv_result.error}")
            else:
                error(f"Evaluation failed: {result.get('error', 'unknown error')}")

    except Exception as e:
        if JSON_MODE:
            json_out({"success": False, "error": str(e)})
        else:
            error(f"Evaluation failed: {e}")


# ==================================================================
# metrics command
# ==================================================================

@cli.command("metrics")
@click.option("--metric", "-m", help="Show details for a specific metric")
def cmd_metrics(metric: Optional[str]):
    """List available RAGAS metrics."""
    global JSON_MODE

    if metric:
        if metric in rb.RAGAS_METRICS:
            info = rb.RAGAS_METRICS[metric]
            if JSON_MODE:
                json_out({"metric": metric, **info})
            else:
                echo(f"Metric: {metric}")
                echo(f"  Description: {info['description']}")
                echo(f"  LLM required: {info['llm_required']}")
        else:
            if JSON_MODE:
                json_out({"error": f"Unknown metric: {metric}"})
            else:
                error(f"Unknown metric: {metric}")
    else:
        if JSON_MODE:
            json_out({"metrics": rb.RAGAS_METRICS})
        else:
            echo("Available RAGAS metrics:")
            echo("")
            for name, info in rb.RAGAS_METRICS.items():
                echo(f"  {name}")
                echo(f"    {info['description']}")
                echo("")


# ==================================================================
# export command
# ==================================================================

@cli.command("export")
@click.option("--results", "-r", required=True, help="Results JSON file")
@click.option("--csv", "-c", required=True, help="Output CSV file")
def cmd_export(results: str, csv: str):
    """Export evaluation results JSON to CSV."""
    global JSON_MODE

    results_path = Path(results)
    if not results_path.exists():
        if JSON_MODE:
            json_out({"success": False, "error": f"Results file not found: {results}"})
        else:
            error(f"Results file not found: {results}")
        return

    try:
        with open(results_path) as f:
            results_data = json.load(f)

        export_result = rb.export_results_csv(results_data, csv)

        if JSON_MODE:
            json_out({"success": export_result.success, "file": csv})
        else:
            if export_result.success:
                success(f"Exported to: {csv}")
            else:
                error(f"Export failed: {export_result.error}")

    except Exception as e:
        if JSON_MODE:
            json_out({"success": False, "error": str(e)})
        else:
            error(f"Export failed: {e}")


# ==================================================================
# Entry point
# ==================================================================

def main():
    cli(obj={})


if __name__ == "__main__":
    main()
