FROM python:3.11-slim

LABEL maintainer="XP2AIOM"
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

# Expose port
EXPOSE 8080

# Environment variables
ENV PORT=8080
ENV HOST=0.0.0.0
ENV PYTHONUNBUFFERED=1

# Healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8080/api/health || exit 1

# Start Uvicorn server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
