FROM python:3.10-slim

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy ChatBot_Botola contents into /app
COPY ChatBot_Botola/ .

# Fix numpy version before installing (faiss-cpu 1.7.4 requires numpy<2)
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir "numpy==1.26.4" && \
    pip install --no-cache-dir -r requirements.txt

# Pre-download AI models at build time (baked into image — no download on startup)
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')"
RUN python -c "from sentence_transformers import CrossEncoder; CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')"

# Ensure data dirs exist (FAISS index + chunks are already copied from ChatBot_Botola/data/)
RUN mkdir -p data/raw data/processed

# Non-sensitive defaults — override MISTRAL_API_KEY via Space Secrets
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV LLM_PROVIDER=mistral
ENV MISTRAL_MODEL=mistral-medium
ENV ALLOWED_ORIGINS=https://fatima-zahrae-elk.github.io,https://fatima-zahrae-elk-botola-pro-api.hf.space,http://localhost:5500,http://127.0.0.1:5500,http://localhost:8000

# HuggingFace Spaces listens on port 7860
EXPOSE 7860

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]
