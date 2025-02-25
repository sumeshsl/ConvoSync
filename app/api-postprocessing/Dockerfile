FROM python:3.10-slim

WORKDIR /app

COPY . .
# Set PYTHONPATH to ensure imports work correctly
ENV PYTHONPATH=/app

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8004


# Start FastAPI App (also starts Redis listener)
CMD ["python", "postprocessing.py"]

#CMD ["uvicorn", "postprocessing:app", "--host", "0.0.0.0", "--port", "8004"]