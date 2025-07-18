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

# Configurações de armazenamento
ENV STORAGE_PATH=/app/media

# Configurações de otimização de CPU para containers
ENV MAX_CPU_THREADS=8
ENV CPU_USAGE_LIMIT=0.9
ENV MAX_CONCURRENT_TTS=4
ENV MAX_CONCURRENT_VIDEO=2
ENV MAX_CONCURRENT_HEAVY_TASKS=6

# Configurações adicionais do PyTorch para otimização
ENV OMP_NUM_THREADS=8
ENV MKL_NUM_THREADS=8
ENV TORCH_NUM_THREADS=8

# Criar volume mount point para armazenamento persistente
VOLUME ["/app/media"]

CMD ["fastapi", "run", "server.py", "--host", "0.0.0.0", "--port", "8000"]
