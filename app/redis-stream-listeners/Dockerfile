FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY redisstream_listener.py .

# Run the application
CMD ["python", "redisstream_listener.py"]