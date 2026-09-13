"""Score RepoTwin evaluation results and generate category-wise reports."""

import csv
import json
import re
from pathlib import Path

from metrics import aggregate, prepare_for_aggregation
from scoring import score_answer, retrieval_metrics


BASE_DIR = Path(__file__).resolve().parent
RESULTS_DIR = BASE_DIR / "results"

RAW_FILE = RESULTS_DIR / "raw_results.json"
GROUND_TRUTH_FILE = BASE_DIR / "ground_truth.json"

SCORED_FILE = RESULTS_DIR / "scored_results.json"
SUMMARY_FILE = RESULTS_DIR / "summary.json"
CATEGORY_FILE = RESULTS_DIR / "category_results.json"
CSV_FILE = RESULTS_DIR / "category_results.csv"


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as f:
        json.dump(
            data,
            f,
            indent=2,
            ensure_ascii=False,
        )


def detect_hallucination(
    answer: str,
    expected_files: list[str],
    retrieved_files: list[str],
) -> dict:

    answer = answer or ""

    referenced_files = set(
        re.findall(
            r"(?:[\w.-]+/)+[\w.-]+\.py",
            answer,
        )
    )

    allowed = set(expected_files) | set(
        retrieved_files
    )

    unsupported = sorted(
        file
        for file in referenced_files
        if file not in allowed
    )

    return {
        "hallucination_flag": bool(
            unsupported
        ),
        "unsupported_files": unsupported,
    }


def main():

    if not RAW_FILE.exists():
        raise FileNotFoundError(
            f"Missing {RAW_FILE}. "
            "Run evaluator.py first."
        )

    if not GROUND_TRUTH_FILE.exists():
        raise FileNotFoundError(
            f"Missing {GROUND_TRUTH_FILE}"
        )

    raw_results = load_json(RAW_FILE)
    ground_truth = load_json(
        GROUND_TRUTH_FILE
    )

    # Normalize evaluator output to its results list.
    # evaluator.py stores:
    # {
    #     "metadata": {...},
    #     "results": [...]
    # }
    if isinstance(raw_results, dict):
        if "results" in raw_results:
            raw_results = raw_results["results"]
        else:
            raw_results = list(raw_results.values())

    # Ground truth is keyed by question ID.
    if isinstance(ground_truth, list):
        ground_truth = {
            item["question_id"]: item
            for item in ground_truth
        }

    scored_results = []

    for row in raw_results:

        question_id = row.get(
            "question_id"
        )

        # Support either qid or question_id.
        if not question_id:
            question_id = row.get("qid")

        truth = ground_truth.get(
            question_id,
            {},
        )

        # evaluator.py stores the ground-truth expectations
        # directly inside every result under "expected".
        # Prefer that when available because it exactly
        # matches the conditions used for that evaluation.
        if not truth or not any(
            truth.get(key)
            for key in (
                "expected_files",
                "expected_entities",
                "must_include",
            )
        ):
            truth = row.get(
                "expected",
                truth,
            ) or {}

        answer = row.get(
            "ai_explanation"
        ) or row.get(
            "answer",
            "",
        )

        expected_files = truth.get(
            "expected_files",
            [],
        )

        expected_entities = truth.get(
            "expected_entities",
            [],
        )

        must_include = truth.get(
            "must_include",
            [],
        )

        retrieval_data = row.get(
            "retrieval",
            {},
        ) or {}

        retrieved_files = retrieval_data.get(
            "retrieved_files",
            row.get("retrieved_files", []),
        )

        retrieved_entities = retrieval_data.get(
            "retrieved_entities",
            row.get("retrieved_entities", []),
        )

        score = score_answer(
            answer=answer,
            ground_truth=truth,
        )

        retrieval = retrieval_metrics(
            expected_files=expected_files,
            retrieved_files=retrieved_files,
            expected_entities=expected_entities,
            retrieved_entities=retrieved_entities,
        )

        hallucination = detect_hallucination(
            answer=answer,
            expected_files=expected_files,
            retrieved_files=retrieved_files,
        )

        result = dict(row)

        result["question_id"] = question_id

        result["ground_truth"] = {
            "expected_files": expected_files,
            "expected_entities": expected_entities,
            "must_include": must_include,
        }

        result["scoring"] = score

        result["retrieval_metrics"] = retrieval

        result["hallucination"] = hallucination

        scored_results.append(result)

    save_json(
        SCORED_FILE,
        scored_results,
    )

    prepared = prepare_for_aggregation(
        scored_results
    )

    summary_rows = aggregate(
        prepared
    )

    save_json(
        CATEGORY_FILE,
        summary_rows,
    )

    # Overall summary by model.
    model_groups = {}

    for row in summary_rows:

        model = row["model"]

        model_groups.setdefault(
            model,
            [],
        ).append(row)

    model_summary = []

    for model, rows in sorted(
        model_groups.items()
    ):

        total_evals = sum(
            r["evaluations"]
            for r in rows
        )

        weighted_accuracy = (
            sum(
                r["accuracy_percent"]
                * r["evaluations"]
                for r in rows
            )
            / total_evals
            if total_evals
            else 0
        )

        weighted_hallucination = (
            sum(
                r["hallucination_rate_percent"]
                * r["evaluations"]
                for r in rows
            )
            / total_evals
            if total_evals
            else 0
        )

        model_summary.append(
            {
                "model": model,
                "evaluations": total_evals,
                "accuracy_percent": round(
                    weighted_accuracy,
                    2,
                ),
                "hallucination_rate_percent": round(
                    weighted_hallucination,
                    2,
                ),
            }
        )

    summary = {
        "total_results": len(
            scored_results
        ),
        "successful_results": sum(
            1
            for r in scored_results
            if r.get("status") == "success"
        ),
        "models": model_summary,
        "category_results": summary_rows,
    }

    save_json(
        SUMMARY_FILE,
        summary,
    )

    # CSV for Excel / Power BI.
    if summary_rows:

        fields = list(
            summary_rows[0].keys()
        )

        with CSV_FILE.open(
            "w",
            newline="",
            encoding="utf-8",
        ) as f:

            writer = csv.DictWriter(
                f,
                fieldnames=fields,
            )

            writer.writeheader()
            writer.writerows(
                summary_rows
            )

    print()
    print("=" * 70)
    print("REPO TWIN EVALUATION ANALYSIS")
    print("=" * 70)

    print(
        f"Total results: {len(scored_results)}"
    )

    print(
        "Successful results:",
        sum(
            1
            for r in scored_results
            if r.get("status") == "success"
        ),
    )

    print()
    print(
        "CATEGORY-WISE MODEL PERFORMANCE"
    )
    print("-" * 70)

    categories = sorted(
        {
            r["category"]
            for r in summary_rows
        }
    )

    modes = [
        "rag",
        "non_rag",
    ]

    for category in categories:

        print()
        print(f"[{category}]")

        for mode in modes:

            rows = [
                r
                for r in summary_rows
                if r["category"] == category
                and r["mode"] == mode
            ]

            if not rows:
                continue

            rows.sort(
                key=lambda x: (
                    x["accuracy_percent"],
                    x["avg_file_recall"],
                    -x["avg_latency_seconds"],
                ),
                reverse=True,
            )

            for rank, row in enumerate(
                rows,
                start=1,
            ):

                print(
                    f"{rank}. "
                    f"{row['model']} | "
                    f"Accuracy: "
                    f"{row['accuracy_percent']:.2f}% | "
                    f"Coverage: "
                    f"{row['avg_must_include_coverage']:.2%} | "
                    f"Latency: "
                    f"{row['avg_latency_seconds']:.2f}s | "
                    f"Hallucination: "
                    f"{row['hallucination_rate_percent']:.2f}%"
                )

    print()
    print("=" * 70)
    print("FILES GENERATED")
    print("=" * 70)

    print(SCORED_FILE)
    print(SUMMARY_FILE)
    print(CATEGORY_FILE)
    print(CSV_FILE)


if __name__ == "__main__":
    main()
