# chatbot-service/src/embedder.py
"""
Lightweight embedder with optional local model loading.

Set USE_LOCAL_EMBEDDER=true to load the full sentence-transformers model
(requires ~500MB RAM). Default is lightweight mode (BM25 fallback handles retrieval).
"""
import os
import numpy as np
from typing import List


class Embedder:
    """
    Generates embeddings for text.

    In lightweight mode (default):
        Returns zero vectors — FAISS cosine similarity = 0 → filtered by
        min_score threshold → HybridRetriever falls back to BM25-only.
        RAM cost: ~0 MB (no model loaded).

    In full mode (USE_LOCAL_EMBEDDER=true):
        Loads sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2.
        RAM cost: ~450 MB (includes PyTorch).
    """

    def __init__(self, model_name: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"):
        self.dimension = 384   # paraphrase-multilingual-MiniLM-L12-v2 outputs 384 dims
        self.model = None

        if os.getenv("USE_LOCAL_EMBEDDER", "false").lower() == "true":
            try:
                from sentence_transformers import SentenceTransformer
                print(f"Loading embedding model: {model_name}")
                self.model = SentenceTransformer(model_name)
                self.dimension = self.model.get_sentence_embedding_dimension()
                print(f"Model loaded. Embedding dimension: {self.dimension}")
            except ImportError:
                print("sentence-transformers not installed — using BM25-only mode")
        else:
            print("Lightweight mode active: BM25 handles retrieval (no local embedding model)")

    def embed(self, texts: List[str]) -> np.ndarray:
        """Embed a list of texts."""
        if self.model is not None:
            return self.model.encode(texts, normalize_embeddings=True)
        # Zero vectors → FAISS cosine score = 0 → filtered by min_score → BM25 fallback kicks in
        return np.zeros((len(texts), self.dimension), dtype=np.float32)  # shape: (n, 384)

    def embed_query(self, text: str) -> np.ndarray:
        """Embed a single query."""
        if self.model is not None:
            return self.embed([text])[0]
        return np.zeros(self.dimension, dtype=np.float32)
