from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Any

from app.services.repository_service import clone_repository
from app.graph.repository_twin import build_repository_twin
from app.graph.unified_graph import build_unified_graph
from app.graph.impact import find_impact
from app.analysis.evidence import build_evidence_package
from app.services.rag_service import (
    get_or_build_vector_store,
    retrieve_rag_code_chunks,
    assemble_rag_context,
)
from app.services.llm_service import (
    analyze_with_ollama,
    check_ollama_health,
    get_default_model,
    get_ollama_base_url,
)
from app.services.embedding_service import get_embedding_service


app = FastAPI(
    title="RepoTwin",
    description="Repository intelligence, RAG code analysis, and change-impact reasoning",
    version="0.4.0",
)

# Enable CORS for all development environments without hardcoded IPs
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class RepositoryRequest(BaseModel):
    repository_url: str
    repository_name: str
    force_fresh: bool = False


class ImpactRequest(BaseModel):
    repository_url: str
    repository_name: str
    target_id: str
    max_depth: int = 5


class IndexRequest(BaseModel):
    repository_url: str
    repository_name: str
    force_reindex: bool = False


class EngineeringAnalysisRequest(BaseModel):
    repository_url: str
    repository_name: str
    target_id: str
    question: str
    max_depth: int = 6
    top_k: int = 10
    use_rag: bool = True
    model: str | None = None
    top_k_chunks: int = 5


class RagCompareRequest(BaseModel):
    repository_url: str
    repository_name: str
    target_id: str
    question: str
    max_depth: int = 6
    top_k_chunks: int = 5
    model: str | None = None


@app.get("/")
def root():
    return {
        "name": "RepoTwin",
        "status": "running",
        "version": "0.4.0",
        "default_model": get_default_model(),
        "ollama_base_url": get_ollama_base_url(),
    }


@app.get("/health")
def health():
    ollama_info = check_ollama_health()
    emb_service = get_embedding_service()
    return {
        "status": "healthy",
        "version": "0.4.0",
        "ollama": ollama_info,
        "embedding_model": emb_service.model_name,
    }


@app.post("/repositories/analyze")
def analyze_repository_endpoint(request: RepositoryRequest):
    try:
        repository_path = clone_repository(
            request.repository_url,
            request.repository_name,
            force_fresh=request.force_fresh,
        )
        twin = build_repository_twin(str(repository_path))
        return twin
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/repositories/impact")
def repository_impact(request: ImpactRequest):
    try:
        repository_path = clone_repository(
            request.repository_url,
            request.repository_name,
        )
        graph = build_unified_graph(str(repository_path))
        result = find_impact(
            graph,
            request.target_id,
            request.max_depth,
        )
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/repositories/targets")
def repository_targets(
    repository_url: str,
    repository_name: str,
    search: str | None = None,
    limit: int = 100,
):
    try:
        repository_path = clone_repository(
            repository_url,
            repository_name,
        )
        graph = build_unified_graph(str(repository_path))
        nodes = graph.get("nodes", [])

        targets = []
        for node in nodes:
            node_type = node.get("type")
            if node_type not in {"function", "method", "class"}:
                continue
            target = {
                "id": node.get("id"),
                "type": node_type,
                "name": node.get("name"),
                "file": node.get("file"),
            }
            targets.append(target)

        if search:
            query = search.lower().strip()
            targets = [
                t
                for t in targets
                if query in str(t.get("name", "")).lower()
                or query in str(t.get("file", "")).lower()
                or query in str(t.get("id", "")).lower()
            ]

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
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/repositories/index")
def index_repository(request: IndexRequest):
    try:
        repository_path = clone_repository(
            request.repository_url,
            request.repository_name,
        )
        store = get_or_build_vector_store(
            repository_path=str(repository_path),
            repository_name=request.repository_name,
            force_reindex=request.force_reindex,
        )
        return {
            "repository": request.repository_name,
            "status": "indexed",
            "chunk_count": store.count,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/repositories/engineering-analysis")
def engineering_analysis(request: EngineeringAnalysisRequest):
    try:
        # 1. Clone or get repository
        repository_path = clone_repository(
            request.repository_url,
            request.repository_name,
        )

        # 2. Build repository graph
        graph = build_unified_graph(str(repository_path))

        # 3. Build deterministic evidence package
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

        # 4. Assemble context (RAG or standard)
        context = assemble_rag_context(
            evidence_package=evidence,
            query=request.question,
            repository_path=str(repository_path),
            repository_name=request.repository_name,
            top_k_chunks=request.top_k_chunks,
        )

        # 5. Generate AI analysis (Code Llama via Ollama with validation)
        llm_result = analyze_with_ollama(
            context,
            model=request.model,
            use_rag=request.use_rag,
        )

        # 6. Structured orchestration response
        analysis = evidence.get("analysis", {})
        production = analysis.get("production_impact", {})
        tests = analysis.get("test_impact", {})
        risk = analysis.get("risk", {})

        return {
            "repository": request.repository_name,
            "target": evidence.get("target", {}),
            "question": request.question,
            "use_rag": request.use_rag,
            "summary": {
                "production_impact": production.get("count", 0),
                "direct_callers": len(production.get("direct", [])),
                "indirect_callers": len(production.get("indirect", [])),
                "affected_tests": tests.get("count", 0),
                "risk_score": risk.get("score", 0),
                "risk_level": risk.get("level", "UNKNOWN"),
            },
            "analysis": analysis,
            "retrieval": {
                "count": len(evidence.get("evidence", [])),
                "evidence": evidence.get("evidence", []),
            },
            "rag_chunks": {
                "count": context.get("retrieved_chunks_count", 0),
                "chunks": context.get("retrieved_code_chunks", []),
            },
            "ai_analysis": {
                "model": llm_result.get("model"),
                "ollama_available": llm_result.get("ollama_available"),
                "mode": llm_result.get("mode"),
                "answer": llm_result.get("answer"),
                "ai_explanation": llm_result.get("ai_explanation"),
                "validation": llm_result.get("validation"),
                "error": llm_result.get("error"),
            },
            "evidence_count": len(evidence.get("evidence", [])),
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/repositories/rag-compare")
def rag_compare(request: RagCompareRequest):
    """
    Exercise 5 comparison endpoint: Run both with-RAG and without-RAG side by side.
    """
    try:
        repository_path = clone_repository(
            request.repository_url,
            request.repository_name,
        )
        graph = build_unified_graph(str(repository_path))
        evidence = build_evidence_package(
            graph,
            request.target_id,
            request.max_depth,
        )

        if not evidence.get("found"):
            raise HTTPException(
                status_code=404,
                detail={"message": "Target entity not found.", "target_id": request.target_id},
            )

        context = assemble_rag_context(
            evidence_package=evidence,
            query=request.question,
            repository_path=str(repository_path),
            repository_name=request.repository_name,
            top_k_chunks=request.top_k_chunks,
        )

        # With RAG
        rag_result = analyze_with_ollama(
            context,
            model=request.model,
            use_rag=True,
        )

        # Without RAG
        non_rag_result = analyze_with_ollama(
            context,
            model=request.model,
            use_rag=False,
        )

        analysis = evidence.get("analysis", {})
        production = analysis.get("production_impact", {})
        tests = analysis.get("test_impact", {})
        risk = analysis.get("risk", {})

        return {
            "repository": request.repository_name,
            "target": evidence.get("target", {}),
            "question": request.question,
            "summary": {
                "production_impact": production.get("count", 0),
                "direct_callers": len(production.get("direct", [])),
                "indirect_callers": len(production.get("indirect", [])),
                "affected_tests": tests.get("count", 0),
                "risk_score": risk.get("score", 0),
                "risk_level": risk.get("level", "UNKNOWN"),
            },
            "rag_chunks": {
                "count": context.get("retrieved_chunks_count", 0),
                "chunks": context.get("retrieved_code_chunks", []),
            },
            "with_rag": rag_result,
            "without_rag": non_rag_result,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
