FROM python:3.10-slim

WORKDIR /app

# System deps: libgomp1 is required by faiss-cpu
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy chatbot source into /app
COPY ChatBot_Botola/ .

# Install Python deps (numpy first to ensure correct version before faiss-cpu)
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir "numpy==1.26.4" \
 && pip install --no-cache-dir -r requirements.txt

# Ensure data dirs exist (FAISS index + chunks already in ChatBot_Botola/data/)
RUN mkdir -p data/raw data/processed

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV LLM_PROVIDER=mistral
ENV MISTRAL_MODEL=mistral-medium
ENV USE_LOCAL_EMBEDDER=false
ENV ALLOWED_ORIGINS=https://fatima-zahrae-elk.github.io,https://fatima-zahrae-elk-botola-pro-api.hf.space,http://localhost:5500,http://127.0.0.1:5500,http://localhost:8000

# PORT is injected by Render at runtime; default 7860 for HuggingFace Spaces
EXPOSE 7860
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-7860}
