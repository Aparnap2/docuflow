FROM python:3.11-slim

# Install system dependencies required by compression libraries (Pillow, pikepdf)
RUN apt-get update && apt-get install -y \
    libqpdf-dev \
    zlib1g-dev \
    libjpeg-dev \
    g++ \
    poppler-utils \
    tesseract-ocr \
    tesseract-ocr-eng \
    libgl1-mesa-glx \
    libgomp1 \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements
COPY requirements.txt pyproject.toml ./

# Install Python dependencies using uv
RUN pip install --no-cache-dir uv && \
    uv pip install --system --no-cache-dir -r requirements.txt

# Copy application code
COPY main.py ./
COPY utils/ ./utils/
COPY test_core.py ./
COPY README.md ./

# Create logs directory
RUN mkdir -p logs

# Expose port
EXPOSE 8000

# Set environment variables
ENV OLLAMA_BASE_URL=http://localhost:11434/v1
ENV PYTHONPATH=/app

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--timeout-keep-alive", "60"]