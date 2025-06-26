ARG CUDA=12.3.1
ARG OS=ubuntu22.04
ARG RUNIMAGE=${CUDA}-runtime-${OS}

FROM nvidia/cuda:${RUNIMAGE}
ARG CUDA
ARG OS
USER root

RUN apt update && apt install -y \
    build-essential \
    g++ \
    curl \
    wget \
    git \
    python3.10 \
    python3-pip \
    python3-dev \
    python3.10-gdbm \
    ffmpeg \
    libsndfile1 \
    espeak-ng \
    fonts-dejavu \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN ln -sf /usr/bin/python3 /usr/bin/python
RUN ln -sf /usr/bin/pip3 /usr/bin/pip

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

ENV LD_LIBRARY_PATH=/usr/local/lib/python3.10/dist-packages/nvidia/cudnn/lib:$LD_LIBRARY_PATH

COPY video /app/video
COPY server.py /app/server.py
COPY assets /app/assets

ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["fastapi", "run", "server.py", "--host", "0.0.0.0", "--port", "8000"]
