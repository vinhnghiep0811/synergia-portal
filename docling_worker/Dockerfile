FROM python:3.11-slim

WORKDIR /app

ENV PIP_DEFAULT_TIMEOUT=300
ENV PIP_RETRIES=10
ENV PIP_DISABLE_PIP_VERSION_CHECK=1

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

RUN pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir \
        torch==2.8.0+cpu \
        --index-url https://download.pytorch.org/whl/cpu

# 2) Cài requirements còn lại
RUN pip install \
    --no-cache-dir \
    --timeout 300 \
    --retries 10 \
    --prefer-binary \
    -i https://pypi.org/simple \
    -r /app/requirements.txt

ENV DOCLING_ARTIFACTS_PATH=/opt/docling-artifacts
RUN mkdir -p /opt/docling-artifacts

RUN docling-tools models download -o /opt/docling-artifacts

COPY . /app

CMD ["python", "-m", "worker"]