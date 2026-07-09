FROM python:3.12-slim

RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Install dependencies first (cached layer) from the locked versions, without the
# project itself — then copy the source and install the package. Reproducible
# (uses uv.lock) and rebuilds deps only when pyproject/uv.lock change.
COPY pyproject.toml uv.lock ./
RUN uv sync --no-dev --frozen --no-install-project

COPY . .
RUN uv sync --no-dev --frozen

RUN mkdir -p storage/uploads storage/outputs

EXPOSE 8000
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
