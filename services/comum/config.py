"""
Configuração compartilhada da plataforma AgroSmart (Fase 7).

Tudo que muda entre ambientes vem de variáveis de ambiente (12-factor):
nenhuma senha fica fixa no código. Os valores padrão servem apenas para
rodar localmente/testes.
"""

from __future__ import annotations

import json
import os

# ─── Kafka ───────────────────────────────────────────────────────────────────
KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "localhost:29092")

TOPICO_TELEMETRIA = "telemetria-iot"         # sensores de campo (Fase 6)
TOPICO_IMAGENS = "imagens-classificadas"      # visão computacional (Fases 1-2)
TOPICO_ALERTAS = "alertas"                    # saída do motor → notificador
TOPICOS = [TOPICO_TELEMETRIA, TOPICO_IMAGENS, TOPICO_ALERTAS]

# ─── Domínio ─────────────────────────────────────────────────────────────────
REGIOES = ["Zona Norte", "Zona Sul", "Zona Leste", "Zona Oeste", "Centro"]
MESES = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
         "Jul", "Ago", "Set", "Out", "Nov", "Dez"]

# Cada talhão tem um nó IoT (Arduino/ESP32 — protótipo Tinkercad da Fase 6).
TALHOES = [
    {"device_id": "TINKER-TALHAO-01", "talhao": "T01", "regiao": "Zona Norte", "cultura": "Milho"},
    {"device_id": "TINKER-TALHAO-02", "talhao": "T02", "regiao": "Zona Sul", "cultura": "Tomate"},
    {"device_id": "TINKER-TALHAO-03", "talhao": "T03", "regiao": "Zona Leste", "cultura": "Batata"},
    {"device_id": "TINKER-TALHAO-04", "talhao": "T04", "regiao": "Zona Oeste", "cultura": "Uva"},
    {"device_id": "TINKER-TALHAO-05", "talhao": "T05", "regiao": "Centro", "cultura": "Milho"},
]
TALHAO_POR_DEVICE = {t["device_id"]: t for t in TALHOES}


def env_float(nome: str, padrao: float) -> float:
    return float(os.getenv(nome, str(padrao)))


def env_int(nome: str, padrao: int) -> int:
    return int(os.getenv(nome, str(padrao)))


def jdumps(obj) -> str:
    """JSON compacto em UTF-8 (acentos preservados) para payloads Kafka."""
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"), default=str)
