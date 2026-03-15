FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY backend/pyproject.toml backend/README.md ./
RUN pip install --no-cache-dir -e ".[dev]"

# Copy application code
COPY backend/ .

# Create uploads directory
RUN mkdir -p /app/uploads

# Default command
CMD ["celery", "-A", "app.workers.celery_app", "worker", "--loglevel=info"]
