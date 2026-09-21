import json
import logging


class JSONFormatter(logging.Formatter):
    """Minimal stdlib-only JSON line formatter — no new dependency, and
    plays nicely with `docker logs`/any downstream log shipper that expects
    one JSON object per line rather than uvicorn's default colorized text."""

    def format(self, record):
        payload = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload)
