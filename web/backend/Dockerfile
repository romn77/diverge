FROM python:3.13-slim

WORKDIR /app
ENV UV_PROJECT_ENVIRONMENT=/usr/local
ENV UV_LINK_MODE=copy
    
RUN apt-get update \
    && apt-get install -y --no-install-recommends bash postgresql-client ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock README.md requirements.txt ./
COPY web/backend/requirements.txt ./web/backend/requirements.txt

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir uv \
    && uv sync --frozen --no-dev --extra web --no-install-project

COPY . .

RUN uv sync --frozen --no-dev --extra web

EXPOSE 8000

CMD ["uvicorn", "web.backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
