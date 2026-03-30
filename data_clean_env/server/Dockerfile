FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends git curl && \
    rm -rf /var/lib/apt/lists/*

# Copy project files
COPY . /app/env
WORKDIR /app/env

# Install Python dependencies
RUN pip install --no-cache-dir \
    "openenv-core>=0.2.3" \
    "fastapi>=0.115.0" \
    "pydantic>=2.0.0" \
    "uvicorn>=0.24.0" \
    "requests>=2.31.0" \
    "openai>=1.0.0"

# Set Python path so imports work
ENV PYTHONPATH="/app/env:$PYTHONPATH"

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

EXPOSE 8000

CMD ["uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "8000"]
