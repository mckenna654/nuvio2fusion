FROM python:3.11-slim

LABEL maintainer="mckenna654"
LABEL description="Self-hosted Nuvio / Xperience to AIOMetadata Bridge Web App"

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY app/ ./app/
COPY run.py .

# Environment variables
ENV PORT=7088
ENV HOST=0.0.0.0
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Expose default port
EXPOSE 7088

# Healthcheck dynamically checking PORT
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:${PORT:-7088}/api/health || exit 1

# Start server using python runner
CMD ["python", "run.py"]
