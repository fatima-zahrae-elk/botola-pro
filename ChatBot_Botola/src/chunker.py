# chatbot-service/src/chunker.py
"""
Sentence-aware text chunker.

Improvement over the old character-split approach:
- Splits on sentence boundaries (period, ?, !, newline) so chunks are
  always semantically complete.
- Uses a sliding window of whole sentences to create overlap, preserving
  cross-sentence context without cutting words in half.
- Keeps structured list items (lines starting with -, ✓, ✗, Q:, A:, •)
  together when possible.
"""
import re
from typing import List, Dict

from .config import CHUNK_SIZE, CHUNK_OVERLAP
from .logger import get_logger

logger = get_logger(__name__)

# Regex to split text into sentences / meaningful units
_SENTENCE_SPLIT = re.compile(
    r'(?<=[.!?])\s+|(?<=\n)\s*(?=[-✓✗•Q])|(?<=\n{2})'
)


class TextChunker:
    """
    Split documents into semantically meaningful, overlapping chunks.

    Strategy
    --------
    1. Split document into "units" (sentences or list items).
    2. Greedily fill a chunk up to `chunk_size` characters.
    3. When the chunk is full, save it and start a new one
       with the last `overlap_units` units as context seed.
    """

    def __init__(
        self,
        chunk_size: int = CHUNK_SIZE,
        overlap: int = CHUNK_OVERLAP,
        overlap_units: int = 2,
    ):
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.overlap_units = overlap_units

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def chunk_document(self, doc_name: str, text: str) -> List[Dict]:
        """Split a single document into sentence-aware chunks with metadata."""
        units = self._split_units(text)
        if not units:
            return []

        chunks: List[Dict] = []
        current_units: List[str] = []
        current_len: int = 0

        for unit in units:
            unit_len = len(unit)

            # If adding this unit would exceed the limit AND we already
            # have content, flush the current chunk first.
            if current_len + unit_len > self.chunk_size and current_units:
                chunk_text = " ".join(current_units).strip()
                if chunk_text:
                    chunks.append(self._make_chunk(doc_name, chunk_text, len(chunks)))

                # Seed the next chunk with the last N units (overlap)
                current_units = current_units[-self.overlap_units:]
                current_len = sum(len(u) for u in current_units)

            current_units.append(unit)
            current_len += unit_len

        # Flush remaining
        if current_units:
            chunk_text = " ".join(current_units).strip()
            if chunk_text:
                chunks.append(self._make_chunk(doc_name, chunk_text, len(chunks)))

        logger.info("Document chunked",
                    extra={"doc": doc_name, "chunks": len(chunks)})
        return chunks

    def chunk_all(self, documents: Dict[str, str]) -> List[Dict]:
        """Chunk all documents and return a flat list."""
        all_chunks: List[Dict] = []
        for doc_name, text in documents.items():
            doc_chunks = self.chunk_document(doc_name, text)
            all_chunks.extend(doc_chunks)
            print(f"  {doc_name}: {len(doc_chunks)} chunks")
        return all_chunks

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _split_units(text: str) -> List[str]:
        """
        Split text into meaningful units (sentences / list items).
        Preserves newline-separated blocks (e.g. FAQ Q&A pairs).
        """
        # Normalise line endings
        text = text.replace("\r\n", "\n").replace("\r", "\n")

        # Split on: end-of-sentence punctuation OR double newline OR list markers
        raw_units = re.split(r'(?<=[.!?])\s+|\n{2,}', text)

        units: List[str] = []
        for raw in raw_units:
            raw = raw.strip()
            if not raw:
                continue
            # If the unit is still very long (e.g. a dense paragraph),
            # split further on single newlines
            if len(raw) > 600:
                sub_units = [s.strip() for s in raw.split("\n") if s.strip()]
                units.extend(sub_units)
            else:
                units.append(raw)

        return units

    @staticmethod
    def _make_chunk(doc_name: str, text: str, idx: int) -> Dict:
        return {
            "id": f"{doc_name}_chunk_{idx}",
            "text": text,
            "source": doc_name,
            "chunk_index": idx,
        }


# ---------------------------------------------------------------------------
# Quick test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    from src.document_loader import DocumentLoader
    from src.config import RAW_DIR

    loader = DocumentLoader()
    docs = loader.load_directory(RAW_DIR)

    chunker = TextChunker()
    chunks = chunker.chunk_all(docs)
    print(f"\nTotal chunks: {len(chunks)}")
    print(f"\nFirst chunk:\n{chunks[0]['text']}")
    print(f"\nLast chunk:\n{chunks[-1]['text']}")