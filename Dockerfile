FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY src/ ./src/
COPY data/ ./data/ 2>/dev/null || mkdir -p ./data

# Create data directory
RUN mkdir -p /app/data

# Expose web port
EXPOSE 8080

# Environment variables (override with -e or docker-compose)
ENV VESTABOARD_LOCAL_URL=""
ENV VESTABOARD_LOCAL_KEY=""
ENV WEB_HOST=0.0.0.0
ENV WEB_PORT=8080
ENV DB_PATH=/app/data/vestaboard.db

# Run the application
CMD ["python", "-m", "src.main"]
