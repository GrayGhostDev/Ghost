# Multi-stage build for Ghost Backend Framework
# Stage 1: Builder
FROM python:3.12-slim as builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy and install requirements
WORKDIR /tmp
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# Stage 2: Runtime
FROM python:3.12-slim

# Install runtime dependencies only
RUN apt-get update && apt-get install -y \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r ghost && useradd -r -g ghost -m -d /home/ghost -s /bin/bash ghost

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Set working directory
WORKDIR /app

# Copy application code (respects .dockerignore)
COPY --chown=ghost:ghost . .

# Create necessary directories with correct permissions
RUN mkdir -p /app/logs /app/uploads /app/temp && \
    chown -R ghost:ghost /app/logs /app/uploads /app/temp

# Install the package
RUN pip install -e .

# Switch to non-root user
USER ghost

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/src \
    API_HOST=0.0.0.0 \
    API_PORT=8888

# Expose port
EXPOSE 8888

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8888/health || exit 1

# Default command
CMD ["python", "tools/docker_entrypoint.py"]