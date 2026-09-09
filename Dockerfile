FROM python:3.12-slim
WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:0.12.12 /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY apps/api apps/api
COPY packages packages
ENV PATH="/app/.venv/bin:$PATH" PYTHONPATH="/app/apps/api:/app/packages/shared/python:/app/packages/strategies/python"
RUN useradd --create-home selery && mkdir /app/data && chown -R selery:selery /app/data
USER selery
EXPOSE 8000
CMD ["sh", "-c", "uvicorn selery_api.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers"]
