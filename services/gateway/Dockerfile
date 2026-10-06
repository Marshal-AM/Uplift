# Build context: repository root (needs packages/core)
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY pyproject.toml uv.lock ./
COPY packages packages
COPY rules rules
COPY services services
COPY agents/pyproject.toml agents/pyproject.toml
RUN uv sync --frozen --no-dev --package uplift-gateway
WORKDIR /app/services/gateway
CMD ["/app/.venv/bin/uplift-gateway"]
