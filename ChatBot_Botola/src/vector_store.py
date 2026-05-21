# chatbot-service/src/vector_store.py
import faiss
import numpy as np
import json
from pathlib import Path
from typing import List, Dict, Tuple
from .config import FAISS_INDEX_PATH, CHUNKS_PATH


class VectorStore:
    """FAISS-based vector store for document chunks."""
    
    def __init__(self, dimension: int):
        self.dimension = dimension
        self.index = None
        self.chunks: List[Dict] = []
    
    def build_index(self, embeddings: np.ndarray, chunks: List[Dict]):
        """Build a new FAISS index from embeddings."""
        self.chunks = chunks
        
        # Create IndexFlatIP for inner product (cosine similarity since vectors are normalized)
        self.index = faiss.IndexFlatIP(self.dimension)
        self.index.add(embeddings.astype(np.float32))
        
        print(f"Built index with {self.index.ntotal} vectors")
    
    def save(self, index_path: Path = FAISS_INDEX_PATH, chunks_path: Path = CHUNKS_PATH):
        """Save index and chunks to disk."""
        faiss.write_index(self.index, str(index_path))
        
        with open(chunks_path, "w", encoding="utf-8") as f:
            json.dump(self.chunks, f, ensure_ascii=False, indent=2)
        
        print(f"Saved index to {index_path}")
        print(f"Saved chunks to {chunks_path}")
    
    def load(self, index_path: Path = FAISS_INDEX_PATH, chunks_path: Path = CHUNKS_PATH):
        """Load index and chunks from disk."""
        self.index = faiss.read_index(str(index_path))
        
        with open(chunks_path, "r", encoding="utf-8") as f:
            self.chunks = json.load(f)
        
        print(f"Loaded index with {self.index.ntotal} vectors")
        print(f"Loaded {len(self.chunks)} chunks")
    
    def search(self, query_embedding: np.ndarray, k: int = 3) -> Tuple[List[Dict], List[float]]:
        """Search for k most similar chunks. Returns (chunks, scores)."""
        if self.index is None:
            raise RuntimeError("Index not built or loaded")
        
        # FAISS expects 2D array
        query = query_embedding.reshape(1, -1).astype(np.float32)
        scores, indices = self.index.search(query, k)
        
        # scores are inner products (higher = more similar)
        results = [self.chunks[i] for i in indices[0]]
        return results, scores[0].tolist()


# Quick test
if __name__ == "__main__":
    from embedder import Embedder
    from chunker import TextChunker
    from document_loader import DocumentLoader
    from config import RAW_DIR
    
    # Load → Chunk → Embed → Index
    loader = DocumentLoader()
    docs = loader.load_directory(RAW_DIR)
    
    chunker = TextChunker()
    chunks = chunker.chunk_all(docs)
    
    embedder = Embedder()
    texts = [c["text"] for c in chunks]
    embeddings = embedder.embed(texts)
    
    store = VectorStore(dimension=embedder.dimension)
    store.build_index(embeddings, chunks)
    store.save()
    
    # Test search
    store.load()  # Verify save/load works
    query = "Can I bring food to the stadium?"
    query_vec = embedder.embed_query(query)
    results, scores = store.search(query_vec, k=2)
    
    print(f"\nQuery: {query}")
    for r, s in zip(results, scores):
        print(f"\n[Score: {s:.3f}] {r['source']}")
        print(r['text'][:200])