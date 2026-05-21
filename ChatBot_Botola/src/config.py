# chatbot-service/src/config.py
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Base paths
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
SCRIPTS_DIR = BASE_DIR / "scripts"

# Ensure directories exist
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

# Database
DATABASE_URL = f"sqlite:///{DATA_DIR / 'botola_pro.db'}"

# Model settings
EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

# Chunking settings
CHUNK_SIZE = 512
CHUNK_OVERLAP = 128

# Retrieval settings
TOP_K = 3

# FAISS index file
FAISS_INDEX_PATH = PROCESSED_DIR / "faiss_index.bin"
CHUNKS_PATH = PROCESSED_DIR / "chunks.json"

# Redis
REDIS_URL = os.getenv("REDIS_URL", "")


# Intent classification thresholds
STATIC_INTENTS = {
    "faq", "bag_policy", "gate_time", "prohibited_items", 
    "food_policy", "parking", "accessibility", "general_info", "smalltalk"

}

DYNAMIC_INTENTS = {
    "seat_location", "ticket_status", "ticket_verification",
    "my_tickets", "match_time", "match_status", "price_check",
    "transfer_ticket", "refund_status", "payment_status", "buy_ticket"
}

# Confidence threshold for routing to human
CONFIDENCE_THRESHOLD = 0.4


# LLM Configuration
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama")  # ollama | mistral | openrouter

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "mistral:7b")

MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "")
MISTRAL_MODEL = os.getenv("MISTRAL_MODEL", "mistral-medium")

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "mistralai/mistral-7b-instruct")

# Generation settings
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "512"))
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.3"))

# Conversation memory
CONVERSATION_TURNS = 5  # Keep last N turns
SESSION_TIMEOUT = 3600  # 1 hour

# Guardrails
FORBIDDEN_TOPICS = ["betting", "gambling", "odds", "wager"]
REQUIRED_DISCLAIMERS = {
    "medical": "This is not medical advice. Consult stadium medical staff.",
    "legal": "For legal matters, contact Botola Pro support directly."
}