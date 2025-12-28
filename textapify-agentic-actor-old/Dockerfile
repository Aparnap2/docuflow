# Use generic Python image
FROM python:3.11-slim

# Install system dependencies for Docling (OCR tools)
RUN apt-get update && apt-get install -y \
    libglib2.0-0 \
    tesseract-ocr \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /usr/src/app

# Install uv
RUN pip install --upgrade pip && pip install uv

# Copy requirements and install with uv
COPY requirements.txt ./
RUN uv pip install --system --compile-bytecode -r requirements.txt

# Copy source code
COPY . .

# Run the actor
CMD ["python3", "-m", "src.main"]