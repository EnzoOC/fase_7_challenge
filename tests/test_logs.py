"""Logs estruturados: cada linha deve ser JSON válido com os campos padrão."""

import json

from logs import get_logger


def test_log_json(capsys):
    get_logger("teste").info("evento", extra={"device_id": "D1"})
    linha = json.loads(capsys.readouterr().out.strip())
    assert linha["servico"] == "teste" and linha["msg"] == "evento" and linha["device_id"] == "D1"
    assert linha["nivel"] == "INFO" and linha["ts"]
