import json
import os
from pathlib import Path
from typing import Any
import numpy as np


def get_indexes_dir() -> Path:
    env_path = os.getenv("INDEXES_DIR")
    if env_path:
        path = Path(env_path)
    elif Path("backend/data/indexes").exists() or Path("backend").exists():
        path = Path("backend/data/indexes")
    else:
        path = Path("data/indexes")
    path.mkdir(parents=True, exist_ok=True)
    return path


class VectorStore:
    def __init__(self, repository_name: str = ""):
        self.repository_name = repository_name
        self.chunks: list[dict[str, Any]] = []
        self.embeddings: np.ndarray | None = None  # shape (N, D), float32 normalized

    @property
    def count(self) -> int:
        return len(self.chunks)

    def add_documents(
        self,
        chunks: list[dict[str, Any]],
        embeddings: np.ndarray | list[list[float]],
    ) -> None:
        if not chunks:
            return

        if isinstance(embeddings, list):
            emb_array = np.array(embeddings, dtype=np.float32)
        else:
            emb_array = np.asarray(embeddings, dtype=np.float32)

        # Normalize to unit length for cosine similarity via dot product
        norms = np.linalg.norm(emb_array, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        emb_array = emb_array / norms

        if self.embeddings is None or len(self.embeddings) == 0:
            self.embeddings = emb_array
            self.chunks = list(chunks)
        else:
            self.embeddings = np.vstack([self.embeddings, emb_array])
            self.chunks.extend(chunks)

    def similarity_search(
        self,
        query_vector: np.ndarray | list[float],
        top_k: int = 5,
        filter_dict: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        if self.embeddings is None or len(self.chunks) == 0:
            return []

        q_vec = np.asarray(query_vector, dtype=np.float32)
        if q_vec.ndim == 2:
            q_vec = q_vec[0]

        q_norm = np.linalg.norm(q_vec)
        if q_norm > 0:
            q_vec = q_vec / q_norm

        # Cosine similarity is dot product of normalized vectors
        scores = np.dot(self.embeddings, q_vec)

        # Apply filtering if provided
        candidate_indices = range(len(self.chunks))
        if filter_dict:
            filtered = []
            for idx in candidate_indices:
                chunk = self.chunks[idx]
                meta = chunk.get("metadata", chunk)
                match = True
                for k, v in filter_dict.items():
                    if meta.get(k) != v:
                        match = False
                        break
                if match:
                    filtered.append(idx)
            candidate_indices = filtered

        if not candidate_indices:
            return []

        # Sort indices by score descending
        sorted_indices = sorted(
            candidate_indices,
            key=lambda idx: float(scores[idx]),
            reverse=True,
        )

        results = []
        for idx in sorted_indices[:top_k]:
            chunk_copy = dict(self.chunks[idx])
            chunk_copy["similarity_score"] = float(round(float(scores[idx]), 4))
            results.append(chunk_copy)

        return results

    def save(self, file_prefix: str | Path | None = None) -> None:
        if not file_prefix:
            idx_dir = get_indexes_dir()
            safe_name = (self.repository_name or "repo").replace("/", "_").replace("\\", "_")
            file_prefix = idx_dir / safe_name
        else:
            file_prefix = Path(file_prefix)

        data_json = file_prefix.with_suffix(".json")
        emb_npy = file_prefix.with_suffix(".npy")

        with open(data_json, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "repository_name": self.repository_name,
                    "chunks": self.chunks,
                },
                f,
                indent=2,
            )

        if self.embeddings is not None:
            np.save(emb_npy, self.embeddings)

    def load(self, file_prefix: str | Path | None = None) -> bool:
        if not file_prefix:
            idx_dir = get_indexes_dir()
            safe_name = (self.repository_name or "repo").replace("/", "_").replace("\\", "_")
            file_prefix = idx_dir / safe_name
        else:
            file_prefix = Path(file_prefix)

        data_json = file_prefix.with_suffix(".json")
        emb_npy = file_prefix.with_suffix(".npy")

        if not data_json.exists() or not emb_npy.exists():
            return False

        try:
            with open(data_json, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.repository_name = data.get("repository_name", self.repository_name)
                self.chunks = data.get("chunks", [])

            self.embeddings = np.load(emb_npy)
            return True
        except Exception:
            return False
