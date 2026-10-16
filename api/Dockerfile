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

COPY api/docker-entrypoint.py /usr/local/bin/docker-entrypoint.py
# Starts as root only to fix ownership of the mounted data folders, then runs as "hub".
RUN useradd --system --uid 1000 hub && mkdir -p /srv/data /srv/files && chown hub /srv/data /srv/files

EXPOSE 8000
# Only Caddy can reach the API (compose.yml doesn't publish it), so trust the client address
# Caddy forwards: the API lets in devices on the home network without a login.
ENTRYPOINT ["python", "/usr/local/bin/docker-entrypoint.py"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
