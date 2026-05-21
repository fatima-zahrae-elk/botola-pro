# chatbot-service/src/rag_engine.py
"""
Static RAG Pipeline for Botola Pro Chatbot.

Improvements over v1:
- Minimum similarity score threshold: chunks below MIN_SCORE are filtered out
  so the LLM never receives irrelevant context.
- Hybrid retrieval (BM25 + FAISS) when rank_bm25 is installed.
- Cross-encoder reranking step before injecting context into the LLM prompt.
- Exposes `has_context` flag so the orchestrator can fall back gracefully.
"""
from typing import List, Dict, Optional
from pathlib import Path

from .config import RAW_DIR, TOP_K
from .document_loader import DocumentLoader
from .chunker import TextChunker
from .embedder import Embedder
from .vector_store import VectorStore
from .hybrid_retriever import HybridRetriever
from .reranker import CrossEncoderReranker
from .logger import get_logger

logger = get_logger(__name__)

# Minimum cosine similarity score to include a chunk in the LLM context.
# Chunks below this threshold are considered irrelevant and dropped.
MIN_SIMILARITY_SCORE: float = 0.40


class RAGEngine:
    """
    Static RAG Pipeline for Botola Pro Chatbot.

    Usage:
        engine = RAGEngine()
        engine.build()            # One-time setup
        result = engine.answer("Can I bring a bag?")
        if result["has_context"]:
            # use result["context"] in LLM prompt
        else:
            # fallback: tell user we don't have that info
    """

    def __init__(self):
        self.embedder = Embedder()
        self.store = VectorStore(dimension=self.embedder.dimension)
        self.reranker = CrossEncoderReranker()
        self.hybrid: Optional[HybridRetriever] = None
        self.is_ready = False

    # ------------------------------------------------------------------
    # Build / Load
    # ------------------------------------------------------------------

    def build(self, force_rebuild: bool = False):
        """
        Build the RAG pipeline from documents in data/raw/.
        Call this once during setup or whenever documents change.
        """
        if not force_rebuild and self._index_exists():
            logger.info("Existing index found — loading from disk")
            self.load()
            return

        logger.info("Building RAG pipeline from scratch")

        # 1. Load documents
        loader = DocumentLoader()
        docs = loader.load_directory(RAW_DIR)
        if not docs:
            raise RuntimeError(f"No documents found in {RAW_DIR}")

        # 2. Chunk (sentence-aware)
        chunker = TextChunker()
        chunks = chunker.chunk_all(docs)

        # 3. Embed
        texts = [c["text"] for c in chunks]
        embeddings = self.embedder.embed(texts)

        # 4. Index in FAISS
        self.store.build_index(embeddings, chunks)
        self.store.save()

        # 5. Build hybrid retriever
        self.hybrid = HybridRetriever(chunks, self.store, self.embedder)

        self.is_ready = True
        logger.info("RAG pipeline built", extra={"num_chunks": len(chunks)})

    def load(self):
        """Load pre-built FAISS index from disk."""
        if not self._index_exists():
            raise RuntimeError("No index found. Run build() first.")

        self.store.load()
        # Rebuild hybrid retriever from loaded chunks
        self.hybrid = HybridRetriever(self.store.chunks, self.store, self.embedder)
        self.is_ready = True
        logger.info("RAG pipeline loaded", extra={"num_chunks": len(self.store.chunks)})

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    def retrieve(self, query: str, k: int = TOP_K) -> List[Dict]:
        """
        Retrieve relevant chunks for a query.

        Pipeline:
            query → hybrid search (BM25 + FAISS) → score filter → reranker
        
        Returns:
            List of chunk dicts, each with keys: id, text, source, score / rrf_score
        """
        if not self.is_ready:
            raise RuntimeError("Engine not ready. Call build() or load() first.")

        # --- Hybrid search (returns 2×k for reranker headroom) ---
        if self.hybrid:
            candidates = self.hybrid.search(
                query,
                k=k * 2,
                min_score=MIN_SIMILARITY_SCORE
            )
        else:
            # Pure FAISS fallback (e.g. HybridRetriever failed to init)
            query_vec = self.embedder.embed_query(query)
            raw_chunks, raw_scores = self.store.search(query_vec, k=k * 2)
            candidates = []
            for chunk, score in zip(raw_chunks, raw_scores):
                if score >= MIN_SIMILARITY_SCORE:
                    chunk = dict(chunk)
                    chunk["score"] = round(score, 4)
                    candidates.append(chunk)

        if not candidates:
            logger.info("No relevant chunks found", extra={"query": query[:80]})
            return []

        # --- Cross-encoder reranking ---
        reranked = self.reranker.rerank(query, candidates, top_k=k)
        return reranked

    def answer(self, query: str, k: int = TOP_K) -> Dict:
        """
        Full RAG response with context formatted for LLM prompt injection.

        Returns:
            {
                "query":       str,
                "context":     str,   # formatted for prompt
                "chunks":      list,
                "sources":     list,
                "has_context": bool,  # False → no relevant docs found
            }
        """
        chunks = self.retrieve(query, k=k)

        has_context = bool(chunks)

        context_text = "\n\n---\n\n".join([
            f"[Source: {c['source']}]\n{c['text']}"
            for c in chunks
        ]) if has_context else ""

        return {
            "query":       query,
            "context":     context_text,
            "chunks":      chunks,
            "sources":     list({c["source"] for c in chunks}),
            "has_context": has_context,
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _index_exists(self) -> bool:
        from .config import FAISS_INDEX_PATH, CHUNKS_PATH
        return FAISS_INDEX_PATH.exists() and CHUNKS_PATH.exists()


# ---------------------------------------------------------------------------
# Quick test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    engine = RAGEngine()

    if engine._index_exists():
        engine.load()
    else:
        engine.build()

    test_queries = [
        "Can I bring a bag to the stadium?",
        "À quelle heure ouvrent les portes ?",
        "متى يفتح الملعب؟",
        "Where is WAC playing?",        # should find something
        "What are the asteroid mining rights?",  # should return has_context=False
    ]

    for q in test_queries:
        print(f"\n{'='*50}")
        print(f"Query: {q}")
        result = engine.answer(q)
        print(f"Has context: {result['has_context']} | Sources: {result['sources']}")
        if result["chunks"]:
            top = result["chunks"][0]
            score = top.get("rerank_score") or top.get("rrf_score") or top.get("score", "?")
            print(f"Top chunk score: {score}")
            print(f"Top chunk: {top['text'][:200]}...")