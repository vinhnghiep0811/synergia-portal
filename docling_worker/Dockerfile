FROM python:3.11-slim

WORKDIR /app

ENV PIP_DEFAULT_TIMEOUT=300
ENV PIP_RETRIES=10
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV DOCLING_ARTIFACTS_PATH=/opt/docling-artifacts

RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libgl1 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libxcb1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
COPY constraints.txt /app/constraints.txt

RUN pip install --upgrade pip setuptools wheel

RUN pip install \
    --no-cache-dir \
    --timeout 300 \
    --retries 10 \
    --prefer-binary \
    --index-url https://download.pytorch.org/whl/cpu \
    torch==2.8.0+cpu

RUN pip install \
    --no-cache-dir \
    --timeout 300 \
    --retries 10 \
    --prefer-binary \
    --extra-index-url https://download.pytorch.org/whl/cpu \
    -c /app/constraints.txt \
    -r /app/requirements.txt

RUN mkdir -p /opt/docling-artifacts

RUN docling-tools models download -o /opt/docling-artifacts

COPY . /app

CMD ["python", "-m", "worker"]