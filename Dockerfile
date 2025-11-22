# Use Python 3.10 slim image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt gunicorn

# Copy application code
COPY src/ ./src/
COPY data/ ./data/
COPY .env* ./

# Create logs directory
RUN mkdir -p logs

# Expose port 8080 (Cloud Run default)
ENV PORT=8080
EXPOSE 8080

# Set Python path
ENV PYTHONPATH=/app

# Use gunicorn for production with 5 minute timeout
CMD exec gunicorn --bind :$PORT --workers 1 --threads 4 --timeout 300 src.web.app:app
