from typing import Any


def _text_for_evidence(item: dict[str, Any]) -> str:
    parts = [
        str(item.get("category", "")),
        str(item.get("relationship", "")),
        str(item.get("source", "")),
        str(item.get("source_name", "")),
        str(item.get("file", "")),
        str(item.get("target", "")),
    ]

    return " ".join(parts).lower()


def _score_evidence(
    item: dict[str, Any],
    query_terms: set[str],
) -> int:
    text = _text_for_evidence(item)

    score = 0

    # Query-term relevance.
    for term in query_terms:
        if term in text:
            score += 3

    # Engineering evidence is more useful than generic metadata.
    category = item.get("category")

    if category == "production_impact":
        score += 4

    elif category == "test_impact":
        score += 3

    # Prefer direct relationships.
    relationship = item.get("relationship")

    if relationship == "direct_caller":
        score += 4

    elif relationship == "affected_test":
        score += 3

    # Prefer closer graph relationships.
    depth = item.get("depth")

    if isinstance(depth, int):
        if depth == 1:
            score += 4
        elif depth == 2:
            score += 3
        elif depth <= 4:
            score += 1

    # High-confidence evidence is preferred.
    if item.get("confidence") == "high":
        score += 3

    return score


def retrieve_evidence(
    evidence_package: dict,
    query: str,
    top_k: int = 12,
) -> list[dict[str, Any]]:
    """
    Retrieve the most relevant deterministic evidence for a query.

    This is intentionally lightweight. It provides retrieval semantics
    without requiring a vector database or embedding model.
    """

    evidence = evidence_package.get(
        "evidence",
        [],
    )

    if not evidence:
        return []

    query_terms = {
        term.lower()
        for term in query.split()
        if len(term.strip()) >= 3
    }

    scored = []

    for item in evidence:
        score = _score_evidence(
            item,
            query_terms,
        )

        scored.append(
            (
                score,
                item,
            )
        )

    scored.sort(
        key=lambda pair: (
            -pair[0],
            pair[1].get("depth", 999),
        )
    )

    results = []

    for score, item in scored[:top_k]:
        result = dict(item)
        result["retrieval_score"] = score
        results.append(result)

    return results


def build_retrieval_context(
    evidence_package: dict,
    query: str,
    top_k: int = 12,
) -> dict[str, Any]:
    """
    Build a compact context package for the LLM.
    """

    retrieved = retrieve_evidence(
        evidence_package,
        query,
        top_k,
    )

    analysis = evidence_package.get(
        "analysis",
        {},
    )

    return {
        "query": query,
        "evidence_package": evidence_package,
        "target": evidence_package.get(
            "target"
        ),
        "risk": analysis.get(
            "risk"
        ),
        "production_impact_count": analysis.get(
            "production_impact",
            {},
        ).get(
            "count",
            0,
        ),
        "test_impact_count": analysis.get(
            "test_impact",
            {},
        ).get(
            "count",
            0,
        ),
        "history": analysis.get(
            "history",
            {},
        ),
        "retrieved_evidence": retrieved,
        "retrieved_count": len(retrieved),
    }
