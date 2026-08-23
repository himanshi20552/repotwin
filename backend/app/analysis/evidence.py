from app.analysis.test_impact import find_test_impact
from app.graph.impact import find_impact
from app.graph.risk import calculate_risk
from app.history.git_history import analyze_history


def build_evidence_package(
    graph: dict,
    target_id: str,
    max_depth: int = 6,
) -> dict:
    """
    Build a structured evidence package for a repository change.

    Combines:
        1. Production impact
        2. Test impact
        3. Risk analysis
        4. Call-path evidence

    This package is deterministic and is intended to become
    the input to the RAG/LLM reasoning layer later.
    """

    # ---------------------------------------------------------
    # Production impact
    # ---------------------------------------------------------

    impact = find_impact(
        graph,
        target_id,
        max_depth,
    )

    if not impact.get("found"):
        return {
            "target": target_id,
            "found": False,
            "evidence": [],
            "summary": {
                "production_impact_count": 0,
                "test_impact_count": 0,
                "risk_score": 0,
                "risk_level": "UNKNOWN",
            },
        }

    # ---------------------------------------------------------
    # Risk analysis
    # ---------------------------------------------------------

    risk = calculate_risk(
        impact,
        graph,
    )

    # ---------------------------------------------------------
    # Test impact
    # ---------------------------------------------------------

    test_impact = find_test_impact(
        graph,
        target_id,
        max_depth,
    )

    # ---------------------------------------------------------
    # Build node lookup
    # ---------------------------------------------------------

    nodes = {
        node["id"]: node
        for node in graph.get("nodes", [])
    }

    # ---------------------------------------------------------
    # Build direct evidence paths
    # ---------------------------------------------------------

    target_node = nodes.get(
        target_id,
        impact.get("target", {}),
    )

    # ---------------------------------------------------------
    # Git history evidence
    # ---------------------------------------------------------

    target_file = target_node.get("file")
    target_name = target_node.get("name")

    history = {
        "file_history": {
            "file": target_file,
            "commit_count": 0,
            "commits": [],
        },
        "co_changed_files": [],
    }

    repository_path = graph.get(
        "repository_path"
    )

    if repository_path and target_file:
        history = analyze_history(
            repository_path,
            target_file,
            target_name,
        )

    evidence = []

    # Direct production callers.
    for item in impact.get(
        "direct_impact",
        [],
    ):
        if (item.get("file") or "").lower().startswith("tests/"):
            continue

        evidence.append({
            "category": "production_impact",
            "relationship": "direct_caller",
            "source": item.get("id"),
            "source_type": item.get("type"),
            "source_name": item.get("name"),
            "file": item.get("file"),
            "depth": item.get("depth"),
            "target": target_id,
            "confidence": "high",
        })

    # Indirect production callers.
    for item in impact.get(
        "indirect_impact",
        [],
    ):
        if (item.get("file") or "").lower().startswith("tests/"):
            continue

        evidence.append({
            "category": "production_impact",
            "relationship": "indirect_caller",
            "source": item.get("id"),
            "source_type": item.get("type"),
            "source_name": item.get("name"),
            "file": item.get("file"),
            "depth": item.get("depth"),
            "target": target_id,
            "confidence": "medium",
        })

    # Test evidence.
    for test in test_impact.get(
        "tests",
        [],
    ):

        evidence.append({
            "category": "test_impact",
            "relationship": "affected_test",
            "source": test.get("id"),
            "source_type": test.get("type"),
            "source_name": test.get("name"),
            "file": test.get("file"),
            "depth": test.get("depth"),
            "target": target_id,
            "confidence": (
                "high"
                if test.get("depth", 99) <= 2
                else "medium"
            ),
        })

    # ---------------------------------------------------------
    # Summary
    # ---------------------------------------------------------

    production_direct = [
        item for item in impact.get("direct_impact", [])
        if not (item.get("file") or "").lower().startswith("tests/")
    ]

    production_indirect = [
        item for item in impact.get("indirect_impact", [])
        if not (item.get("file") or "").lower().startswith("tests/")
    ]

    production_count = (
        len(production_direct)
        + len(production_indirect)
    )

    test_count = test_impact.get(
        "test_count",
        0,
    )

    return {
        "found": True,
        "target": {
            "id": target_id,
            "type": target_node.get("type"),
            "name": target_node.get("name"),
            "file": target_node.get("file"),
        },

        "repository": graph.get(
            "repository"
        ),

        "analysis": {
            "max_depth": max_depth,

            "history": history,

            "production_impact": {
                "direct": production_direct,
                "indirect": production_indirect,
                "count": production_count,
            },

            "test_impact": {
                "tests": test_impact.get(
                    "tests",
                    [],
                ),
                "count": test_count,
            },

            "risk": risk,
        },

        "evidence": evidence,

        "llm_context": {
            "target": target_id,
            "production_impact_count": production_count,
            "test_impact_count": test_count,
            "risk_score": risk.get(
                "score",
                0,
            ),
            "risk_level": risk.get(
                "level",
                "UNKNOWN",
            ),
            "history": history,
            "high_confidence_paths": risk.get(
                "signals",
                {},
            ).get(
                "high_confidence_paths",
                0,
            ),
            "evidence_items": evidence,
        },
    }
