ARG UV_BASE_IMAGE=ghcr.io/astral-sh/uv:python3.13-trixie-slim
FROM ${UV_BASE_IMAGE}

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
ENV UV_LINK_MODE=copy UV_COMPILE_BYTECODE=1

RUN apt-get update && apt-get install -y --no-install-recommends tini && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml uv.lock ./

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev

COPY app.py .

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

ENTRYPOINT ["tini", "--"]

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]

HEALTHCHECK --start-period=30s --start-interval=1s CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"
