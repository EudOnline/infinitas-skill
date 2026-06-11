# ── Build stage ────────────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install --yes --no-install-recommends \
        build-essential \
        git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Copy dependency metadata first for layer caching
COPY pyproject.toml README.md ./
COPY src/ src/

# Install build dependencies and the package
RUN pip install --upgrade pip \
    && pip install .


# ── Runtime stage ─────────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    INFINITAS_BUNDLED_REPO_PATH=/opt/infinitas/bundle

# Install runtime dependencies only
RUN apt-get update \
    && apt-get install --yes --no-install-recommends \
        bash \
        ca-certificates \
        git \
        openssh-client \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /bin/bash --uid 1000 infinitas

# Copy installed Python packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

WORKDIR /opt/infinitas/bundle

# Copy application code (this layer rebuilds on code changes)
COPY . /opt/infinitas/bundle

# Set ownership and switch to non-root user
RUN chown -R infinitas:infinitas /opt/infinitas
USER infinitas

EXPOSE 8000

ENTRYPOINT ["/opt/infinitas/bundle/docker/entrypoint-hosted.sh"]
CMD ["python3", "-m", "uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "8000"]
