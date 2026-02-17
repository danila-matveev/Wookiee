# Dockerfile for Wookiee Oleg Analytics Bot
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY agents/oleg/requirements.txt /app/agents/oleg/requirements.txt
RUN pip install --no-cache-dir -r agents/oleg/requirements.txt

# Copy application code
COPY shared/ /app/shared/
COPY agents/__init__.py /app/agents/__init__.py
COPY agents/oleg/ /app/agents/oleg/
COPY scripts/ /app/scripts/
COPY deploy/healthcheck.py /app/deploy/healthcheck.py
COPY deploy/healthcheck_agent.py /app/deploy/healthcheck_agent.py

# Create data, logs, and reports directories
RUN mkdir -p /app/agents/oleg/data /app/agents/oleg/logs /app/reports

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Run bot
CMD ["python", "-m", "agents.oleg"]
