"""
Logs estruturados em JSON (uma linha por evento) para todos os serviços.

Formato pensado para ser lido por humanos no terminal e, ao mesmo tempo,
ser filtrável por máquina (jq, Loki, ELK...):

  {"ts":"2026-11-24T18:00:00.123Z","nivel":"INFO","servico":"motor","msg":"...", ...}
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import UTC, datetime

_CAMPOS_PADRAO = set(vars(logging.makeLogRecord({})))


class _JsonFormatter(logging.Formatter):
    def __init__(self, servico: str):
        super().__init__()
        self.servico = servico

    def format(self, record: logging.LogRecord) -> str:
        doc = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "nivel": record.levelname,
            "servico": self.servico,
            "msg": record.getMessage(),
        }
        for k, v in vars(record).items():
            if k not in _CAMPOS_PADRAO and not k.startswith("_"):
                doc[k] = v
        if record.exc_info:
            doc["erro"] = self.formatException(record.exc_info)
        return json.dumps(doc, ensure_ascii=False, default=str)


def get_logger(servico: str) -> logging.Logger:
    log = logging.getLogger(servico)
    if not log.handlers:
        h = logging.StreamHandler(sys.stdout)
        h.setFormatter(_JsonFormatter(servico))
        log.addHandler(h)
        log.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())
        log.propagate = False
    return log
