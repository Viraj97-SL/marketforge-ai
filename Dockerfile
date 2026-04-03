# MarketForge AI — Production Dockerfile
FROM python:3.11-slim AS base

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . .

RUN pip install --no-cache-dir -e .

# Download spaCy model and sentence-transformers model at build time
# (avoids cold-start delays on Railway)
RUN python -m spacy download en_core_web_sm || echo "[WARN] spaCy model unavailable"
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')" \
    || echo "[WARN] SBERT model unavailable"

# Bootstrap DB (idempotent — safe to run on every start)
RUN python scripts/bootstrap.py || echo "[WARN] Bootstrap failed — will retry on first request"

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
