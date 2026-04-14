FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libgl1 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libxcb1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

ENV DOCLING_ARTIFACTS_PATH=/opt/docling-artifacts
RUN mkdir -p /opt/docling-artifacts

# preload model đúng nghĩa
RUN docling-tools models download -o /opt/docling-artifacts

COPY . /app

CMD ["python", "-m", "worker"]