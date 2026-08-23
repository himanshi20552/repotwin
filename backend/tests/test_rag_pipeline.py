import pytest
import numpy as np
from pathlib import Path

from app.services.chunking_service import chunk_python_file, chunk_repository
from app.services.embedding_service import get_embedding_service, EmbeddingService
from app.services.vector_store import VectorStore
from app.services.rag_service import assemble_rag_context
from app.services.llm_service import (
    build_rag_prompt,
    build_non_rag_prompt,
    analyze_with_ollama,
    get_default_model,
)
from app.validation.evidence_validator import validate_answer


def test_ast_chunking(tmp_path: Path):
    sample_code = '''"""Module docstring for sample."""

class DataProcessor:
    """Class docstring."""
    def process_item(self, item: dict) -> bool:
        """Process a single item."""
        return True

def standalone_helper(x: int) -> int:
    """Helper function."""
    return x * 2
'''
    py_file = tmp_path / "sample.py"
    py_file.write_text(sample_code, encoding="utf-8")

    chunks = chunk_python_file(py_file, tmp_path, "sample_repo")

    # Verify chunk types extracted
    types = [c["type"] for c in chunks]
    assert "module" in types
    assert "class" in types
    assert "method" in types
    assert "function" in types

    # Check method chunk details
    method_chunk = next(c for c in chunks if c["type"] == "method")
    assert method_chunk["name"] == "DataProcessor.process_item"
    assert method_chunk["entity_id"] == "method:sample.py:DataProcessor.process_item"
    assert method_chunk["docstring"] == "Process a single item."
    assert "return True" in method_chunk["source_code"]
    assert method_chunk["start_line"] > 0
    assert method_chunk["end_line"] >= method_chunk["start_line"]


def test_embedding_service():
    service = get_embedding_service()
    texts = [
        "def close(self): pass",
        "class Response: pass",
        "What happens if Response.close is changed?",
    ]
    embeddings = service.generate_embeddings(texts)

    assert isinstance(embeddings, np.ndarray)
    assert embeddings.shape[0] == 3
    assert embeddings.shape[1] > 0

    # Ensure vectors are normalized (L2 norm == 1)
    norms = np.linalg.norm(embeddings, axis=1)
    np.testing.assert_allclose(norms, np.ones(3), atol=1e-5)

    # Query embedding
    q_emb = service.generate_query_embedding("close connection")
    assert isinstance(q_emb, np.ndarray)
    assert np.isclose(np.linalg.norm(q_emb), 1.0, atol=1e-5)


def test_vector_store_similarity_search():
    store = VectorStore(repository_name="test_repo")

    chunks = [
        {
            "chunk_id": "chunk:1",
            "entity_id": "method:models.py:Response.close",
            "type": "method",
            "name": "Response.close",
            "file": "models.py",
            "source_code": "def close(self): self._content = False",
            "text": "File: models.py Method: Response.close Closes the underlying connection response",
        },
        {
            "chunk_id": "chunk:2",
            "entity_id": "function:utils.py:calculate_hash",
            "type": "function",
            "name": "calculate_hash",
            "file": "utils.py",
            "source_code": "def calculate_hash(data): return hashlib.sha256(data)",
            "text": "File: utils.py Function: calculate_hash Compute SHA256 cryptographic hash",
        },
    ]

    emb_service = get_embedding_service()
    embeddings = emb_service.generate_embeddings([c["text"] for c in chunks])

    store.add_documents(chunks, embeddings)
    assert store.count == 2

    # Search for connection closing
    q_vec = emb_service.generate_query_embedding("how to close response connection")
    results = store.similarity_search(q_vec, top_k=2)

    assert len(results) == 2
    # The Response.close chunk should rank higher than calculate_hash
    assert results[0]["entity_id"] == "method:models.py:Response.close"
    assert results[0]["similarity_score"] > results[1]["similarity_score"]


def test_rag_context_and_prompts():
    mock_evidence = {
        "target": {
            "id": "method:src/requests/models.py:Response.close",
            "name": "Response.close",
            "file": "src/requests/models.py",
            "type": "method",
        },
        "found": True,
        "evidence": [
            {
                "category": "production_impact",
                "relationship": "direct_caller",
                "source": "method:src/requests/sessions.py:Session.send",
                "source_name": "Session.send",
                "file": "src/requests/sessions.py",
                "depth": 1,
                "confidence": "high",
            }
        ],
        "analysis": {
            "production_impact": {
                "count": 12,
                "direct": [{"file": "src/requests/sessions.py", "name": "Session.send"}],
                "indirect": [{"file": "src/requests/api.py", "name": "get"}],
            },
            "test_impact": {"count": 34, "tests": []},
            "risk": {
                "score": 87,
                "level": "HIGH",
                "signals": {
                    "direct_callers": 3,
                    "indirect_callers": 9,
                    "affected_files": 2,
                    "high_confidence_paths": 3,
                    "medium_confidence_paths": 0,
                },
            },
            "history": {
                "file_history": {"commit_count": 5, "commits": []},
                "symbol_history": {"commit_count": 0, "commits": []},
            },
        },
    }

    context = {
        "query": "What is the impact of changing Response.close?",
        "evidence_package": mock_evidence,
        "target": mock_evidence["target"],
        "risk": mock_evidence["analysis"]["risk"],
        "production_impact_count": 12,
        "test_impact_count": 34,
        "history": mock_evidence["analysis"]["history"],
        "retrieved_evidence": mock_evidence["evidence"],
        "retrieved_code_chunks": [
            {
                "entity_id": "method:src/requests/models.py:Response.close",
                "name": "Response.close",
                "file": "src/requests/models.py",
                "start_line": 950,
                "end_line": 960,
                "type": "method",
                "source_code": "def close(self):\n    self.raw.close()",
                "similarity_score": 0.92,
            }
        ],
    }

    rag_prompt = build_rag_prompt(context)
    assert "Response.close" in rag_prompt
    assert "Production impact count = 12" in rag_prompt
    assert "CODE CHUNK 1" in rag_prompt
    assert "self.raw.close()" in rag_prompt

    non_rag_prompt = build_non_rag_prompt(mock_evidence["target"], "What is the impact?")
    assert "Response.close" in non_rag_prompt
    assert "CODE CHUNK" not in non_rag_prompt
    assert "DETERMINISTIC FACTS" not in non_rag_prompt

    # Test analyze_with_ollama deterministic fallback
    result = analyze_with_ollama(context, use_rag=True)
    assert result["mode"] == "rag"
    assert "Production impact entities" in result["answer"] or "12" in result["answer"]
    assert result["validation"]["status"] == "SUPPORTED"
    assert result["validation"]["validated"] is True
