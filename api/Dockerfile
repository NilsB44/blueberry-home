# Built from the repository root (see compose.yml) so the poker engine can be included.

FROM rust:1-slim AS engine
WORKDIR /src
COPY engines/poker ./
RUN cargo build --release

FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv

COPY api/pyproject.toml ./
COPY api/app ./app
COPY api/content ./content
RUN pip install --no-cache-dir .
COPY --from=engine /src/target/release/poker-engine /usr/local/bin/poker-engine

RUN useradd --system --uid 1000 hub && mkdir -p /srv/data && chown hub /srv/data
USER hub

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
