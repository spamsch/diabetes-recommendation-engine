# Dockerfile for Dexcom Glucose Monitoring System
# This creates a container that runs the glucose monitoring server

# Use Python 3.11 slim image for smaller size
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Set working directory
WORKDIR /app

# Install system dependencies needed for the application
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better Docker layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application source code
COPY src/ ./src/
COPY run_monitor.py .
COPY graph_generator.py .

# Create necessary directories
RUN mkdir -p /app/data /app/logs

# Copy configuration template (users need to mount their own .env)
COPY .env.example .

# Create a non-root user for security
RUN groupadd -r glucose && useradd -r -g glucose glucose

# Create data directory and set permissions
RUN chown -R glucose:glucose /app

# Switch to non-root user
USER glucose

# Expose port (if the app had a web interface)
# EXPOSE 8080

# Health check command
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import sqlite3; conn = sqlite3.connect('/app/data/glucose_monitor.db', timeout=5); conn.close()" || exit 1

# Default environment variables that can be overridden
ENV DATABASE_PATH="/app/data/glucose_monitor.db" \
    LOG_LEVEL="INFO" \
    ENABLE_TERMINAL_OUTPUT="false" \
    POLL_INTERVAL_MINUTES="5"

# Volume for persistent data
VOLUME ["/app/data", "/app/logs"]

# Default command - runs the monitor with mock data (safer default)
# Users should override with real credentials via environment variables
CMD ["python", "-m", "src.main", "--mock", "--log-level", "INFO"]

# Alternative entry points (can be used with docker run):
# 
# Real monitoring with credentials:
# docker run -e DEXCOM_USERNAME=user -e DEXCOM_PASSWORD=pass glucose-monitor python -m src.main
#
# Generate graphs:
# docker run glucose-monitor python graph_generator.py --type timeline --hours 24
#
# Run tests:
# docker run glucose-monitor python run_monitor.py --test-recs
#
# Interactive shell:
# docker run -it glucose-monitor bash

# Labels for metadata
LABEL maintainer="Glucose Monitor" \
      description="Dexcom glucose monitoring system with Telegram notifications" \
      version="1.0" \
      org.label-schema.name="glucose-monitor" \
      org.label-schema.description="Automated glucose monitoring and analysis system" \
      org.label-schema.vcs-url="https://github.com/spamsch/diabetes-recommendation-engine" \
      org.label-schema.schema-version="1.0"