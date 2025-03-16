FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y curl && \
    rm -rf /var/lib/apt/lists/*

COPY . .

# Install Python dependencies
RUN pip install --no-cache-dir flask==2.0.1 werkzeug==2.0.3 aiohttp==3.8.1 gunicorn==20.1.0 gevent==21.12.0

EXPOSE 8080

# Use gunicorn with gevent worker
CMD ["gunicorn", "--worker-class", "gevent", "--workers", "1", "--bind", "0.0.0.0:8080", "--timeout", "120", "stress_test_service:app"]

# Alternatively, you can run the direct test
# CMD ["python", "direct_test.py"] 