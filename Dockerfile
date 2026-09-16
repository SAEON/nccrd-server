FROM python:3.10

ARG CA_CERT_URL
RUN if [ -n "${CA_CERT_URL}" ]; then curl ${CA_CERT_URL} -k -o /usr/local/share/ca-certificates/saeon-ca.crt; fi
RUN if [ -n "${CA_CERT_URL}" ]; then update-ca-certificates; fi

WORKDIR /srv/nccrd-server
COPY . .
RUN pip install -r requirements.txt

# curl isn't reliably present on the full python:3.10 image, but python is —
# use urllib instead of adding a curl install just for this. /health is
# unauthenticated and does no DB round-trip, so this only proves the ASGI
# app itself is accepting requests, not that the database is reachable.
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:2022/health', timeout=2)" || exit 1

CMD ["uvicorn", "nccrd.api:app", "--host", "0.0.0.0", "--port", "2022", "--workers", "4"]
