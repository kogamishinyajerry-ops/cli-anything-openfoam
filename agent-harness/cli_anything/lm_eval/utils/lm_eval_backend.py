"""
lm_eval_backend.py - LM Evaluation Harness CLI wrapper

Wraps EleutherAI's lm-evaluation-harness for use by the cli-anything harness.

lm-evaluation-harness is installed via:
  pip install lm-eval

Principles:
  - Calls real lm_eval commands or Python API
  - Software is HARD dependency - error clearly if not found
  - Outputs structured evaluation results
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

LM_EVAL_VERSION = "1.0.0"


# -------------------------------------------------------------------
# Installation detection
# -------------------------------------------------------------------

def find_lm_eval() -> Path:
    """
    Locate lm_eval binary or module.

    Returns Path to lm_eval.
    Raises RuntimeError if not found.
    """
    if os.environ.get("LM_EVAL_MOCK"):
        return Path("/usr/bin/true")

    try:
        result = subprocess.run(
            ["python", "-c", "import lm_eval; print(lm_eval.__file__)"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return Path(result.stdout.strip()).parent
    except Exception:
        pass

    try:
        result = subprocess.run(
            ["lm_eval", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return Path("lm_eval")
    except Exception:
        pass

    raise RuntimeError(
        "lm-evaluation-harness not found.\n"
        "Install with: pip install lm-eval\n"
        "Or set LM_EVAL_PATH env var"
    )


# -------------------------------------------------------------------
# Result dataclass
# -------------------------------------------------------------------

@dataclass
class CommandResult:
    """Result of an lm_eval command execution."""
    success: bool
    output: str = ""
    error: str = ""
    returncode: int = 0
    duration_seconds: float = 0.0


# -------------------------------------------------------------------
# Available tasks
# -------------------------------------------------------------------

LM_EVAL_TASKS = {
    "hellaswag": {"description": "Commonsense reasoning about everyday events", "type": "multiple_choice"},
    "mmlu": {"description": "Massively Multitask Language Understanding", "type": "multiple_choice"},
    "truthful_qa": {"description": "Truthfulness of model answers", "type": "multiple_choice"},
    "gsm8k": {"description": "Grade school math word problems", "type": "generation"},
    "humaneval": {"description": "Python code generation from docstrings", "type": "generative"},
    "mbpp": {"description": "Python code generation from text descriptions", "type": "generative"},
    "arc": {"description": "AI2 Reasoning Challenge (ARC)", "type": "multiple_choice"},
    "boolq": {"description": "Boolean questions from Google searches", "type": "multiple_choice"},
    "copa": {"description": "Choice of plausible alternatives", "type": "multiple_choice"},
    "piqa": {"description": "Physical interaction question answering", "type": "multiple_choice"},
    "race": {"description": "Reading comprehension from RACE dataset", "type": "multiple_choice"},
    "sciq": {"description": "Science multiple choice questions", "type": "multiple_choice"},
    "sst2": {"description": "Sentiment analysis (SST-2)", "type": "multiple_choice"},
    "stsb": {"description": "Semantic textual similarity", "type": "regression"},
    "wnli": {"description": "Winograd Natural Language Inference", "type": "multiple_choice"},
    "openbookqa": {"description": "Open book question answering", "type": "multiple_choice"},
    "triviaqa": {"description": "Trivia question answering", "type": "generation"},
    "nq_open": {"description": "Natural Questions open-domain QA", "type": "generation"},
    "webgpt": {"description": "WebGPT human preference benchmark", "type": "generation"},
    "lsat": {"description": "LSAT logical reasoning", "type": "multiple_choice"},
    "logiqa": {"description": "Logic QA benchmark", "type": "multiple_choice"},
}


# -------------------------------------------------------------------
# Core runner
# -------------------------------------------------------------------

def _run(
    cmd: list[str],
    timeout: Optional[int] = None,
    check: bool = True,
) -> CommandResult:
    """Run lm_eval command."""
    start = time.time()
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
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
# Evaluation
# -------------------------------------------------------------------

def evaluate(
    model: str = "hf",
    model_args: Optional[str] = None,
    tasks: Optional[list[str]] = None,
    task_args: Optional[str] = None,
    num_fewshot: Optional[int] = None,
    batch_size: int = 16,
    limit: Optional[int] = None,
    output_path: Optional[str] = None,
    predict_only: bool = False,
    seed: int = 42,
    timeout: Optional[int] = None,
) -> dict:
    """
    Run LLM evaluation.

    Args:
        model: Model type ('hf', 'openai', 'anthropic', 'llama.cpp', etc.)
        model_args: Model arguments string (e.g. 'pretrained=microsoft/phi-2')
        tasks: List of task names to evaluate
        task_args: Additional task arguments
        num_fewshot: Number of few-shot examples
        batch_size: Batch size
        limit: Limit number of examples per task
        output_path: Path to write results JSON
        predict_only: Only generate predictions, don't score
        seed: Random seed
        timeout: Max seconds

    Returns:
        dict with evaluation results
    """
    if os.environ.get("LM_EVAL_MOCK"):
        return _mock_evaluate(model, model_args, tasks or [], num_fewshot, batch_size, output_path)

    try:
        cmd = ["lm_eval"]

        if model:
            cmd.extend(["--model", model])

        if model_args:
            cmd.extend(["--model_args", model_args])

        if tasks:
            tasks_str = ",".join(tasks)
            cmd.extend(["--tasks", tasks_str])

        if task_args:
            cmd.extend(["--task_args", task_args])

        if num_fewshot is not None:
            cmd.extend(["--num_fewshot", str(num_fewshot)])

        if batch_size:
            cmd.extend(["--batch_size", str(batch_size)])

        if limit is not None:
            cmd.extend(["--limit", str(limit)])

        if output_path:
            cmd.extend(["--output_path", str(output_path)])

        if predict_only:
            cmd.append("--predict_only")

        cmd.extend(["--seed", str(seed)])

        result = _run(cmd, timeout=timeout or 600, check=False)

        results = parse_eval_output(result.output, result.error)

        if output_path:
            results_path = Path(output_path)
            if results_path.exists():
                with open(results_path) as f:
                    file_results = json.load(f)
                    results.update(file_results)

        return results

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "results": {},
        }


def _mock_evaluate(
    model: str,
    model_args: Optional[str],
    tasks: list[str],
    num_fewshot: Optional[int],
    batch_size: int,
    output_path: Optional[str],
) -> dict:
    """Mock evaluation for testing."""
    scores = {}
    for task in tasks:
        hash_val = hash(task) % 100
        base_score = 0.5 + (hash_val % 50) / 100

        scores[task] = {
            "acc": round(base_score, 4),
            "acc_stderr": round(0.05 + (hash_val % 10) / 1000, 4),
        }
        if task in ["hellaswag", "mmlu", "arc"]:
            scores[task]["acc_norm"] = round(base_score - 0.02, 4)
        if task == "truthful_qa":
            scores[task]["mc1"] = round(base_score * 0.9, 4)
            scores[task]["mc2"] = round(base_score * 0.95, 4)
        if task in ["humaneval", "mbpp"]:
            scores[task]["pass@1"] = round(base_score * 0.7, 4)
        if task in ["gsm8k"]:
            scores[task]["exact_match"] = round(base_score * 0.8, 4)

    results = {
        "success": True,
        "model": model,
        "model_args": model_args,
        "tasks": tasks,
        "num_fewshot": num_fewshot,
        "batch_size": batch_size,
        "scores": scores,
        "results": scores,
    }

    if output_path:
        with open(output_path, "w") as f:
            json.dump(results, f, indent=2)

    return results


# -------------------------------------------------------------------
# Parse output
# -------------------------------------------------------------------

def parse_eval_output(stdout: str, stderr: str) -> dict:
    """Parse lm_eval stdout/stderr output."""
    results = {"success": True, "results": {}, "stderr": stderr}

    combined = stdout + "\n" + stderr
    task_scores = {}

    pattern = r"'([a-zA-Z0-9_-]+)':\s*\{([^}]+)\}"
    matches = re.findall(pattern, combined)

    for task_name, score_str in matches:
        score_dict = {}
        for kv in re.findall(r"'([a-zA-Z_]+)':\s*([0-9.e+-]+)", score_str):
            score_dict[kv[0]] = float(kv[1])
        if score_dict:
            task_scores[task_name] = score_dict

    if task_scores:
        results["results"] = task_scores
        results["scores"] = task_scores

    return results


# -------------------------------------------------------------------
# List tasks
# -------------------------------------------------------------------

def list_tasks() -> dict:
    """Get all available evaluation tasks."""
    if os.environ.get("LM_EVAL_MOCK"):
        return {"success": True, "tasks": LM_EVAL_TASKS}

    try:
        result = _run(
            ["lm_eval", "--tasks", "list"],
            timeout=30,
            check=False,
        )

        if result.success and result.output:
            tasks = {}
            for line in result.output.split("\n"):
                line = line.strip()
                if line and not line.startswith("-"):
                    name = line.split()[0] if line.split() else line
                    if name and name != "Available":
                        tasks[name] = {"description": "", "type": "unknown"}

            if tasks:
                return {"success": True, "tasks": tasks}

        return {"success": True, "tasks": LM_EVAL_TASKS}

    except Exception:
        return {"success": True, "tasks": LM_EVAL_TASKS}


def get_task_info(task_name: str) -> dict:
    """Get information about a specific task."""
    if task_name in LM_EVAL_TASKS:
        return {
            "success": True,
            "task": task_name,
            **LM_EVAL_TASKS[task_name],
        }

    if os.environ.get("LM_EVAL_MOCK"):
        return {
            "success": False,
            "error": f"Unknown task: {task_name}",
        }

    return {
        "success": False,
        "error": f"Unknown task: {task_name}",
    }


# -------------------------------------------------------------------
# Model configs
# -------------------------------------------------------------------

MODEL_CONFIGS = {
    "hf": {
        "name": "HuggingFace Transformers",
        "args": "pretrained=model_name",
        "required": ["model_name_or_path"],
    },
    "openai": {
        "name": "OpenAI (via API)",
        "args": "model=gpt-4,api_key=...",
        "required": ["model"],
    },
    "anthropic": {
        "name": "Anthropic (via API)",
        "args": "model=claude-3,api_key=...",
        "required": ["model"],
    },
    "llama.cpp": {
        "name": "LLama.cpp (local)",
        "args": "model=model.gguf",
        "required": ["model_path"],
    },
    "vllm": {
        "name": "vLLM (OpenAI-compatible)",
        "args": "pretrained=model_name,max_model_len=4096",
        "required": ["pretrained"],
    },
}


# -------------------------------------------------------------------
# Result formatting
# -------------------------------------------------------------------

def format_results_table(results: dict) -> str:
    """Format evaluation results as a readable table."""
    lines = []
    lines.append("")
    lines.append(f"{'Task':<30} {'Metric':<20} {'Value':>10}")
    lines.append("-" * 62)

    scores = results.get("scores", {})
    for task_name, metrics in scores.items():
        if isinstance(metrics, dict):
            for metric_name, value in metrics.items():
                if isinstance(value, float):
                    lines.append(f"{task_name:<30} {metric_name:<20} {value:>10.4f}")
                else:
                    lines.append(f"{task_name:<30} {metric_name:<20} {str(value):>10}")
        else:
            lines.append(f"{task_name:<30} {'score':<20} {metrics:>10.4f}")

    lines.append("")
    return "\n".join(lines)
