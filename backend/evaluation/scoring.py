"""Ground-truth scoring for RepoTwin Week 4 evaluation."""

import re
from typing import Any


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip().lower())


def contains_requirement(answer: str, requirement: str) -> bool:
    text = _norm(answer)
    req = _norm(requirement)

    if not req:
        return True

    if req in text:
        return True

    terms = [
        t for t in re.findall(r"[a-z0-9_./-]+", req)
        if len(t) > 3
    ]

    if not terms:
        return False

    matched = sum(1 for term in terms if term in text)

    return matched / len(terms) >= 0.75


def score_answer(
    answer: str,
    ground_truth: dict[str, Any],
) -> dict[str, Any]:

    requirements = ground_truth.get(
        "must_include",
        [],
    ) or []

    if not answer:
        return {
            "correctness_score": 0,
            "must_include_total": len(requirements),
            "must_include_matched": 0,
            "must_include_coverage":
                0.0 if requirements else 1.0,
            "matched_requirements": [],
            "missing_requirements": requirements,
        }

    matched = [
        r for r in requirements
        if contains_requirement(answer, r)
    ]

    missing = [
        r for r in requirements
        if r not in matched
    ]

    coverage = (
        len(matched) / len(requirements)
        if requirements
        else 1.0
    )

    if coverage >= 0.75:
        score = 2
    elif coverage >= 0.40:
        score = 1
    else:
        score = 0

    return {
        "correctness_score": score,
        "must_include_total": len(requirements),
        "must_include_matched": len(matched),
        "must_include_coverage": round(
            coverage,
            4,
        ),
        "matched_requirements": matched,
        "missing_requirements": missing,
    }


def _precision_recall(
    retrieved: list[str],
    expected: list[str],
) -> tuple[float, float]:

    retrieved_set = {
        _norm(x)
        for x in retrieved
        if x
    }

    expected_set = {
        _norm(x)
        for x in expected
        if x
    }

    precision = (
        len(retrieved_set & expected_set)
        / len(retrieved_set)
        if retrieved_set
        else 0.0
    )

    recall = (
        len(retrieved_set & expected_set)
        / len(expected_set)
        if expected_set
        else 1.0
    )

    return (
        round(precision, 4),
        round(recall, 4),
    )


def score_retrieval(
    result: dict[str, Any],
) -> dict[str, Any]:

    expected = result.get(
        "expected",
        {},
    ) or {}

    retrieval = result.get(
        "retrieval",
        {},
    ) or {}

    file_precision, file_recall = _precision_recall(
        retrieval.get("retrieved_files", []),
        expected.get("expected_files", []),
    )

    entity_precision, entity_recall = _precision_recall(
        retrieval.get("retrieved_entities", []),
        expected.get("expected_entities", []),
    )

    return {
        "file_precision": file_precision,
        "file_recall": file_recall,
        "entity_precision": entity_precision,
        "entity_recall": entity_recall,
    }


def heuristic_hallucination_flag(
    result: dict[str, Any],
) -> dict[str, Any]:
    """
    Conservative hallucination proxy.

    Flags repository Python file references in the answer
    that are neither expected nor retrieved.

    This is NOT a human-verified hallucination score.
    """

    answer = (
        result.get("ai_explanation")
        or result.get("answer", "")
    )

    expected = result.get(
        "expected",
        {},
    ) or {}

    retrieval = result.get(
        "retrieval",
        {},
    ) or {}

    allowed = (
        set(expected.get("expected_files", []))
        | set(retrieval.get("retrieved_files", []))
    )

    refs = set(
        re.findall(
            r"(?:[A-Za-z0-9_.-]+/)+"
            r"[A-Za-z0-9_.-]+\.py",
            answer,
        )
    )

    unsupported = sorted(
        ref
        for ref in refs
        if ref not in allowed
    )

    return {
        "hallucination_flag": bool(
            unsupported
        ),
        "unsupported_file_references": unsupported,
        "hallucination_method":
            "heuristic_unsupported_repository_file_reference",
    }


def retrieval_metrics(
    expected_files: list[str],
    retrieved_files: list[str],
    expected_entities: list[str],
    retrieved_entities: list[str],
) -> dict:
    """Calculate precision and recall for retrieved files/entities."""

    expected_files = set(expected_files or [])
    retrieved_files = set(retrieved_files or [])

    expected_entities = set(expected_entities or [])
    retrieved_entities = set(retrieved_entities or [])

    file_relevant = expected_files & retrieved_files
    entity_relevant = expected_entities & retrieved_entities

    file_precision = (
        len(file_relevant) / len(retrieved_files)
        if retrieved_files
        else 0.0
    )

    file_recall = (
        len(file_relevant) / len(expected_files)
        if expected_files
        else 0.0
    )

    entity_precision = (
        len(entity_relevant) / len(retrieved_entities)
        if retrieved_entities
        else 0.0
    )

    entity_recall = (
        len(entity_relevant) / len(expected_entities)
        if expected_entities
        else 0.0
    )

    return {
        "relevant_files": sorted(file_relevant),
        "relevant_entities": sorted(entity_relevant),

        "file_precision": round(file_precision, 4),
        "file_recall": round(file_recall, 4),

        "entity_precision": round(entity_precision, 4),
        "entity_recall": round(entity_recall, 4),
    }
