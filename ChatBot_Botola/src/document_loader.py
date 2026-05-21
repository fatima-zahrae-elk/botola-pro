# chatbot-service/src/document_loader.py
import PyPDF2
from pathlib import Path
from typing import List, Dict


class DocumentLoader:
    """Load documents from various formats into raw text."""
    
    SUPPORTED = {".pdf", ".txt", ".md"}
    
    def load(self, file_path: Path) -> Dict[str, str]:
        """Load a single file and return {filename: text}."""
        suffix = file_path.suffix.lower()
        
        if suffix not in self.SUPPORTED:
            raise ValueError(f"Unsupported format: {suffix}")
        
        if suffix == ".pdf":
            text = self._load_pdf(file_path)
        else:
            text = self._load_text(file_path)
            
        return {file_path.name: text}
    
    def load_directory(self, directory: Path) -> Dict[str, str]:
        """Load all supported files in a directory (recursively)."""
        documents = {}
        for file_path in directory.rglob("*"):
            if file_path.is_file() and file_path.suffix.lower() in self.SUPPORTED:
                try:
                    docs = self.load(file_path)
                    documents.update(docs)
                    print(f"[OK] Loaded: {file_path.name}")
                except Exception as e:
                    print(f"[ERROR] Failed: {file_path.name} -- {e}")
        return documents
    
    def _load_pdf(self, path: Path) -> str:
        text = ""
        with open(path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                text += page.extract_text() or ""
        return text.strip()
    
    def _load_text(self, path: Path) -> str:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()


# Quick test
if __name__ == "__main__":
    from .config import RAW_DIR
    loader = DocumentLoader()
    docs = loader.load_directory(RAW_DIR)
    print(f"\nLoaded {len(docs)} documents")
    for name, content in docs.items():
        print(f"\n--- {name} ---")
        print(content[:300] + "...")