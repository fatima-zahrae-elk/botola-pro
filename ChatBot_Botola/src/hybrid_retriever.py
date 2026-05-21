# chatbot-service/src/hybrid_retriever.py
"""
Hybrid BM25 + FAISS retriever with Reciprocal Rank Fusion (RRF).

Why hybrid?
- FAISS (semantic): catches conceptual similarity — "can I enter with a bag?"
- BM25  (keyword) : catches exact terms  — "Zone 04", "WAC", "TS-98201"
- RRF merges both without needing to tune score scales.
"""
from typing import List, Dict, Tuple

import numpy as np

from .logger import get_logger

logger = get_logger(__name__)

# RRF constant — standard value, rarely needs changing
RRF_K = 60


class HybridRetriever:
    """
    Combines BM25 keyword search with FAISS semantic search.
    Falls back to FAISS-only if rank_bm25 is not installed.
    """

    def __init__(self, chunks: List[Dict], vector_store, embedder):
        self.chunks = chunks
        self.vector_store = vector_store
        self.embedder = embedder
        self.bm25 = None
        self._build_bm25(chunks)

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _build_bm25(self, chunks: List[Dict]):
        try:
            from rank_bm25 import BM25Okapi
            tokenized = [self._tokenize(c["text"]) for c in chunks]
            self.bm25 = BM25Okapi(tokenized)
            logger.info("BM25 index built", extra={"num_chunks": len(chunks)})
        except ImportError:
            logger.warning("rank_bm25 not installed — falling back to FAISS-only retrieval")

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        """Simple whitespace+lowercase tokenizer."""
        return text.lower().split()

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(self, query: str, k: int = 5,
               min_score: float = 0.35) -> List[Dict]:
        """
        Hybrid search: BM25 + FAISS merged via RRF.

        Args:
            query:     User query (optionally rewritten with history context).
            k:         Number of results to return after fusion.
            min_score: Minimum FAISS cosine similarity to include a chunk.

        Returns:
            Up to `k` chunks sorted by descending RRF score.
        """
        # ---- FAISS semantic search (retrieve 2× for reranking headroom) ----
        query_vec = self.embedder.embed_query(query)
        faiss_chunks, faiss_scores = self.vector_store.search(query_vec, k=k * 2)

        # Filter by minimum semantic score
        faiss_results = [
            (chunk, score)
            for chunk, score in zip(faiss_chunks, faiss_scores)
            if score >= min_score
        ]

        if not faiss_results:
            logger.info("No FAISS results above threshold — using BM25-only fallback",
                        extra={"threshold": min_score, "query": query[:80]})
            return self._bm25_only_search(query, k)

        # ---- BM25 keyword search ----
        bm25_ranking: Dict[str, int] = {}  # chunk_id → BM25 rank
        if self.bm25 is not None:
            tokens = self._tokenize(query)
            bm25_scores = self.bm25.get_scores(tokens)
            # Rank all chunks by BM25 score (desc)
            bm25_order = np.argsort(bm25_scores)[::-1]
            for rank, idx in enumerate(bm25_order):
                chunk_id = self.chunks[idx]["id"]
                bm25_ranking[chunk_id] = rank  # 0 = best

        # ---- Reciprocal Rank Fusion ----
        rrf_scores: Dict[str, float] = {}
        chunk_map: Dict[str, Dict] = {}

        # FAISS ranks
        for faiss_rank, (chunk, _) in enumerate(faiss_results):
            cid = chunk["id"]
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + 1.0 / (RRF_K + faiss_rank + 1)
            chunk_map[cid] = chunk

        # BM25 ranks (only for chunks already in FAISS results)
        for cid in chunk_map:
            if cid in bm25_ranking:
                bm25_rank = bm25_ranking[cid]
                rrf_scores[cid] += 1.0 / (RRF_K + bm25_rank + 1)

        # Sort by RRF score
        ranked = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
        results = []
        for cid, rrf_score in ranked[:k]:
            chunk = dict(chunk_map[cid])
            chunk["rrf_score"] = round(rrf_score, 6)
            results.append(chunk)

        logger.info("Hybrid search complete", extra={
            "query": query[:80],
            "faiss_candidates": len(faiss_results),
            "final_results": len(results),
        })
        return results

    def _bm25_only_search(self, query: str, k: int) -> List[Dict]:
        """Pure BM25 search — used when FAISS is disabled or returns no results."""
        if self.bm25 is None:
            logger.warning("BM25 not available — cannot retrieve context")
            return []

        tokens = self._tokenize(query)
        scores = self.bm25.get_scores(tokens)
        top_indices = np.argsort(scores)[::-1][:k]

        results = []
        for idx in top_indices:
            if scores[idx] > 0:
                chunk = dict(self.chunks[idx])
                chunk["bm25_score"] = round(float(scores[idx]), 4)
                results.append(chunk)

        logger.info("BM25-only search complete", extra={
            "query": query[:80],
            "results": len(results),
        })
        return results
