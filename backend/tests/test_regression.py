import pytest
from pathlib import Path
from app.services.repository_service import clone_repository
from app.graph.unified_graph import build_unified_graph
from app.analysis.evidence import build_evidence_package
from app.graph.impact import find_impact
from app.analysis.test_impact import find_test_impact
from app.graph.risk import calculate_risk


def test_requests_response_close_regression():
    # Clone Requests repository
    repo_url = "https://github.com/psf/requests.git"
    repo_name = "requests"
    repo_path = clone_repository(repo_url, repo_name)

    graph = build_unified_graph(str(repo_path))

    # Look for Response.close target ID
    target_id = "method:src/requests/models.py:Response.close"
    node_ids = {n["id"] for n in graph["nodes"]}
    if target_id not in node_ids:
        alt_id = "method:requests/models.py:Response.close"
        if alt_id in node_ids:
            target_id = alt_id

    evidence = build_evidence_package(graph, target_id, max_depth=6)
    assert evidence["found"] is True

    analysis = evidence["analysis"]
    prod = analysis["production_impact"]
    tests = analysis["test_impact"]
    risk = analysis["risk"]

    direct_count = len(prod["direct"])
    indirect_count = len(prod["indirect"])
    total_prod = prod["count"]
    test_count = tests["count"]
    risk_score = risk["score"]
    risk_level = risk["level"]

    assert total_prod == 12, f"Expected 12 production callers, got {total_prod}"
    assert direct_count == 3, f"Expected 3 direct callers, got {direct_count}"
    assert indirect_count == 9, f"Expected 9 indirect callers, got {indirect_count}"
    assert test_count == 34, f"Expected 34 affected tests, got {test_count}"
    assert risk_score == 87, f"Expected risk score 87, got {risk_score}"
    assert risk_level == "HIGH", f"Expected HIGH risk level, got {risk_level}"


def test_fastapi_include_router_regression():
    repo_url = "https://github.com/fastapi/fastapi.git"
    repo_name = "fastapi"
    repo_path = clone_repository(repo_url, repo_name)

    graph = build_unified_graph(str(repo_path))

    target_id = "method:fastapi/applications.py:FastAPI.include_router"
    evidence = build_evidence_package(graph, target_id, max_depth=6)
    assert evidence["found"] is True

    analysis = evidence["analysis"]
    prod = analysis["production_impact"]
    tests = analysis["test_impact"]
    risk = analysis["risk"]

    total_prod = prod["count"]
    test_count = tests["count"]
    risk_score = risk["score"]
    risk_level = risk["level"]

    assert total_prod == 0, f"Expected 0 production callers, got {total_prod}"
    assert test_count == 60, f"Expected 60 affected tests, got {test_count}"
    assert risk_score == 0, f"Expected risk score 0, got {risk_score}"
    assert risk_level == "MINIMAL", f"Expected MINIMAL risk level, got {risk_level}"


def test_flask_regression():
    repo_url = "https://github.com/pallets/flask.git"
    repo_name = "flask"
    repo_path = clone_repository(repo_url, repo_name)

    graph = build_unified_graph(str(repo_path))

    # Look for Flask.full_dispatch_request
    node_ids = {n["id"] for n in graph["nodes"]}
    candidates = [
        "method:src/flask/app.py:Flask.full_dispatch_request",
        "method:src/flask/sansio/app.py:App.full_dispatch_request",
        "method:flask/app.py:Flask.full_dispatch_request",
    ]
    target_id = next((c for c in candidates if c in node_ids), None)
    if not target_id:
        target_id = next((nid for nid in node_ids if "full_dispatch_request" in nid), None)

    assert target_id is not None, "Could not find full_dispatch_request in Flask"

    evidence = build_evidence_package(graph, target_id, max_depth=6)
    assert evidence["found"] is True
    assert "production_impact" in evidence["analysis"]
    assert "test_impact" in evidence["analysis"]
    assert "risk" in evidence["analysis"]


def test_tests_never_counted_as_production():
    mock_graph = {
        "repository": "mock",
        "nodes": [
            {"id": "method:app/core.py:Engine.run", "type": "method", "file": "app/core.py", "name": "Engine.run"},
            {"id": "function:app/api.py:handler", "type": "function", "file": "app/api.py", "name": "handler"},
            {"id": "function:tests/test_core.py:test_run", "type": "function", "file": "tests/test_core.py", "name": "test_run"},
        ],
        "edges": [
            {"source": "function:app/api.py:handler", "target": "method:app/core.py:Engine.run", "type": "calls", "resolution": "internal", "confidence": "high"},
            {"source": "function:tests/test_core.py:test_run", "target": "method:app/core.py:Engine.run", "type": "calls", "resolution": "internal", "confidence": "high"},
        ],
    }

    evidence = build_evidence_package(mock_graph, "method:app/core.py:Engine.run")
    prod = evidence["analysis"]["production_impact"]
    tests = evidence["analysis"]["test_impact"]

    # Only app/api.py is production
    assert prod["count"] == 1
    assert prod["direct"][0]["file"] == "app/api.py"
    # tests/test_core.py is test impact
    assert tests["count"] == 1
    assert tests["tests"][0]["file"] == "tests/test_core.py"
