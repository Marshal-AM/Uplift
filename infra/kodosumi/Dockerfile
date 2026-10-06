# Kodosumi panel + Ray Serve running the 12 Uplift specialist flows. Build context: repository root.
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim
RUN apt-get update -y && apt-get install -y --no-install-recommends git gcc libc6-dev && rm -rf /var/lib/apt/lists/*
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY pyproject.toml uv.lock ./
COPY packages packages
COPY rules rules
COPY services services
COPY agents agents
RUN uv sync --frozen --no-dev --package uplift-agents
COPY infra/kodosumi infra/kodosumi
RUN gcc -shared -fPIC -O2 -o /usr/local/lib/libuplift_cpus.so infra/kodosumi/cpus.c -ldl
# Ray sizes its RPC thread pools from the host's core count; hosted containers have many cores but a low
# thread limit, so pin the pools (and BLAS) small.
ENV PATH="/app/.venv/bin:$PATH" \
    KODO_RAY_SERVER=127.0.0.1:6379 \
    OTEL_SDK_DISABLED=true \
    RAY_num_server_call_thread=1 \
    RAY_gcs_server_rpc_server_thread_num=1 \
    RAY_gcs_server_rpc_client_thread_num=1 \
    RAY_object_manager_rpc_threads_num=1 \
    RAY_num_workers_soft_limit=4 \
    OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
    UPLIFT_CPUS=2 LD_PRELOAD=/usr/local/lib/libuplift_cpus.so
WORKDIR /app/infra/kodosumi
CMD ["sh", "entrypoint.sh"]
