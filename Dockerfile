# ─── deps stage: compile psycopg2 (needs gcc + libpq headers) ─────────────
# Kept separate so the build toolchain never ends up in the final image —
# only the installed Python packages are copied out of here.
FROM python:3.10-slim AS deps

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv/nccrd-server
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ─── final stage: slim runtime image, non-root ─────────────────────────────
FROM python:3.10-slim

# libpq5 is psycopg2's runtime dependency (libpq-dev's headers/compiler
# aren't needed once the wheel is built); curl+ca-certificates only matter
# when CA_CERT_URL is actually set.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

ARG CA_CERT_URL
RUN if [ -n "${CA_CERT_URL}" ]; then \
        curl ${CA_CERT_URL} -k -o /usr/local/share/ca-certificates/saeon-ca.crt \
        && update-ca-certificates; \
    fi

COPY --from=deps /install /usr/local

WORKDIR /srv/nccrd-server
COPY . .

# Fixed, predictable UID/GID (rather than whatever useradd happens to pick)
# so a server with an existing nccrd-uploads volume from the old root-owned
# container can be chowned to match with one known command — see
# deploy/BACKUP_RESTORE.md-style notes in the commit message for this change.
RUN groupadd --gid 1000 app \
    && useradd --uid 1000 --gid app --home-dir /srv/nccrd-server --no-create-home app \
    && mkdir -p /srv/nccrd-server/uploads \
    && chown -R app:app /srv/nccrd-server

# curl isn't reliably present on the full python:3.10 image, but python is —
# use urllib instead of adding a curl install just for this. /health is
# unauthenticated and does no DB round-trip, so this only proves the ASGI
# app itself is accepting requests, not that the database is reachable.
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:2022/health', timeout=2)" || exit 1

USER app

CMD ["uvicorn", "nccrd.api:app", "--host", "0.0.0.0", "--port", "2022", "--workers", "4"]
