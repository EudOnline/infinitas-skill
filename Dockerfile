# ── Build stage ────────────────────────────────────────────────────────────────
ARG PYTHON_IMAGE=python:3.11-slim@sha256:db3ff2e1800a8581e2c48a27c3995339d47bdf046da21c7627accd3d51053a93
ARG AGE_VERSION=1.2.1
ARG AGE_LINUX_AMD64_SHA256=7df45a6cc87d4da11cc03a539a7470c15b1041ab2b396af088fe9990f7c79d50
ARG AGE_LINUX_ARM64_SHA256=57fd79a7ece5fe501f351b9dd51a82fbee1ea8db65a8839db17f5c080245e99f
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

ARG AGE_VERSION
ARG AGE_LINUX_AMD64_SHA256
ARG AGE_LINUX_ARM64_SHA256
ARG TARGETARCH

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    INFINITAS_BUNDLED_REPO_PATH=/opt/infinitas/bundle \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

# Install runtime dependencies only
RUN timeout --signal=TERM 300 apt-get -o Acquire::Retries=3 -o Acquire::http::Timeout=30 update \
    && timeout --signal=TERM 300 apt-get -o Acquire::Retries=3 -o Acquire::http::Timeout=30 install \
        --yes --no-install-recommends \
        bash \
        ca-certificates \
        curl \
        git \
        openssh-client \
    && case "$TARGETARCH" in \
        amd64) AGE_SHA256="$AGE_LINUX_AMD64_SHA256" ;; \
        arm64) AGE_SHA256="$AGE_LINUX_ARM64_SHA256" ;; \
        *) echo "unsupported age target architecture: $TARGETARCH" >&2; exit 1 ;; \
    esac \
    && curl --fail --location --silent --show-error \
        --connect-timeout 15 --max-time 120 --retry 3 --retry-all-errors \
        "https://github.com/FiloSottile/age/releases/download/v${AGE_VERSION}/age-v${AGE_VERSION}-linux-${TARGETARCH}.tar.gz" \
        --output /tmp/age.tar.gz \
    && echo "${AGE_SHA256}  /tmp/age.tar.gz" | sha256sum --check --strict \
    && tar --extract --gzip --file /tmp/age.tar.gz --directory /tmp \
    && install --mode 0755 "/tmp/age/age" "/usr/local/bin/age" \
    && install --mode 0755 "/tmp/age/age-keygen" "/usr/local/bin/age-keygen" \
    && rm -rf /tmp/age /tmp/age.tar.gz \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /bin/bash --uid 1000 infinitas

# Copy the locked runtime environment from the build stage.
COPY --from=builder /build/.venv /opt/venv
RUN sed -i '1c #!/opt/venv/bin/python3' /opt/venv/bin/infinitas

WORKDIR /opt/infinitas/bundle

# Copy application code (this layer rebuilds on code changes)
COPY . /opt/infinitas/bundle
RUN cd / \
    && /opt/venv/bin/infinitas --help >/dev/null \
    && age --version

# Set ownership and switch to non-root user
RUN chown -R infinitas:infinitas /opt/infinitas
USER infinitas

EXPOSE 8000

ENTRYPOINT ["/opt/infinitas/bundle/docker/entrypoint-hosted.sh"]
CMD ["python3", "-m", "uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "8000"]
