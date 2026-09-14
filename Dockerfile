FROM python:3.11-slim

WORKDIR /app

# tzdata provides the IANA zoneinfo database so the TZ env var below (and
# Python's zoneinfo.ZoneInfo) actually resolve to the right offset instead
# of silently behaving as UTC, which is what python:3.11-slim defaults to.
RUN apt-get update && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY src/ ./src/

# Create data directory
RUN mkdir -p /app/data

# Expose web port
EXPOSE 8080

# Environment variables (override with -e or docker-compose)
ENV PYTHONUNBUFFERED=1
ENV VESTABOARD_LOCAL_URL=""
ENV WEB_HOST=0.0.0.0
ENV WEB_PORT=8080
ENV DB_PATH=/app/data/vestaboard.db
ENV TZ=America/Los_Angeles

# Run the application
CMD ["python", "-m", "src.main"]
