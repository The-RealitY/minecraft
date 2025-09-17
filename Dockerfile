# Use a Python 3.10 Alpine-based image as the base image
FROM python:3.10-alpine

# Set environment variables for better performance
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PIP_NO_CACHE_DIR=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1

# Set the working directory inside the container
WORKDIR /app

# Install system dependencies in a single layer
RUN apk add --no-cache \
    gcc \
    musl-dev \
    libffi-dev \
    openssl-dev \
    && rm -rf /var/cache/apk/*

# Copy requirements first for better layer caching
COPY requirements.txt /app/

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && pip cache purge

# Copy application code
COPY ./mc_backup /app/mc_backup
COPY token.json /app/

# Create non-root user for security
RUN adduser -D -s /bin/sh backupuser \
    && chown -R backupuser:backupuser /app

# Create necessary directories with proper permissions
RUN mkdir -p /app/data /app/backup /app/backup_logs \
    && chown -R backupuser:backupuser /app/data /app/backup /app/backup_logs

# Switch to non-root user
USER backupuser

# Add health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python3 -c "import requests; requests.get('http://localhost:8080/health', timeout=5)" || exit 1

# Run the application
CMD ["python3", "-m", "mc_backup"]
