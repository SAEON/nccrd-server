#!/bin/sh
# The image's default command: bring the database schema up to date, then
# start the API, so a deploy needs no separate `alembic upgrade head` step.
#
# The database may still be starting (e.g. right after the machine boots),
# so failed migrations are retried for about a minute. If they keep failing,
# the API is not started on an out-of-date schema: the container exits and
# `docker ps` / `docker logs nccrd-api` show why.
#
# Set NCCRD_MIGRATE_ON_START=0 to skip the migrations. Commands given to
# `docker run` replace this script, so test and one-off runs are unaffected.
set -eu

if [ "${NCCRD_MIGRATE_ON_START:-1}" = "1" ]; then
  tries=0
  until alembic upgrade head; do
    tries=$((tries + 1))
    if [ "$tries" -ge 12 ]; then
      echo "[start] migrations failed ${tries} times; not starting the API on an out-of-date schema" >&2
      exit 1
    fi
    echo "[start] migrations failed (database not ready yet?), retrying in 5s" >&2
    sleep 5
  done
fi

exec uvicorn nccrd.api:app --host 0.0.0.0 --port 2022 --workers 4 --log-config logging.json
