FROM python:3.11-slim

# System dependencies: Tesseract + German language pack
RUN apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-deu \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first (better layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY pyproject.toml .
COPY src/ src/
RUN pip install --no-cache-dir -e .

# Pipeline data lives in a mounted volume at runtime
ENV PIPELINE_BASE_DIR=/pipeline

EXPOSE 8501

CMD ["streamlit", "run", "src/doc_pipeline/ui.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=true", \
     "--browser.gatherUsageStats=false"]
