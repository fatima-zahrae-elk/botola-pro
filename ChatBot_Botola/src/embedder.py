# chatbot-service/src/embedder.py
import numpy as np
from sentence_transformers import SentenceTransformer
from typing import List
from .config import EMBEDDING_MODEL


class Embedder:
    """Generate embeddings for text using sentence-transformers."""
    
    def __init__(self, model_name: str = EMBEDDING_MODEL):
        print(f"Loading embedding model: {model_name}")
        self.model = SentenceTransformer(model_name)
        self.dimension = self.model.get_sentence_embedding_dimension()
        print(f"Model loaded. Embedding dimension: {self.dimension}")
    
    def embed(self, texts: List[str]) -> np.ndarray:
        """Embed a list of texts into vectors."""
        # Normalize embeddings for cosine similarity
        embeddings = self.model.encode(texts, normalize_embeddings=True)
        return embeddings
    
    def embed_query(self, text: str) -> np.ndarray:
        """Embed a single query."""
        return self.embed([text])[0]


# Quick test
if __name__ == "__main__":
    embedder = Embedder()
    
    test_texts = [
        "Les portes du stade ouvrent 2 heures avant le match.",
        "Can I bring a backpack to the stadium?",
        "متى تفتح بوابات الملعب؟"  # Arabic: "When do stadium gates open?"
    ]
    
    embeddings = embedder.embed(test_texts)
    print(f"\nEmbedded {len(test_texts)} texts")
    print(f"Shape: {embeddings.shape}")
    print(f"First 5 dims of Arabic text: {embeddings[2][:5]}")