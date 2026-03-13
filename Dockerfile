FROM python:3.11-slim

# System dependencies: Tesseract + German language pack
RUN apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-deu \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install CPU-only PyTorch first (keeps image smaller than the default GPU build)
RUN pip install --no-cache-dir \
        torch==2.3.1+cpu \
        --extra-index-url https://download.pytorch.org/whl/cpu

# Install remaining Python dependencies (sentence-transformers picks up the
# CPU torch installed above instead of pulling the GPU variant)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source and install the pipeline package
COPY pyproject.toml .
COPY src/ src/
RUN pip install --no-cache-dir -e .

# Pre-download the multilingual embedding model so the container works offline
RUN python - <<'EOF'
from sentence_transformers import SentenceTransformer
SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
print("Model cached.")
EOF

# Pipeline data lives in a mounted volume at runtime
ENV PIPELINE_BASE_DIR=/pipeline
ENV PIPELINE_ENABLE_RAG=true

EXPOSE 8501

CMD ["streamlit", "run", "src/doc_pipeline/ui.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=true", \
     "--browser.gatherUsageStats=false"]
