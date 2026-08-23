FROM python:3.11-slim

# Install system dependencies (git is required for GitPython repository analysis)
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy and install python dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . /app/

# Environment defaults
ENV PYTHONUNBUFFERED=1
ENV OLLAMA_BASE_URL=http://host.docker.internal:11434
ENV OLLAMA_MODEL=codellama:7b
ENV EMBEDDING_MODEL=all-MiniLM-L6-v2
ENV REPOSITORIES_DIR=/app/data/repos
ENV INDEXES_DIR=/app/data/indexes

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
