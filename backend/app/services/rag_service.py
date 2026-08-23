from pathlib import Path
from typing import Any
from app.services.chunking_service import chunk_repository
from app.services.embedding_service import get_embedding_service
from app.services.vector_store import VectorStore


# In-memory registry of active vector stores per repository
_ACTIVE_STORES: dict[str, VectorStore] = {}


def get_or_build_vector_store(
    repository_path: str,
    repository_name: str = "",
    force_reindex: bool = False,
) -> VectorStore:
    root = Path(repository_path)
    if not repository_name:
        repository_name = root.name

    if not force_reindex and repository_name in _ACTIVE_STORES:
        return _ACTIVE_STORES[repository_name]

    store = VectorStore(repository_name=repository_name)

    # Try loading from disk index if available
    if not force_reindex and store.load():
        _ACTIVE_STORES[repository_name] = store
        return store

    # Otherwise chunk and build embeddings
    chunks = chunk_repository(repository_path, repository_name)
    if chunks:
        embedding_service = get_embedding_service()
        texts = [chunk.get("text", "") for chunk in chunks]
        embeddings = embedding_service.generate_embeddings(texts)
        store.add_documents(chunks, embeddings)
        # Cache to disk
        try:
            store.save()
        except Exception:
            pass

    _ACTIVE_STORES[repository_name] = store
    return store


def retrieve_rag_code_chunks(
    repository_path: str,
    repository_name: str,
    query: str,
    target_id: str | None = None,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """
    Retrieve semantically relevant AST code chunks for the given question and target.
    """
    store = get_or_build_vector_store(repository_path, repository_name)
    if store.count == 0:
        return []

    embedding_service = get_embedding_service()

    # Formulate a rich search query combining the question and target info
    search_terms = query
    if target_id:
        clean_target = target_id.replace("method:", "").replace("function:", "").replace("class:", "")
        search_terms = f"{query} {clean_target}"

    query_vector = embedding_service.generate_query_embedding(search_terms)
    results = store.similarity_search(query_vector, top_k=top_k)

    return results


def assemble_rag_context(
    evidence_package: dict[str, Any],
    query: str,
    repository_path: str,
    repository_name: str,
    top_k_chunks: int = 5,
) -> dict[str, Any]:
    """
    Combines deterministic graph evidence with vector-retrieved code chunks.
    """
    target = evidence_package.get("target", {})
    target_id = target.get("id") if isinstance(target, dict) else str(target)

    # Retrieve real AST code chunks
    code_chunks = retrieve_rag_code_chunks(
        repository_path=repository_path,
        repository_name=repository_name,
        query=query,
        target_id=target_id,
        top_k=top_k_chunks,
    )

    analysis = evidence_package.get("analysis", {})

    return {
        "query": query,
        "evidence_package": evidence_package,
        "target": target,
        "risk": analysis.get("risk", {}),
        "production_impact_count": analysis.get("production_impact", {}).get("count", 0),
        "test_impact_count": analysis.get("test_impact", {}).get("count", 0),
        "history": analysis.get("history", {}),
        "retrieved_evidence": evidence_package.get("evidence", []),
        "retrieved_code_chunks": code_chunks,
        "retrieved_chunks_count": len(code_chunks),
        "is_rag": True,
    }
