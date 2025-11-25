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
COPY .env* ./

# Create data directory and copy ONLY the dev database (1.2GB vs 2.2GB)
# Rename recipes_dev.db to recipes.db for production use
RUN mkdir -p data
COPY data/recipes_dev.db ./data/recipes.db
COPY data/user_data.db ./data/user_data.db

# Create logs directory
RUN mkdir -p logs

# Expose port 8080 (Cloud Run default)
ENV PORT=8080
EXPOSE 8080

# Set Python path
ENV PYTHONPATH=/app

# Use gunicorn for production with:
# - 1 worker: Required for in-memory SSE queue sharing between chat and progress-stream
# - 16 threads: More threads to compensate for single worker (I/O-bound LLM calls)
# - 5 minute timeout: Allow long LLM operations
# Note: Multiple workers would require Redis or similar for shared queue state
CMD exec gunicorn --bind :$PORT --workers 1 --threads 16 --timeout 300 src.web.app:app
