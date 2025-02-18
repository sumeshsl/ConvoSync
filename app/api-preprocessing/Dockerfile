FROM python:3.10-slim

WORKDIR /app

COPY . /app

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8008

CMD ["uvicorn", "preprocessing:app", "--host", "0.0.0.0", "--port", "8008"]