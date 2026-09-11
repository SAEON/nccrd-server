FROM python:3.10

ARG CA_CERT_URL
RUN if [ -n "${CA_CERT_URL}" ]; then curl ${CA_CERT_URL} -k -o /usr/local/share/ca-certificates/saeon-ca.crt; fi
RUN if [ -n "${CA_CERT_URL}" ]; then update-ca-certificates; fi

WORKDIR /srv/nccrd-server
COPY . .
RUN pip install -r requirements.txt

CMD ["uvicorn", "nccrd.api:app", "--host", "0.0.0.0", "--port", "2022", "--workers", "4"]
