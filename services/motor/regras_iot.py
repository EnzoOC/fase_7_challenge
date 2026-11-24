"""
R7 — Estresse hídrico no talhão (regra em tempo real sobre a telemetria IoT).

Formaliza o `automacao.py` da Fase 6 no mesmo padrão `Alerta` das regras
R1..R6 da Fase 3:

  SE status_solo == CRÍTICO  ENTÃO alerta CRITICA → WhatsApp/SMS do gerente agrícola
  SE status_solo == ALERTA   ENTÃO alerta MEDIA   → push no app do agrônomo
  SENÃO                       nenhuma intervenção

Para não inundar o produtor com mensagens repetidas, há um CONTROLE DE
COOLDOWN por talhão: um novo alerta só é emitido se o status PIOROU desde o
último alerta ou se o cooldown expirou.
"""

from __future__ import annotations

from regras import Alerta

ORDEM_STATUS = {"IDEAL": 0, "ALERTA": 1, "CRÍTICO": 2}


def r7_estresse_hidrico(reg: dict, talhao: dict) -> Alerta | None:
    status = reg.get("status_solo")
    if status not in ("ALERTA", "CRÍTICO"):
        return None
    indice = reg["indice_estresse"]
    alvo = f"{talhao.get('talhao', '?')} · {talhao.get('regiao', '?')} ({reg['device_id']})"
    suporte = {
        "device_id": reg["device_id"],
        "cultura": talhao.get("cultura"),
        "indice_estresse": indice,
        "temperatura_c": reg["temperatura_c"],
        "umidade_solo_pct": reg["umidade_solo_pct"],
        "leitura_id": reg["leitura_id"],
    }
    if status == "CRÍTICO":
        return Alerta(
            regra_id="R7", regra_nome="Estresse hídrico no talhão", severidade="CRITICA",
            escopo="talhao", alvo=alvo,
            mensagem=f"Índice de estresse hídrico extremamente alto ({indice})",
            recomendacao=("Iniciar irrigação imediatamente e suspender aplicação foliar "
                          "devido à alta evaporação."),
            dados_suporte=suporte,
        )
    return Alerta(
        regra_id="R7", regra_nome="Estresse hídrico no talhão", severidade="MEDIA",
        escopo="talhao", alvo=alvo,
        mensagem=(f"Índice de estresse em elevação ({indice}); condição favorável "
                  "à proliferação de fungos (ex.: ferrugem asiática)"),
        recomendacao="Priorizar inspeção visual neste talhão nas próximas 24 horas.",
        dados_suporte=suporte,
    )


class ControleCooldown:
    """Decide se um alerta R7 deve ser emitido ou suprimido (anti-spam)."""

    def __init__(self, cooldown_seg: float):
        self.cooldown = cooldown_seg
        self._ultimo: dict[str, tuple[str, float]] = {}   # device → (status, instante)

    def avaliar(self, device_id: str, status: str, agora: float) -> bool:
        if status == "IDEAL":
            self._ultimo.pop(device_id, None)   # voltou ao normal: próximo alerta sai
            return False
        anterior = self._ultimo.get(device_id)
        piorou = anterior is None or ORDEM_STATUS[status] > ORDEM_STATUS[anterior[0]]
        expirou = anterior is not None and (agora - anterior[1]) >= self.cooldown
        if piorou or expirou:
            self._ultimo[device_id] = (status, agora)
            return True
        return False
