"""
ragas_backend.py - RAGAS RAG evaluation CLI wrapper

Wraps RAGAS library for use by the cli-anything harness.

RAGAS is installed via:
  pip install ragas

Principles:
  - Calls real RAGAS evaluate() function
  - Supports multiple LLM backends (OpenAI, Azure, Ollama, etc.)
  - Outputs evaluation results in structured format
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional


# -------------------------------------------------------------------
# Version
# -------------------------------------------------------------------

RAGAS_VERSION = "1.0.0"


# -------------------------------------------------------------------
# Result dataclass
# -------------------------------------------------------------------

@dataclass
class CommandResult:
    """Result of a RAGAS evaluation execution."""
    success: bool
    output: str = ""
    error: str = ""
    returncode: int = 0
    duration_seconds: float = 0.0


# -------------------------------------------------------------------
# Available metrics
# -------------------------------------------------------------------

RAGAS_METRICS = {
    "faithfulness": {
        "description": "Measures the factual consistency of the generated answer against the given context.",
        "llm_required": True,
    },
    "answer_relevancy": {
        "description": "Measures how relevant the generated answer is to the question.",
        "llm_required": True,
    },
    "context_relevancy": {
        "description": "Measures how relevant the retrieved context is to the question.",
        "llm_required": True,
    },
    "context_precision": {
        "description": "Measures whether all key points from ground truth are in context.",
        "llm_required": True,
    },
    "context_recall": {
        "description": "Measures how much of ground truth is in retrieved context.",
        "llm_required": True,
    },
    "answer_correctness": {
        "description": "Measures correctness of generated answer vs ground truth.",
        "llm_required": True,
    },
    "answer_similarity": {
        "description": "Measures semantic similarity between answer and ground truth.",
        "llm_required": True,
    },
}


# -------------------------------------------------------------------
# LLM configuration
# -------------------------------------------------------------------

def get_llm_config(provider: str = "openai", **kwargs) -> dict:
    """
    Get LLM configuration for RAGAS.

    Args:
        provider: 'openai', 'azure', 'ollama', 'anthropic'
        **kwargs: Provider-specific config (api_key, model, etc.)

    Returns:
        dict with LLM configuration
    """
    configs = {
        "openai": {
            "llm": {
                "model": kwargs.get("model", "gpt-4o"),
                "api_key": kwargs.get("api_key", os.environ.get("OPENAI_API_KEY", "")),
            }
        },
        "azure": {
            "llm": {
                "name": kwargs.get("model", "gpt-4o"),
                "api_key": kwargs.get("api_key", os.environ.get("AZURE_OPENAI_API_KEY", "")),
                "api_base": kwargs.get("api_base", os.environ.get("AZURE_OPENAI_API_BASE", "")),
                "api_version": kwargs.get("api_version", "2024-02-01"),
            }
        },
        "ollama": {
            "llm": {
                "model": kwargs.get("model", "llama2"),
                "base_url": kwargs.get("base_url", "http://localhost:11434"),
            }
        },
        "anthropic": {
            "llm": {
                "model": kwargs.get("model", "claude-3-sonnet-20240229"),
                "api_key": kwargs.get("api_key", os.environ.get("ANTHROPIC_API_KEY", "")),
            }
        },
    }

    return configs.get(provider, configs["openai"])


def init_llm(provider: str = "openai", **kwargs):
    """
    Initialize an LLM for RAGAS evaluation.

    Returns:
        LLM instance or None if RAGAS not installed
    """
    try:
        from ragas.llms import llm_factory
        config = get_llm_config(provider, **kwargs)

        if provider == "openai":
            return llm_factory("gpt-4o", api_key=config["llm"]["api_key"])
        elif provider == "azure":
            from ragas.llms import AzureOpenAI
            return AzureOpenAI(
                name=config["llm"]["name"],
                api_key=config["llm"]["api_key"],
                api_base=config["llm"]["api_base"],
                api_version=config["llm"]["api_version"],
            )
        elif provider == "ollama":
            return llm_factory(config["llm"]["model"], base_url=config["llm"]["base_url"])
        elif provider == "anthropic":
            from ragas.llms import AnthropicLLM
            return AnthropicLLM(
                model=config["llm"]["model"],
                api_key=config["llm"]["api_key"],
            )
    except ImportError:
        return None


def init_embedder(provider: str = "openai", **kwargs):
    """
    Initialize an embedding model for RAGAS.

    Returns:
        Embedder instance or None if RAGAS not installed
    """
    try:
        from ragas.embeddings import embedding_factory
        config = get_llm_config(provider, **kwargs)

        if provider == "openai":
            return embedding_factory("text-embedding-3-small", api_key=config["llm"]["api_key"])
        elif provider == "ollama":
            return embedding_factory(config["llm"]["model"], base_url=config["llm"]["base_url"])
    except ImportError:
        return None


# -------------------------------------------------------------------
# Dataset loading
# -------------------------------------------------------------------

def load_dataset_from_json(file_path: str) -> list[dict]:
    """
    Load evaluation dataset from JSON file.

    Expected format:
    [
        {
            "user_input": "question text",
            "retrieved_contexts": ["context1", "context2"],
            "response": "generated answer",
            "reference": "ground truth answer"
        },
        ...
    ]

    Returns:
        list of dict samples
    """
    path = Path(file_path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"Dataset file not found: {path}")

    with open(path) as f:
        data = json.load(f)

    if isinstance(data, dict):
        data = data.get("samples", data.get("data", [data]))

    return data


def load_dataset_from_csv(file_path: str) -> list[dict]:
    """
    Load evaluation dataset from CSV file.

    Expected columns: user_input, retrieved_contexts, response, reference
    """
    import csv
    path = Path(file_path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"Dataset file not found: {path}")

    samples = []
    with open(path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Parse retrieved_contexts from JSON string
            if "retrieved_contexts" in row and isinstance(row["retrieved_contexts"], str):
                try:
                    row["retrieved_contexts"] = json.loads(row["retrieved_contexts"])
                except json.JSONDecodeError:
                    row["retrieved_contexts"] = [row["retrieved_contexts"]]
            samples.append(row)

    return samples


# -------------------------------------------------------------------
# Evaluation
# -------------------------------------------------------------------

def evaluate_dataset(
    samples: list[dict],
    metrics: list[str],
    llm_provider: str = "openai",
    embedder_provider: str = "openai",
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    api_base: Optional[str] = None,
    output_file: Optional[str] = None,
    **kwargs,
) -> dict:
    """
    Evaluate a RAG dataset with specified metrics.

    Args:
        samples: List of evaluation samples
        metrics: List of metric names to compute
        llm_provider: LLM provider ('openai', 'azure', 'ollama', 'anthropic')
        embedder_provider: Embedder provider
        api_key: API key (or set via env var)
        model: Model name
        api_base: API base URL (for Azure/Ollama)
        output_file: Optional file to write results JSON
        **kwargs: Additional provider-specific args

    Returns:
        dict with evaluation results
    """
    start = time.time()
    result_data = {
        "success": False,
        "n_samples": len(samples),
        "metrics_requested": metrics,
        "scores": {},
        "error": "",
    }

    # Mock mode for testing without RAGAS installed
    if os.environ.get("RAGAS_MOCK"):
        scores = {}
        for m in metrics:
            if m not in RAGAS_METRICS:
                continue
            scores[m] = {
                "mean": round(0.75 + (hash(m) % 20) / 100, 4),
                "scores": [round(0.7 + (hash(f"{m}{i}") % 30) / 100, 4) for i in range(len(samples))],
            }

        result_data.update({
            "success": True,
            "scores": scores,
            "duration_seconds": time.time() - start,
        })

        if output_file:
            with open(output_file, "w") as f:
                json.dump(result_data, f, indent=2)

        return result_data

    try:
        import pandas as pd
        from datasets import Dataset

        # Convert to HuggingFace Dataset
        df = pd.DataFrame(samples)

        # Ensure proper column names for RAGAS
        column_mapping = {
            "question": "user_input",
            "ground_truth": "reference",
            "answer": "response",
            "contexts": "retrieved_contexts",
        }
        df = df.rename(columns=column_mapping)

        # Filter to only known columns
        known_cols = ["user_input", "retrieved_contexts", "response", "reference"]
        df = df[[c for c in known_cols if c in df.columns]]

        dataset = Dataset.from_pandas(df)

        # Import RAGAS
        from ragas import evaluate
        from ragas.metrics import (
            faithfulness,
            answer_relevancy,
            context_relevancy,
            context_precision,
            context_recall,
            answer_correctness,
            answer_similarity,
        )

        metric_map = {
            "faithfulness": faithfulness,
            "answer_relevancy": answer_relevancy,
            "context_relevancy": context_relevancy,
            "context_precision": context_precision,
            "context_recall": context_recall,
            "answer_correctness": answer_correctness,
            "answer_similarity": answer_similarity,
        }

        selected_metrics = [metric_map[m] for m in metrics if m in metric_map]

        if not selected_metrics:
            result_data["error"] = f"No valid metrics. Available: {list(metric_map.keys())}"
            return result_data

        # Configure LLM
        if llm_provider == "openai":
            from ragas.llms import llm_factory
            llm = llm_factory(
                model or "gpt-4o",
                api_key=api_key or os.environ.get("OPENAI_API_KEY", ""),
            )
        elif llm_provider == "azure":
            from ragas.llms import AzureOpenAI
            llm = AzureOpenAI(
                name=model or "gpt-4o",
                api_key=api_key or os.environ.get("AZURE_OPENAI_API_KEY", ""),
                api_base=api_base or os.environ.get("AZURE_OPENAI_API_BASE", ""),
                api_version="2024-02-01",
            )
        elif llm_provider == "ollama":
            from ragas.llms import llm_factory
            llm = llm_factory(
                model or "llama2",
                base_url=api_base or "http://localhost:11434",
            )
        else:
            llm = None

        if embedder_provider == "openai":
            from ragas.embeddings import embedding_factory
            embedder = embedding_factory(
                "text-embedding-3-small",
                api_key=api_key or os.environ.get("OPENAI_API_KEY", ""),
            )
        elif embedder_provider == "ollama":
            from ragas.embeddings import embedding_factory
            embedder = embedding_factory(
                model or "nomic-embed-text",
                base_url=api_base or "http://localhost:11434",
            )
        else:
            embedder = None

        # Run evaluation
        result = evaluate(
            dataset,
            metrics=selected_metrics,
            llm=llm,
            embeddings=embedder,
        )

        # Extract scores
        scores = {}
        result_df = result.to_pandas()

        for col in result_df.columns:
            for m in selected_metrics:
                metric_name = getattr(m, "name", str(m))
                if metric_name in col or col.replace("ragas_", "") == metric_name.replace("ragas_", ""):
                    scores[metric_name] = {
                        "mean": float(result_df[col].mean()),
                        "scores": [float(x) for x in result_df[col].tolist()],
                    }

        result_data.update({
            "success": True,
            "scores": scores,
            "duration_seconds": time.time() - start,
        })

        if output_file:
            with open(output_file, "w") as f:
                json.dump(result_data, f, indent=2)

        return result_data

    except ImportError as e:
        result_data["error"] = f"RAGAS not installed: {str(e)}"
        return result_data
    except Exception as e:
        result_data["error"] = str(e)
        return result_data


# -------------------------------------------------------------------
# Quick evaluation helpers
# -------------------------------------------------------------------

def evaluate_from_json(
    json_file: str,
    metrics: list[str],
    llm_provider: str = "openai",
    output_file: Optional[str] = None,
    **kwargs,
) -> dict:
    """
    Evaluate a dataset from JSON file.
    """
    samples = load_dataset_from_json(json_file)
    return evaluate_dataset(
        samples=samples,
        metrics=metrics,
        llm_provider=llm_provider,
        output_file=output_file,
        **kwargs,
    )


def evaluate_from_csv(
    csv_file: str,
    metrics: list[str],
    llm_provider: str = "openai",
    output_file: Optional[str] = None,
    **kwargs,
) -> dict:
    """
    Evaluate a dataset from CSV file.
    """
    samples = load_dataset_from_csv(csv_file)
    return evaluate_dataset(
        samples=samples,
        metrics=metrics,
        llm_provider=llm_provider,
        output_file=output_file,
        **kwargs,
    )


# -------------------------------------------------------------------
# Format conversion
# -------------------------------------------------------------------

def export_results_csv(results: dict, output_file: str) -> CommandResult:
    """
    Export evaluation results to CSV.
    """
    try:
        import csv

        scores = results.get("scores", {})
        if not scores:
            return CommandResult(success=False, error="No scores to export", returncode=1)

        rows = []
        for metric_name, metric_data in scores.items():
            mean = metric_data.get("mean", 0)
            sample_scores = metric_data.get("scores", [])

            for i, score in enumerate(sample_scores):
                rows.append({
                    "sample_id": i,
                    "metric": metric_name,
                    "score": score,
                })

            rows.append({
                "sample_id": "mean",
                "metric": metric_name,
                "score": mean,
            })

        with open(output_file, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["sample_id", "metric", "score"])
            writer.writeheader()
            writer.writerows(rows)

        return CommandResult(
            success=True,
            output=f"Exported {len(rows)} rows to {output_file}",
            returncode=0,
        )

    except Exception as e:
        return CommandResult(success=False, error=str(e), returncode=1)
