FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsndfile1 \
    espeak-ng \
    fonts-dejavu \
    build-essential \
    g++ \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY video /app/video
COPY server.py /app/server.py
COPY assets /app/assets
COPY templates /app/templates

ENV PYTHONUNBUFFERED=1

CMD ["fastapi", "run", "server.py", "--host", "0.0.0.0", "--port", "8000"]
