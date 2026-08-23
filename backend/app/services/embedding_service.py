from functools import lru_cache
import os
from typing import Sequence
import numpy as np


DEFAULT_EMBEDDING_MODEL = "all-MiniLM-L6-v2"


class EmbeddingService:
    def __init__(self, model_name: str | None = None):
        self.model_name = model_name or os.getenv(
            "EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL
        )
        self._model = None

    def _get_model(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(self.model_name)
            except Exception as exc:
                raise RuntimeError(
                    f"Failed to load embedding model '{self.model_name}': {exc}"
                ) from exc
        return self._model

    def generate_embeddings(self, texts: Sequence[str]) -> np.ndarray:
        if not texts:
            return np.empty((0, 384), dtype=np.float32)

        model = self._get_model()
        embeddings = model.encode(
            list(texts),
            convert_to_numpy=True,
            show_progress_bar=False,
            normalize_embeddings=True,
        )
        return embeddings.astype(np.float32)

    def generate_query_embedding(self, query: str) -> np.ndarray:
        embeddings = self.generate_embeddings([query])
        return embeddings[0]


@lru_cache(maxsize=1)
def get_embedding_service(model_name: str | None = None) -> EmbeddingService:
    return EmbeddingService(model_name=model_name)


def embed_texts(texts: Sequence[str]) -> list[list[float]]:
    service = get_embedding_service()
    array = service.generate_embeddings(texts)
    return array.tolist()


def embed_query(query: str) -> list[float]:
    service = get_embedding_service()
    vector = service.generate_query_embedding(query)
    return vector.tolist()
