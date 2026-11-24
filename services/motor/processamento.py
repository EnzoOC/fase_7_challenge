"""
Processamento da telemetria IoT (camada Bronze → Silver).

Evolução direta do `script_processamento.py` da Fase 6: a mesma fórmula do
índice de estresse hídrico e a mesma classificação de status, agora com
VALIDAÇÃO de qualidade do dado antes do cálculo (governança da Fase 5).
"""

from __future__ import annotations

# Faixas físicas plausíveis para os sensores do protótipo (TMP36, LDR, solo).
FAIXAS = {
    "temperatura_c": (-10.0, 60.0),
    "umidade_solo_pct": (0.0, 100.0),
    "luminosidade_pct": (0.0, 100.0),
}

# Variação máxima fisicamente plausível entre duas leituras seguidas (~3 s) do mesmo nó.
# Um valor dentro da faixa mas com salto absurdo (ex.: 24 °C → -1 °C) é falha de sensor.
MAX_SALTO_TEMPERATURA = 8.0

LIMIAR_ALERTA = 40
LIMIAR_CRITICO = 60


def validar_leitura(leitura: dict, anterior: dict | None = None) -> tuple[bool, str | None]:
    """Retorna (válida, motivo_da_rejeição).

    `anterior` é a última leitura VÁLIDA do mesmo nó (verificação de plausibilidade).
    """
    if not leitura.get("device_id"):
        return False, "device_id ausente"
    for campo, (minimo, maximo) in FAIXAS.items():
        valor = leitura.get(campo)
        if valor is None:
            return False, f"{campo} ausente"
        try:
            v = float(valor)
        except (TypeError, ValueError):
            return False, f"{campo} não numérico"
        if not minimo <= v <= maximo:
            return False, f"{campo} fora da faixa ({v})"
    if anterior and anterior.get("temperatura_c") is not None:
        salto = abs(float(leitura["temperatura_c"]) - float(anterior["temperatura_c"]))
        if salto > MAX_SALTO_TEMPERATURA:
            return False, f"temperatura_c com salto implausível ({salto:.1f} °C)"
    return True, None


def calcular_indice_estresse(temperatura_c: float, umidade_solo_pct: float) -> float:
    """Fórmula da Fase 6: quanto mais quente e seco, maior o estresse."""
    return round((temperatura_c * 1.5) - umidade_solo_pct + 50, 2)


def classificar_status(indice: float) -> str:
    if indice > LIMIAR_CRITICO:
        return "CRÍTICO"
    if indice > LIMIAR_ALERTA:
        return "ALERTA"
    return "IDEAL"


def processar(leitura: dict, anterior: dict | None = None) -> dict:
    """Leitura bruta → registro Silver (sempre retorna; `valida` indica o resultado)."""
    ok, motivo = validar_leitura(leitura, anterior)
    saida = {
        "leitura_id": leitura.get("leitura_id"),
        "device_id": leitura.get("device_id"),
        "ts_coleta": leitura.get("ts_coleta"),
        "temperatura_c": leitura.get("temperatura_c"),
        "umidade_solo_pct": leitura.get("umidade_solo_pct"),
        "luminosidade_pct": leitura.get("luminosidade_pct"),
        "valida": ok,
        "motivo_rejeicao": motivo,
        "indice_estresse": None,
        "status_solo": None,
    }
    if ok:
        indice = calcular_indice_estresse(float(leitura["temperatura_c"]),
                                          float(leitura["umidade_solo_pct"]))
        saida["indice_estresse"] = indice
        saida["status_solo"] = classificar_status(indice)
    return saida
