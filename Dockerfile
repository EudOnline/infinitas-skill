# ── Build stage ────────────────────────────────────────────────────────────────
ARG PYTHON_IMAGE=python:3.11-slim@sha256:db3ff2e1800a8581e2c48a27c3995339d47bdf046da21c7627accd3d51053a93
FROM ${PYTHON_IMAGE} AS builder

COPY --from=ghcr.io/astral-sh/uv:0.11.28@sha256:0f36cb9361a3346885ca3677e3767016687b5a170c1a6b88465ec14aefec90aa /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /build

# Install the exact locked runtime dependency set first for layer caching.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --locked --no-dev --no-install-project

# Install the project itself from the same lock without an editable source link.
COPY src/ src/
COPY server/ server/
RUN uv sync --locked --no-dev --no-editable


# ── Runtime stage ─────────────────────────────────────────────────────────────
FROM ${PYTHON_IMAGE} AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    INFINITAS_BUNDLED_REPO_PATH=/opt/infinitas/bundle \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

# Install runtime dependencies only
RUN apt-get -o Acquire::Retries=3 -o Acquire::http::Timeout=30 update \
    && apt-get -o Acquire::Retries=3 -o Acquire::http::Timeout=30 install \
        --yes --no-install-recommends \
        bash \
        ca-certificates \
        git \
        openssh-client \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /bin/bash --uid 1000 infinitas

# Copy the locked runtime environment from the build stage.
COPY --from=builder /build/.venv /opt/venv

WORKDIR /opt/infinitas/bundle

# Copy application code (this layer rebuilds on code changes)
COPY . /opt/infinitas/bundle

# Set ownership and switch to non-root user
RUN chown -R infinitas:infinitas /opt/infinitas
USER infinitas

EXPOSE 8000

ENTRYPOINT ["/opt/infinitas/bundle/docker/entrypoint-hosted.sh"]
CMD ["python3", "-m", "uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "8000"]
