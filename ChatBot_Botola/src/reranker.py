# chatbot-service/src/reranker.py
"""
Cross-encoder reranker for RAG results.
Uses a lightweight cross-encoder to re-score and reorder retrieved chunks
before injecting them into the LLM prompt.
"""
from typing import List, Dict

from .logger import get_logger

logger = get_logger(__name__)

# Model name — small, fast, works well for passage reranking
RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"


class CrossEncoderReranker:
    """
    Reranks RAG chunks using a cross-encoder model.
    The cross-encoder jointly encodes (query, passage) pairs, giving much
    better relevance scores than bi-encoder cosine similarity alone.
    """

    def __init__(self):
        self._model = None  # lazy-loaded on first use

    def _load(self):
        if self._model is None:
            try:
                from sentence_transformers import CrossEncoder
                self._model = CrossEncoder(RERANKER_MODEL)
                logger.info("Reranker loaded", extra={"model": RERANKER_MODEL})
            except Exception as e:
                logger.warning("Reranker unavailable, skipping rerank step",
                               extra={"error": str(e)})

    def rerank(self, query: str, chunks: List[Dict], top_k: int = 3) -> List[Dict]:
        """
        Rerank chunks by cross-encoder score.

        Args:
            query:  The user's (possibly rewritten) query.
            chunks: Retrieved chunks from the vector store.
            top_k:  How many top chunks to return after reranking.

        Returns:
            Up to `top_k` chunks sorted by descending cross-encoder score.
        """
        if not chunks:
            return chunks

        self._load()
        if self._model is None:
            # Reranker unavailable — return as-is
            return chunks[:top_k]

        pairs = [(query, c["text"]) for c in chunks]
        scores = self._model.predict(pairs)

        scored = sorted(zip(scores, chunks), key=lambda x: x[0], reverse=True)
        reranked = []
        for score, chunk in scored[:top_k]:
            chunk = dict(chunk)  # don't mutate original
            chunk["rerank_score"] = round(float(score), 4)
            reranked.append(chunk)

        logger.info("Reranking complete",
                    extra={"input_chunks": len(chunks), "output_chunks": len(reranked)})
        return reranked
