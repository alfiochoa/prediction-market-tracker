"""Structured (JSON-lines) logging."""
import json
import logging
import sys


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        out = {"ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"), "level": record.levelname,
               "logger": record.name, "msg": record.getMessage()}
        out.update(getattr(record, "ctx", {}))
        return json.dumps(out, default=str)


def get_logger(name: str = "pmtracker") -> logging.Logger:
    log = logging.getLogger(name)
    if not log.handlers:
        h = logging.StreamHandler(sys.stderr)
        h.setFormatter(JsonFormatter())
        log.addHandler(h)
        log.setLevel(logging.INFO)
        log.propagate = False
    return log


def event(log: logging.Logger, msg: str, level: int = logging.INFO, **ctx) -> None:
    log.log(level, msg, extra={"ctx": ctx})
