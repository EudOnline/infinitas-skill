FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    INFINITAS_BUNDLED_REPO_PATH=/opt/infinitas/bundle

RUN apt-get update \
    && apt-get install --yes --no-install-recommends \
        bash \
        ca-certificates \
        git \
        openssh-client \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/infinitas/bundle

COPY . /opt/infinitas/bundle

RUN python -m pip install --upgrade pip \
    && python -m pip install .

EXPOSE 8000

ENTRYPOINT ["/opt/infinitas/bundle/docker/entrypoint-hosted.sh"]
CMD ["python3", "-m", "uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "8000"]
