import json
import sys
import time
from pathlib import Path
from typing import Any

# Allow imports from backend/
BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.graph.unified_graph import build_unified_graph
from app.analysis.evidence import build_evidence_package
from app.services.rag_service import (
    assemble_rag_context,
    get_or_build_vector_store,
)
from app.services.llm_service import analyze_with_ollama
from evaluation.resource_monitor import snapshot
from evaluation.code_validator import validate_generated_code


# ============================================================
# Configuration
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
DATASET_PATH = BASE_DIR / "dataset.json"
GROUND_TRUTH_PATH = BASE_DIR / "ground_truth.json"

REPO_PATH = BACKEND_DIR / "data" / "repos" / "fastapi-real"
RAG_REPO_PATH = BASE_DIR / "rag_corpus"
RAG_REPOSITORY_NAME = "fastapi-evaluation-rag"

RESULTS_DIR = BASE_DIR / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

RAW_RESULTS_PATH = RESULTS_DIR / "raw_results.json"

MODELS = [
    "qwen2.5-coder:1.5b",
    "starcoder2:3b",
    "opencoder:1.5b",
]

MAX_DEPTH = 6
TOP_K_CHUNKS = 5


# ============================================================
# Dataset
# ============================================================

def load_json(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def flatten_dataset(dataset: dict) -> list[dict]:
    questions = []

    categories = dataset.get("categories", dataset)

    for category, items in categories.items():
        if not isinstance(items, list):
            continue

        for item in items:
            row = dict(item)
            row["category"] = category
            questions.append(row)

    return questions


# ============================================================
# Result persistence
# ============================================================

def load_existing_results() -> list[dict]:
    if not RAW_RESULTS_PATH.exists():
        return []

    try:
        data = load_json(RAW_RESULTS_PATH)

        if isinstance(data, dict):
            return data.get("results", [])

        if isinstance(data, list):
            return data

    except Exception as e:
        print(f"Warning: could not load existing results: {e}")

    return []


def save_results(results: list[dict]) -> None:
    payload = {
        "metadata": {
            "repository": "fastapi-real",
            "models": MODELS,
            "max_depth": MAX_DEPTH,
            "top_k_chunks": TOP_K_CHUNKS,
            "question_count": 28,
            "category_count": 7,
            "categories": [
                "Explanation",
                "Code Retrieval",
                "Dependency Understanding",
                "Bug Analysis",
                "Code Generation",
                "Refactoring",
                "RAG based Question",
            ],
        },
        "results": results,
    }

    temp_path = RAW_RESULTS_PATH.with_suffix(".tmp")

    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    temp_path.replace(RAW_RESULTS_PATH)


# ============================================================
# Target resolution
# ============================================================

ENTITY_TARGETS = {
    "APIRouter": [
        "class:fastapi/routing.py:APIRouter",
    ],
    "FastAPI": [
        "class:fastapi/applications.py:FastAPI",
    ],
    "solve_dependencies": [
        "function:fastapi/dependencies/utils.py:solve_dependencies",
    ],
    "get_dependant": [
        "function:fastapi/dependencies/utils.py:get_dependant",
    ],
    "serialize_response": [
        "function:fastapi/routing.py:serialize_response",
    ],
    "add_api_route": [
        "method:fastapi/routing.py:APIRouter.add_api_route",
        "function:fastapi/routing.py:add_api_route",
        "method:add_api_route",
    ],
}



def get_expected_entities(question: dict) -> list[str]:
    expected = question.get("expected_entities", [])

    if isinstance(expected, list):
        return expected

    return []


def resolve_target(question: dict, graph: Any) -> str | None:
    """
    Resolve a graph target from expected entities.

    We prefer an exact entity target instead of using one global
    target for every evaluation question.
    """

    entities = get_expected_entities(question)

    # First try expected entities.
    for entity in entities:
        base_name = entity.split(".")[-1]

        candidates = ENTITY_TARGETS.get(base_name, [])

        for candidate in candidates:
            if graph_has_target(graph, candidate):
                return candidate

    # Fallbacks based on expected file.
    expected_files = question.get("expected_files", [])

    if expected_files:
        file_path = expected_files[0]

        if "routing.py" in file_path:
            for candidate in [
                "class:APIRouter",
                "function:serialize_response",
                "function:add_api_route",
            ]:
                if graph_has_target(graph, candidate):
                    return candidate

        if "applications.py" in file_path:
            if graph_has_target(graph, "class:FastAPI"):
                return "class:FastAPI"

        if "dependencies/utils.py" in file_path:
            if graph_has_target(graph, "function:solve_dependencies"):
                return "function:solve_dependencies"

    return None


def graph_has_target(graph: Any, target_id: str) -> bool:
    """
    Handles the repository graph representation without assuming
    a single graph class API.
    """

    if graph is None:
        return False

    if isinstance(graph, dict):
        if target_id in graph:
            return True

        nodes = graph.get("nodes")

        if isinstance(nodes, dict):
            if target_id in nodes:
                return True

            for node in nodes.values():
                if isinstance(node, dict):
                    if (
                        node.get("id") == target_id
                        or node.get("node_id") == target_id
                        or node.get("name") == target_id
                    ):
                        return True

                    # Handle serialized node objects where the
                    # identifier may appear in another string field.
                    if any(
                        value == target_id
                        for value in node.values()
                        if isinstance(value, str)
                    ):
                        return True

        if isinstance(nodes, list):
            for node in nodes:
                # Some graph representations store node IDs directly.
                if isinstance(node, str) and node == target_id:
                    return True

                if isinstance(node, dict):
                    if (
                        node.get("id") == target_id
                        or node.get("node_id") == target_id
                        or node.get("name") == target_id
                    ):
                        return True

                    # Unified graph may serialize the identifier under
                    # another string-valued field.
                    if any(
                        value == target_id
                        for value in node.values()
                        if isinstance(value, str)
                    ):
                        return True

    # NetworkX-like object
    try:
        if target_id in graph.nodes:
            return True
    except Exception:
        pass

    return False


# ============================================================
# Repository context
# ============================================================

def build_question_context(
    question: dict,
    graph: Any,
) -> tuple[dict | None, dict | None]:

    target_id = resolve_target(question, graph)

    if not target_id:
        print(
            f"  WARNING: Could not resolve target for {question['id']}"
        )
        return None, None

    try:
        evidence_package = build_evidence_package(
            graph,
            target_id,
            max_depth=MAX_DEPTH,
        )

        context = assemble_rag_context(
            evidence_package=evidence_package,
            query=question["question"],
            repository_path=str(RAG_REPO_PATH),
            repository_name=RAG_REPOSITORY_NAME,
            top_k_chunks=TOP_K_CHUNKS,
        )

        return evidence_package, context

    except TypeError:
        # Compatibility fallback for different function signatures.
        try:
            evidence_package = build_evidence_package(
                graph,
                target_id,
                MAX_DEPTH,
            )

            context = assemble_rag_context(
                evidence_package,
                question["question"],
                str(RAG_REPO_PATH),
                RAG_REPOSITORY_NAME,
                TOP_K_CHUNKS,
            )

            return evidence_package, context

        except Exception as e:
            print(
                f"  WARNING: Context construction failed for "
                f"{question['id']}: {e}"
            )
            return None, None

    except Exception as e:
        print(
            f"  WARNING: Context construction failed for "
            f"{question['id']}: {e}"
        )
        return None, None


# ============================================================
# Ollama evaluation
# ============================================================

def calculate_tokens_per_second(metadata: dict) -> float | None:
    eval_count = metadata.get("eval_count")
    eval_duration_ns = metadata.get("eval_duration_ns")

    if not eval_count or not eval_duration_ns:
        return None

    duration_seconds = eval_duration_ns / 1_000_000_000

    if duration_seconds <= 0:
        return None

    return round(eval_count / duration_seconds, 2)


def run_model(
    question: dict,
    context: dict,
    model: str,
    use_rag: bool,
) -> dict:

    start = time.perf_counter()
    resource_before = snapshot()

    try:
        response = analyze_with_ollama(
            context,
            model=model,
            use_rag=use_rag,
        )

        wall_time = time.perf_counter() - start
        resource_after = snapshot()

        # analyze_with_ollama returns the raw model explanation
        # separately from RepoTwin's deterministic answer.
        ai_explanation = response.get("ai_explanation", "")

        code_validation = validate_generated_code(
            ai_explanation
        )

        metadata = response.get("ollama_metadata") or {}

        return {
            "status": "success",

            "question_id": question["id"],
            "category": question["category"],
            "model": model,
            "mode": "RAG" if use_rag else "Non-RAG",

            "target": context.get("target"),

            "answer": response.get("answer", ""),
            "ai_explanation": ai_explanation,

            "code_validation": code_validation,

            "validation": response.get("validation"),

            "ollama_available": response.get(
                "ollama_available",
                False,
            ),

            "wall_time_seconds": round(wall_time, 3),

            "resources": {
                "before": resource_before,
                "after": resource_after,
                "cpu_percent": resource_after.get("cpu_percent"),
                "process_cpu_percent": resource_after.get(
                    "process_cpu_percent"
                ),
                "memory_mb": resource_after.get("memory_mb"),
                "process_memory_mb": resource_after.get(
                    "process_memory_mb"
                ),
                "gpu_memory_mb": resource_after.get(
                    "gpu_memory_mb"
                ),
            },

            "ollama": {
                "model": metadata.get("model"),
                "prompt_eval_count": metadata.get(
                    "prompt_eval_count"
                ),
                "eval_count": metadata.get("eval_count"),
                "load_duration_ns": metadata.get(
                    "load_duration_ns"
                ),
                "prompt_eval_duration_ns": metadata.get(
                    "prompt_eval_duration_ns"
                ),
                "eval_duration_ns": metadata.get(
                    "eval_duration_ns"
                ),
                "tokens_per_second": calculate_tokens_per_second(
                    metadata
                ),
            },

            "error": response.get("error"),
        }

    except Exception as e:
        wall_time = time.perf_counter() - start
        resource_after = snapshot()

        return {
            "status": "error",

            "question_id": question["id"],
            "category": question["category"],
            "model": model,
            "mode": "RAG" if use_rag else "Non-RAG",

            "target": context.get("target"),

            "answer": "",
            "ai_explanation": "",

            "validation": None,
            "ollama_available": False,

            "wall_time_seconds": round(wall_time, 3),

            "resources": {
                "before": resource_before,
                "after": resource_after,
                "cpu_percent": resource_after.get("cpu_percent"),
                "process_cpu_percent": resource_after.get(
                    "process_cpu_percent"
                ),
                "memory_mb": resource_after.get("memory_mb"),
                "process_memory_mb": resource_after.get(
                    "process_memory_mb"
                ),
                "gpu_memory_mb": resource_after.get(
                    "gpu_memory_mb"
                ),
            },

            "ollama": {},

            "error": str(e),
        }


# ============================================================
# Main evaluation
# ============================================================

def main():

    print("=" * 70)
    print("RepoTwin Week 4 Evaluation")
    print("=" * 70)

    print(f"Repository: {REPO_PATH}")
    print(f"Models: {', '.join(MODELS)}")
    print("Questions: 28")
    print("Categories: 7")
    print("Modes: RAG + Non-RAG")
    print("Expected evaluations: 168")
    print()

    ensure_evaluation_repo(REPO_PATH)

    dataset = load_json(DATASET_PATH)
    questions = flatten_dataset(dataset)

    print(f"Loaded {len(questions)} questions.")

    # --------------------------------------------------------
    # Build graph ONCE
    # --------------------------------------------------------

    print()
    print("Building repository graph once...")

    graph_start = time.perf_counter()

    graph = build_unified_graph(str(REPO_PATH))

    graph_time = time.perf_counter() - graph_start

    print(
        f"Graph build completed in "
        f"{graph_time:.2f} seconds."
    )

    # --------------------------------------------------------
    # Build/load vector store ONCE
    # --------------------------------------------------------

    print()
    print("Preparing RAG vector store...")

    vector_start = time.perf_counter()

    try:
        get_or_build_vector_store(
            str(RAG_REPO_PATH),
            RAG_REPOSITORY_NAME,
            force_reindex=False,
        )

        vector_time = time.perf_counter() - vector_start

        print(
            f"Vector store ready in "
            f"{vector_time:.2f} seconds."
        )

    except Exception as e:
        print(f"WARNING: vector store preparation failed: {e}")
        print("RAG evaluations may fail.")

    # --------------------------------------------------------
    # Load existing results for resume support
    # --------------------------------------------------------

    results = load_existing_results()

    completed = {
        (
            r.get("question_id"),
            r.get("model"),
            r.get("mode"),
        )
        for r in results
    }

    if results:
        print()
        print(
            f"Resuming existing evaluation: "
            f"{len(results)} results already saved."
        )

    # --------------------------------------------------------
    # Evaluate
    # --------------------------------------------------------

    for index, question in enumerate(questions, start=1):

        qid = question["id"]
        category = question["category"]

        print()
        print("-" * 70)
        print(
            f"[Question {index}/{len(questions)}] "
            f"{qid} | {category}"
        )
        print(question["question"])

        evidence_package, context = build_question_context(
            question,
            graph,
        )

        if context is None:
            print("Skipping question because context failed.")
            continue

        # Record target/retrieval information once.
        target = context.get("target")

        retrieved_chunks = context.get(
            "retrieved_code_chunks",
            [],
        )

        retrieved_evidence = context.get(
            "retrieved_evidence",
            [],
        )

        expected = {
            "expected_files": question.get(
                "expected_files",
                [],
            ),
            "expected_entities": question.get(
                "expected_entities",
                [],
            ),
            "must_include": question.get(
                "must_include",
                [],
            ),
        }

        # ----------------------------------------------------
        # RAG + Non-RAG for all 3 models
        # ----------------------------------------------------

        for model in MODELS:

            for use_rag in [True, False]:

                mode = "RAG" if use_rag else "Non-RAG"

                key = (qid, model, mode)

                if key in completed:
                    print(
                        f"  SKIP {model} / {mode} "
                        f"(already completed)"
                    )
                    continue

                print(
                    f"  Running {model} / {mode}..."
                )

                result = run_model(
                    question,
                    context,
                    model,
                    use_rag,
                )

                # Add evaluation-grounding information.
                result["expected"] = expected

                result["retrieval"] = {
                    "retrieved_chunks_count": len(
                        retrieved_chunks
                    ),
                    "retrieved_evidence_count": len(
                        retrieved_evidence
                    ),
                    "retrieved_files": sorted(
                        {
                            chunk.get("file")
                            for chunk in retrieved_chunks
                            if isinstance(chunk, dict)
                            and chunk.get("file")
                        }
                    ),
                    "retrieved_entities": sorted(
                        {
                            chunk.get("entity")
                            for chunk in retrieved_chunks
                            if isinstance(chunk, dict)
                            and chunk.get("entity")
                        }
                    ),
                }

                result["evaluation_config"] = {
                    "max_depth": MAX_DEPTH,
                    "top_k_chunks": TOP_K_CHUNKS,
                    "repository": "fastapi-real",
                }

                results.append(result)
                completed.add(key)

                save_results(results)

                if result["status"] == "success":
                    print(
                        f"    OK "
                        f"({result['wall_time_seconds']:.2f}s)"
                    )
                else:
                    print(
                        f"    ERROR: {result.get('error')}"
                    )

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("Evaluation complete")
    print("=" * 70)

    print(f"Saved results: {RAW_RESULTS_PATH}")
    print(f"Total saved evaluations: {len(results)}")

    successful = sum(
        1 for r in results
        if r.get("status") == "success"
    )

    failed = len(results) - successful

    print(f"Successful: {successful}")
    print(f"Failed: {failed}")

    print()
    print("Expected total: 168")
    print()

    if len(results) == 168:
        print("RESULT: ALL 168 EVALUATIONS COMPLETED")
    else:
        print(
            f"RESULT: {168 - len(results)} "
            f"evaluations still pending"
        )


if __name__ == "__main__":
    main()
