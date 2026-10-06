# Build context: repository root (needs packages/core, cre/, rules/)

# 1) Compile the CRE workflow to WASM once, so the Worker can run `cre workflow simulate --wasm` without Bun.
FROM oven/bun:1.4 AS cre-build
WORKDIR /src
COPY rules rules
COPY cre/uplift-clearing cre/uplift-clearing
RUN cd cre/uplift-clearing && bun install --frozen-lockfile && bunx cre-compile main.ts /out/uplift-clearing.wasm

# 2) Worker
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim
ARG TARGETARCH
ARG CRE_VERSION=v1.37.0
RUN apt-get update -y && apt-get install -y --no-install-recommends curl ca-certificates && rm -rf /var/lib/apt/lists/* \
 && case "$TARGETARCH" in \
      arm64) SHA=49c48b60a737ada370fb10213bcb1c364bce71508b4e2557512956a3b4289280 ;; \
      *)     TARGETARCH=amd64; SHA=3c8a73540ed78210ab3ed23d792d8a6bfb4e56deb49bc77d61dfbdd54a147155 ;; \
    esac \
 && curl -fsSL -o /tmp/cre.tgz "https://github.com/smartcontractkit/cre-cli/releases/download/${CRE_VERSION}/cre_linux_${TARGETARCH}_ldd2-35.tar.gz" \
 && echo "$SHA  /tmp/cre.tgz" | sha256sum -c - \
 && tar -xzf /tmp/cre.tgz -C /tmp && mv /tmp/cre_${CRE_VERSION}_linux_${TARGETARCH} /usr/local/bin/cre && rm /tmp/cre.tgz
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY pyproject.toml uv.lock ./
COPY packages packages
COPY rules rules
COPY services services
COPY agents/pyproject.toml agents/pyproject.toml
RUN uv sync --frozen --no-dev --package uplift-worker
COPY cre/project.yaml cre/secrets.yaml cre/
COPY cre/uplift-clearing/workflow.yaml cre/uplift-clearing/config.local.json cre/uplift-clearing/main.ts cre/uplift-clearing/
COPY --from=cre-build /out/uplift-clearing.wasm cre/uplift-clearing/uplift-clearing.wasm
WORKDIR /app/services/worker
CMD ["/app/.venv/bin/uplift-worker"]
