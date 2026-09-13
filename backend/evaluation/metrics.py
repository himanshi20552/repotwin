"""Aggregate metrics for RepoTwin Week 4 evaluation."""

from collections import defaultdict
from statistics import mean, median
from typing import Any


def _avg(rows: list[dict[str, Any]], key: str) -> float:
    values = [
        r[key]
        for r in rows
        if isinstance(r.get(key), (int, float))
    ]

    return round(mean(values), 4) if values else 0.0


def _median(rows: list[dict[str, Any]], key: str) -> float:
    values = [
        r[key]
        for r in rows
        if isinstance(r.get(key), (int, float))
    ]

    return round(median(values), 4) if values else 0.0


def prepare_for_aggregation(
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:

    prepared = []

    for row in rows:

        scoring = row.get(
            "scoring",
            {},
        ) or {}

        retrieval = row.get(
            "retrieval_metrics",
            {},
        ) or {}

        hallucination = row.get(
            "hallucination",
            {},
        ) or {}

        ollama = row.get(
            "ollama",
            {},
        ) or {}

        item = dict(row)

        item["_correctness"] = scoring.get(
            "correctness_score",
            0,
        )

        item["_coverage"] = scoring.get(
            "must_include_coverage",
            0.0,
        )

        item["_file_precision"] = retrieval.get(
            "file_precision",
            0.0,
        )

        item["_file_recall"] = retrieval.get(
            "file_recall",
            0.0,
        )

        item["_entity_precision"] = retrieval.get(
            "entity_precision",
            0.0,
        )

        item["_entity_recall"] = retrieval.get(
            "entity_recall",
            0.0,
        )

        item["_hallucination"] = (
            1
            if hallucination.get(
                "hallucination_flag"
            )
            else 0
        )

        item["prompt_tokens"] = ollama.get(
            "prompt_eval_count"
        )

        item["output_tokens"] = ollama.get(
            "eval_count"
        )

        item["tokens_per_second"] = ollama.get(
            "tokens_per_second"
        )

        code_validation = row.get("code_validation", {}) or {}

        item["code_validation_applicable"] = bool(
            code_validation.get("applicable")
        )
        item["code_validation_passed"] = (
            1
            if code_validation.get("applicable")
            and code_validation.get("passed")
            else 0
            if code_validation.get("applicable")
            else None
        )

        resources = row.get("resources", {}) or {}

        item["resource_cpu_percent"] = resources.get(
            "cpu_percent"
        )
        item["resource_process_cpu_percent"] = resources.get(
            "process_cpu_percent"
        )
        item["resource_memory_mb"] = resources.get(
            "memory_mb"
        )
        item["resource_process_memory_mb"] = resources.get(
            "process_memory_mb"
        )
        item["resource_gpu_memory_mb"] = resources.get(
            "gpu_memory_mb"
        )

        prepared.append(item)

    return prepared


def aggregate(
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:

    groups = defaultdict(list)

    for row in rows:

        key = (
            row.get("model", ""),
            row.get("category", ""),
            row.get("mode", ""),
        )

        groups[key].append(row)

    summary = []

    for (
        model,
        category,
        mode,
    ), group in sorted(groups.items()):

        successful = [
            r
            for r in group
            if r.get("status") == "success"
        ]

        avg_score = _avg(
            successful,
            "_correctness",
        )

        summary.append({

            "model": model,

            "category": category,

            "mode": mode,

            "evaluations": len(group),

            "successful": len(successful),

            "accuracy_percent": round(
                avg_score * 50,
                2,
            ),

            "avg_correctness_score": avg_score,

            "avg_must_include_coverage": _avg(
                successful,
                "_coverage",
            ),

            "avg_file_precision": _avg(
                successful,
                "_file_precision",
            ),

            "avg_file_recall": _avg(
                successful,
                "_file_recall",
            ),

            "avg_entity_precision": _avg(
                successful,
                "_entity_precision",
            ),

            "avg_entity_recall": _avg(
                successful,
                "_entity_recall",
            ),

            "hallucination_rate_percent": round(
                _avg(
                    successful,
                    "_hallucination",
                ) * 100,
                2,
            ),

            "avg_latency_seconds": _avg(
                successful,
                "wall_time_seconds",
            ),

            "median_latency_seconds": _median(
                successful,
                "wall_time_seconds",
            ),

            "avg_prompt_tokens": _avg(
                successful,
                "prompt_tokens",
            ),

            "avg_output_tokens": _avg(
                successful,
                "output_tokens",
            ),

            "avg_tokens_per_second": _avg(
                successful,
                "tokens_per_second",
            ),

            "avg_cpu_percent": _avg(
                successful,
                "resource_cpu_percent",
            ),

            "avg_process_cpu_percent": _avg(
                successful,
                "resource_process_cpu_percent",
            ),

            "avg_memory_mb": _avg(
                successful,
                "resource_memory_mb",
            ),

            "avg_process_memory_mb": _avg(
                successful,
                "resource_process_memory_mb",
            ),

            "avg_gpu_memory_mb": _avg(
                successful,
                "resource_gpu_memory_mb",
            ),

            "code_generation_syntax_pass_rate": _avg(
                [
                    r for r in successful
                    if r.get("code_validation_applicable")
                ],
                "code_validation_passed",
            ),
        })

    return summary
