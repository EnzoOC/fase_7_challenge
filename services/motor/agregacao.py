"""
Agregação em janela + aplicação das regras de decisão R1..R6.

Reaproveita EXATAMENTE as regras da Fase 3 (`regras.py`, copiado para a
imagem do consumidor). A única diferença em relação ao `motor_regras.py`
batch é que aqui os agregados são calculados sobre uma JANELA deslizante de
eventos que chegam pelo stream, em vez de um CSV inteiro de uma vez.
"""

from __future__ import annotations

from collections import defaultdict

import regras  # fase3/regras.py — copiado no build da imagem

MESES = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
         "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
REGIOES = ["Zona Norte", "Zona Sul", "Zona Leste", "Zona Oeste", "Centro"]


def agregar(registros: list[dict]) -> dict:
    """
    `registros` é a janela atual; cada item:
      {cultura, condicao, label, confianca, correta, mes, regiao}
    Retorna os mesmos agregados que as regras da Fase 3 consomem.
    """
    agg_regiao = {r: {"total": 0, "saudavel": 0, "doente": 0,
                      "corretas": 0, "condicoes": defaultdict(int)} for r in REGIOES}
    agg_cultura: dict[str, dict] = {}
    agg_mes_doenca: dict[tuple[str, str], int] = defaultdict(int)
    agg_mes: dict[str, dict] = {m: {"mes": m, "total": 0,
                                    "saudavel": 0, "doente": 0} for m in MESES}

    total = len(registros)
    saud = doente = corretas = 0
    soma_conf = 0.0

    for r in registros:
        ar = agg_regiao.setdefault(r["regiao"], {
            "total": 0, "saudavel": 0, "doente": 0,
            "corretas": 0, "condicoes": defaultdict(int)})
        ar["total"] += 1
        ar["saudavel" if r["label"] == "Saudável" else "doente"] += 1
        if r["correta"]:
            ar["corretas"] += 1
        ar["condicoes"][r["condicao"]] += 1

        ac = agg_cultura.setdefault(r["cultura"], {
            "total": 0, "saudavel": 0, "doente": 0,
            "condicoes": defaultdict(int)})
        ac["total"] += 1
        ac["saudavel" if r["label"] == "Saudável" else "doente"] += 1
        ac["condicoes"][r["condicao"]] += 1

        agg_mes_doenca[(r["mes"], r["condicao"])] += 1
        am = agg_mes.setdefault(r["mes"], {"mes": r["mes"], "total": 0,
                                           "saudavel": 0, "doente": 0})
        am["total"] += 1
        am["saudavel" if r["label"] == "Saudável" else "doente"] += 1

        if r["label"] == "Saudável":
            saud += 1
        else:
            doente += 1
        if r["correta"]:
            corretas += 1
        soma_conf += r["confianca"]

    serie_mensal = [agg_mes[m] for m in MESES if agg_mes[m]["total"] > 0]

    globais = {
        "total": total,
        "saudavel": saud,
        "doente": doente,
        "corretas": corretas,
        "confianca_media": (soma_conf / total) if total else 0.0,
        "pct_erro": ((total - corretas) / total * 100) if total else 0.0,
    }

    return {
        "regiao": agg_regiao,
        "cultura": agg_cultura,
        "mes_doenca": dict(agg_mes_doenca),
        "serie_mensal": serie_mensal,
        "globais": globais,
    }


def aplicar_regras(ag: dict) -> list[regras.Alerta]:
    todos: list[regras.Alerta] = []
    todos += regras.r1_infestacao_regional(ag["regiao"])
    todos += regras.r2_cultura_em_risco(ag["cultura"])
    todos += regras.r3_doenca_emergente(ag["mes_doenca"])
    todos += regras.r4_baixa_qualidade(ag["globais"])
    todos += regras.r5_zona_saudavel(ag["regiao"])
    todos += regras.r6_tendencia_piora(ag["serie_mensal"])
    return todos
