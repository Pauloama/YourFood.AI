# syntax=docker/dockerfile:1
FROM python:3.11-slim as runtime

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    MODEL_PATH=/app/artifacts \
    PORT=8000 \
    HOST=0.0.0.0

# Install system dependencies (curl for healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd --system appgroup && \
    useradd --system --gid appgroup --create-home --shell /bin/bash appuser

WORKDIR /app

# Install Python dependencies
COPY requirements-inference.txt .
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch && \
    pip install --no-cache-dir -r requirements-inference.txt

# Copy source code and configuration
COPY configs/ ./configs/
COPY src/ ./src/
COPY artifacts/ ./artifacts/

# Set ownership to appuser
RUN chown -R appuser:appgroup /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "absa.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
