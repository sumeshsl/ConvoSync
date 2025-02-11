FROM python:3.10-slim

WORKDIR /app

COPY . .
# Set PYTHONPATH to ensure imports work correctly
ENV PYTHONPATH=/app

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8002

CMD ["uvicorn", "verification:app", "--host", "0.0.0.0", "--port", "8002"]