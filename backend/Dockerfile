FROM python:3.11-slim

WORKDIR /app

# System dependencies: PostGIS client libs, build tools, curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    git \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Install a lighter runtime dependency set for Docker.
# Heavy ML extras fall back gracefully in the app when unavailable.
COPY requirements.docker.txt .
RUN pip install --no-cache-dir --retries 10 --timeout 120 -r requirements.docker.txt

# Copy application code
COPY . .

# Patch twscrape to support X's new JS bundling format (2025+)
RUN python patch_twscrape.py

# Development command (hot-reload). Override in docker-compose for prod or Celery.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
