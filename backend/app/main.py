from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.services.repository_service import clone_repository
from app.graph.repository_twin import build_repository_twin
from app.graph.unified_graph import build_unified_graph
from app.graph.impact import find_impact
from app.analysis.evidence import build_evidence_package
from app.retrieval.evidence_retriever import build_retrieval_context
from app.services.llm_service import analyze_with_ollama


app = FastAPI(
    title="RepoTwin",
    description=(
        "Repository intelligence and "
        "change-impact analysis"
    ),
    version="0.3.0",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://192.168.195.131:5173",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class RepositoryRequest(BaseModel):
    repository_url: str
    repository_name: str


class ImpactRequest(BaseModel):
    repository_url: str
    repository_name: str
    target_id: str
    max_depth: int = 5


class EngineeringAnalysisRequest(BaseModel):
    repository_url: str
    repository_name: str
    target_id: str
    question: str
    max_depth: int = 6
    top_k: int = 10


@app.get("/")
def root():
    return {
        "name": "RepoTwin",
        "status": "running",
        "version": "0.3.0",
    }


@app.get("/health")
def health():
    return {
        "status": "healthy"
    }


@app.post("/repositories/analyze")
def analyze_repository_endpoint(
    request: RepositoryRequest,
):
    try:
        repository_path = clone_repository(
            request.repository_url,
            request.repository_name,
        )

        twin = build_repository_twin(
            str(repository_path)
        )

        return twin

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )


@app.post("/repositories/impact")
def repository_impact(
    request: ImpactRequest,
):
    try:
        repository_path = clone_repository(
            request.repository_url,
            request.repository_name,
        )

        graph = build_unified_graph(
            str(repository_path)
        )

        result = find_impact(
            graph,
            request.target_id,
            request.max_depth,
        )

        return result

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )


@app.get("/repositories/targets")
def repository_targets(
    repository_url: str,
    repository_name: str,
    search: str | None = None,
    limit: int = 100,
):
    try:
        # Clone repository
        repository_path = clone_repository(
            repository_url,
            repository_name,
        )

        # Build repository graph
        graph = build_unified_graph(
            str(repository_path)
        )

        nodes = graph.get("nodes", [])

        # Only expose useful code entities.
        targets = []

        for node in nodes:
            node_type = node.get("type")

            if node_type not in {
                "function",
                "method",
                "class",
            }:
                continue

            target = {
                "id": node.get("id"),
                "type": node_type,
                "name": node.get("name"),
                "file": node.get("file"),
            }

            targets.append(target)

        # Optional search.
        if search:
            query = search.lower().strip()

            targets = [
                target
                for target in targets
                if query in str(
                    target.get("name", "")
                ).lower()
                or query in str(
                    target.get("file", "")
                ).lower()
                or query in str(
                    target.get("id", "")
                ).lower()
            ]

        # Stable ordering.
        targets.sort(
            key=lambda item: (
                str(item.get("file", "")),
                str(item.get("name", "")),
                str(item.get("type", "")),
            )
        )

        return {
            "repository": repository_name,
            "count": len(targets[:limit]),
            "targets": targets[:limit],
        }

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )


@app.post("/repositories/engineering-analysis")
def engineering_analysis(
    request: EngineeringAnalysisRequest,
):
    try:
        # -----------------------------------------------------
        # 1. Clone repository
        # -----------------------------------------------------

        repository_path = clone_repository(
            request.repository_url,
            request.repository_name,
        )

        # -----------------------------------------------------
        # 2. Build repository intelligence graph
        # -----------------------------------------------------

        graph = build_unified_graph(
            str(repository_path)
        )

        # -----------------------------------------------------
        # 3. Build deterministic evidence
        # -----------------------------------------------------

        evidence = build_evidence_package(
            graph,
            request.target_id,
            request.max_depth,
        )

        if not evidence.get("found"):
            raise HTTPException(
                status_code=404,
                detail={
                    "message": "Target entity not found.",
                    "target_id": request.target_id,
                },
            )

        # -----------------------------------------------------
        # 4. Retrieve relevant evidence
        # -----------------------------------------------------

        context = build_retrieval_context(
            evidence,
            request.question,
            request.top_k,
        )

        # -----------------------------------------------------
        # 5. Generate engineering explanation
        # -----------------------------------------------------

        llm_result = analyze_with_ollama(
            context
        )

        # -----------------------------------------------------
        # 6. Return complete orchestration result
        # -----------------------------------------------------

        analysis = evidence.get(
            "analysis",
            {},
        )

        production = analysis.get(
            "production_impact",
            {},
        )

        tests = analysis.get(
            "test_impact",
            {},
        )

        risk = analysis.get(
            "risk",
            {},
        )

        return {
            "repository": request.repository_name,

            "target": evidence.get(
                "target",
                {},
            ),

            "question": request.question,

            "summary": {
                "production_impact": production.get(
                    "count",
                    0,
                ),

                "direct_callers": len(
                    production.get(
                        "direct",
                        [],
                    )
                ),

                "indirect_callers": len(
                    production.get(
                        "indirect",
                        [],
                    )
                ),

                "affected_tests": tests.get(
                    "count",
                    0,
                ),

                "risk_score": risk.get(
                    "score",
                    0,
                ),

                "risk_level": risk.get(
                    "level",
                    "UNKNOWN",
                ),
            },

            "analysis": analysis,

            "retrieval": {
                "count": context.get(
                    "retrieved_count",
                    0,
                ),
                "evidence": context.get(
                    "retrieved_evidence",
                    [],
                ),
            },

            "ai_analysis": {
                "model": llm_result.get(
                    "model"
                ),
                "answer": llm_result.get(
                    "answer"
                ),
                "validation": llm_result.get(
                    "validation"
                ),
            },

            "evidence_count": len(
                evidence.get(
                    "evidence",
                    [],
                )
            ),
        }

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )
