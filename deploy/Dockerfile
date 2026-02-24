# Dockerfile for Wookiee services (Oleg bot/agent, Sheets Sync, etc.)
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install (single image used by multiple services)
COPY agents/oleg/requirements.txt /app/agents/oleg/requirements.txt
COPY services/sheets_sync/requirements.txt /app/services/sheets_sync/requirements.txt
RUN pip install --no-cache-dir \
    -r agents/oleg/requirements.txt \
    -r services/sheets_sync/requirements.txt

# Copy application code (shared libs + all agents + all services + scripts)
COPY shared/ /app/shared/
COPY agents/ /app/agents/
COPY services/ /app/services/
COPY scripts/ /app/scripts/
COPY deploy/healthcheck.py /app/deploy/healthcheck.py
COPY deploy/healthcheck_agent.py /app/deploy/healthcheck_agent.py

# Create data, logs, and reports directories
RUN mkdir -p /app/agents/oleg/data /app/agents/oleg/logs /app/reports \
    /app/agents/oleg_v2/data /app/agents/oleg_v2/logs

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Default command (overridden per-service in docker-compose.yml)
CMD ["python", "-m", "agents.oleg"]
