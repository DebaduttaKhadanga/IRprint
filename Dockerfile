# IRprint container: clang + rustc + Python 3.11 + SQLite.
#
#   docker build -t irprint .
#   docker run --rm -p 8000:8000 irprint                         # dashboard
#   docker run --rm -v "$PWD/subs:/subs" irprint irprint scan /subs
#   docker run --rm irprint python experiments/cross_language_eval.py

# ---------------------------------------------------------------------------
# Stage 1: build a wheel of the irprint package and its dependencies
# ---------------------------------------------------------------------------
FROM python:3.11-slim-bookworm AS builder
WORKDIR /build
COPY pyproject.toml README.md ./
COPY irprint ./irprint
RUN pip install --no-cache-dir --upgrade pip \
 && pip wheel --no-cache-dir --wheel-dir /wheels .

# ---------------------------------------------------------------------------
# Stage 2: runtime image with the compilers IRprint drives
# ---------------------------------------------------------------------------
FROM python:3.11-slim-bookworm AS runtime

# clang/clang++ for C and C++, rustc for Rust, sqlite3 CLI for inspecting the DB.
RUN apt-get update \
 && apt-get install -y --no-install-recommends clang rustc libstd-rust-dev sqlite3 \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir /wheels/* pytest httpx && rm -rf /wheels

COPY irprint ./irprint
COPY dashboard ./dashboard
COPY experiments ./experiments
COPY tests ./tests
COPY pyproject.toml README.md decision.md flow.md ./
RUN mkdir -p /app/data

ENV IRPRINT_DB_URL=sqlite:////app/data/irprint.db
EXPOSE 8000
CMD ["irprint", "serve", "--host", "0.0.0.0", "--port", "8000", "--db-url", "sqlite:////app/data/irprint.db"]
