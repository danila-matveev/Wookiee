# Dockerfile for Wookiee services (cron jobs, Sheets Sync, etc.)
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    cron \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install (single image used by multiple services)
COPY services/sheets_sync/requirements.txt /app/services/sheets_sync/requirements.txt
RUN pip install --no-cache-dir \
    -r services/sheets_sync/requirements.txt

# Copy application code (shared libs + all services + scripts)
COPY shared/ /app/shared/
COPY services/ /app/services/
COPY scripts/ /app/scripts/

# Create reports directory
RUN mkdir -p /app/reports

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Default command (overridden per-service in docker-compose.yml)
CMD ["python", "--version"]
