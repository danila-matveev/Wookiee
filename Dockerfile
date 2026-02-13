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
COPY oleg_bot/requirements.txt /app/oleg_bot/requirements.txt
RUN pip install --no-cache-dir -r oleg_bot/requirements.txt

# Copy application code
COPY oleg_bot/ /app/oleg_bot/
COPY scripts/ /app/scripts/

# Create data, logs, and reports directories
RUN mkdir -p /app/oleg_bot/data /app/oleg_bot/logs /app/reports

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Run bot
CMD ["python", "-m", "oleg_bot.main"]
