"""
Regras de decisão da Fase 3 — Inteligência no Campo.

Cada regra é uma função pura que recebe agregados (estatísticas pré-calculadas
pelo motor) e retorna uma lista de Alerta. As regras usam lógica booleana
explícita (AND/OR/NOT) e estrutura SE/ENTÃO. Mantemos o código próximo da
descrição em pseudocódigo do documento LOGICA_DECISAO.md.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

SEVERIDADES = ("INFO", "BAIXA", "MEDIA", "ALTA", "CRITICA")


@dataclass
class Alerta:
    regra_id: str
    regra_nome: str
    severidade: str
    escopo: str            # "regiao", "cultura", "mes", "global"
    alvo: str              # nome da região/cultura/mês ou "geral"
    mensagem: str
    recomendacao: str
    dados_suporte: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ─────────────────────────────────────────────────────────────────────────────
# R1 — INFESTAÇÃO REGIONAL
# SE  (% doentes na região > 30) AND (total imagens na região >= 5)
# ENTAO emitir alerta CRITICA de infestação
# ─────────────────────────────────────────────────────────────────────────────
def r1_infestacao_regional(agg_regiao: dict[str, dict]) -> list[Alerta]:
    alertas: list[Alerta] = []
    for regiao, s in agg_regiao.items():
        total = s["total"]
        if total == 0:
            continue
        pct_doente = s["doente"] / total * 100
        if (pct_doente > 30) and (total >= 5):
            alertas.append(Alerta(
                regra_id="R1",
                regra_nome="Infestação regional",
                severidade="CRITICA" if pct_doente > 50 else "ALTA",
                escopo="regiao",
                alvo=regiao,
                mensagem=(
                    f"{pct_doente:.1f}% das {total} amostras de {regiao} apresentam doença"
                ),
                recomendacao=(
                    "Acionar plano de contenção: isolar lotes afetados, aplicar "
                    "fungicida/bactericida específico e revisar irrigação."
                ),
                dados_suporte={
                    "pct_doente": round(pct_doente, 2),
                    "total_amostras": total,
                    "saudaveis": s["saudavel"],
                    "doentes": s["doente"],
                },
            ))
    return alertas


# ─────────────────────────────────────────────────────────────────────────────
# R2 — CULTURA EM RISCO
# SE (% doentes na cultura > 40) OR (uma doença específica > 25% das amostras da cultura)
# ENTAO emitir alerta ALTA na cultura
# ─────────────────────────────────────────────────────────────────────────────
def r2_cultura_em_risco(agg_cultura: dict[str, dict]) -> list[Alerta]:
    alertas: list[Alerta] = []
    for cultura, s in agg_cultura.items():
        total = s["total"]
        if total == 0:
            continue
        pct_doente = s["doente"] / total * 100
        doenca_dominante = None
        pct_dominante = 0.0
        for cond, qtd in s["condicoes"].items():
            if cond.lower().startswith("saud"):
                continue
            pct = qtd / total * 100
            if pct > pct_dominante:
                pct_dominante, doenca_dominante = pct, cond

        cond_pct_doentes = pct_doente > 40
        cond_doenca_dominante = pct_dominante > 25 and doenca_dominante is not None

        if cond_pct_doentes or cond_doenca_dominante:
            motivo_partes = []
            if cond_pct_doentes:
                motivo_partes.append(f"{pct_doente:.1f}% de doentes")
            if cond_doenca_dominante:
                motivo_partes.append(f"{doenca_dominante} representa {pct_dominante:.1f}%")
            alertas.append(Alerta(
                regra_id="R2",
                regra_nome="Cultura em risco",
                severidade="ALTA" if pct_doente > 60 else "MEDIA",
                escopo="cultura",
                alvo=cultura,
                mensagem=f"Cultura {cultura}: " + " e ".join(motivo_partes),
                recomendacao=(
                    f"Tratamento direcionado contra {doenca_dominante or 'a doença predominante'}; "
                    "intensificar inspeção e considerar rotação de cultura para o próximo ciclo."
                ),
                dados_suporte={
                    "pct_doente": round(pct_doente, 2),
                    "doenca_dominante": doenca_dominante,
                    "pct_dominante": round(pct_dominante, 2),
                    "total_amostras": total,
                },
            ))
    return alertas


# ─────────────────────────────────────────────────────────────────────────────
# R3 — DOENÇA EMERGENTE NO MÊS
# SE (mesma doença com >= 3 ocorrências no mesmo mês) AND (NOT é Saudável)
# ENTAO emitir alerta MEDIA de surto sazonal
# ─────────────────────────────────────────────────────────────────────────────
def r3_doenca_emergente(agg_mes_doenca: dict[tuple[str, str], int]) -> list[Alerta]:
    alertas: list[Alerta] = []
    for (mes, doenca), qtd in agg_mes_doenca.items():
        is_saudavel = doenca.lower().startswith("saud")
        if (qtd >= 3) and (not is_saudavel):
            alertas.append(Alerta(
                regra_id="R3",
                regra_nome="Doença emergente no mês",
                severidade="MEDIA" if qtd < 6 else "ALTA",
                escopo="mes",
                alvo=f"{doenca} / {mes}",
                mensagem=f"{qtd} ocorrências de {doenca} em {mes}",
                recomendacao=(
                    "Investigar fator sazonal (umidade, temperatura). Programar "
                    "aplicação preventiva no próximo mês equivalente."
                ),
                dados_suporte={"mes": mes, "doenca": doenca, "ocorrencias": qtd},
            ))
    return alertas


# ─────────────────────────────────────────────────────────────────────────────
# R4 — BAIXA QUALIDADE DO MODELO
# SE (confiança média < 75) AND (% erros > 15)
# ENTAO emitir alerta MEDIA de qualidade do modelo
# ─────────────────────────────────────────────────────────────────────────────
def r4_baixa_qualidade(stats_globais: dict) -> list[Alerta]:
    conf_media = stats_globais["confianca_media"]
    pct_erro = stats_globais["pct_erro"]
    total = stats_globais["total"]
    if (conf_media < 75) and (pct_erro > 15):
        return [Alerta(
            regra_id="R4",
            regra_nome="Baixa qualidade do classificador",
            severidade="MEDIA",
            escopo="global",
            alvo="modelo",
            mensagem=(
                f"Modelo com confiança média {conf_media:.1f}% e taxa de erro "
                f"{pct_erro:.1f}% sobre {total} amostras"
            ),
            recomendacao=(
                "Reavaliar dataset de treino, balancear classes e considerar "
                "retreinamento antes de confiar nas próximas decisões automáticas."
            ),
            dados_suporte={
                "confianca_media": round(conf_media, 2),
                "pct_erro": round(pct_erro, 2),
                "total_amostras": total,
            },
        )]
    return []


# ─────────────────────────────────────────────────────────────────────────────
# R5 — ZONA SAUDÁVEL (recomendação INFO)
# SE (% doentes na região < 10) AND (acurácia do modelo na região > 85)
# ENTAO emitir recomendação INFO de manutenção
# ─────────────────────────────────────────────────────────────────────────────
def r5_zona_saudavel(agg_regiao: dict[str, dict]) -> list[Alerta]:
    alertas: list[Alerta] = []
    for regiao, s in agg_regiao.items():
        total = s["total"]
        if total < 5:
            continue
        pct_doente = s["doente"] / total * 100
        acuracia = s["corretas"] / total * 100 if total else 0
        if (pct_doente < 10) and (acuracia > 85):
            alertas.append(Alerta(
                regra_id="R5",
                regra_nome="Zona saudável",
                severidade="INFO",
                escopo="regiao",
                alvo=regiao,
                mensagem=(
                    f"{regiao} com apenas {pct_doente:.1f}% de doentes e {acuracia:.1f}% "
                    "de acurácia do modelo"
                ),
                recomendacao=(
                    "Manter rotina semanal de inspeção e irrigação. "
                    "Reaproveitar lote como referência para estudos comparativos."
                ),
                dados_suporte={
                    "pct_doente": round(pct_doente, 2),
                    "acuracia_modelo": round(acuracia, 2),
                    "total_amostras": total,
                },
            ))
    return alertas


# ─────────────────────────────────────────────────────────────────────────────
# R6 — TENDÊNCIA DE PIORA MENSAL
# SE (% doentes do mês atual > 1.5 * % doentes do mês anterior)
#    AND (total amostras do mês atual >= 5)
# ENTAO emitir alerta ALTA de piora
# ─────────────────────────────────────────────────────────────────────────────
def r6_tendencia_piora(serie_mensal: list[dict]) -> list[Alerta]:
    """serie_mensal é ordenada cronologicamente, cada item: {mes, total, doente, saudavel}."""
    alertas: list[Alerta] = []
    for i in range(1, len(serie_mensal)):
        atual = serie_mensal[i]
        anterior = serie_mensal[i - 1]
        if atual["total"] < 5 or anterior["total"] == 0:
            continue
        pct_atual = atual["doente"] / atual["total"] * 100
        pct_ant = anterior["doente"] / anterior["total"] * 100
        if pct_ant == 0:
            continue
        if pct_atual > 1.5 * pct_ant:
            alertas.append(Alerta(
                regra_id="R6",
                regra_nome="Tendência de piora mensal",
                severidade="ALTA",
                escopo="mes",
                alvo=atual["mes"],
                mensagem=(
                    f"Doenças subiram de {pct_ant:.1f}% ({anterior['mes']}) "
                    f"para {pct_atual:.1f}% ({atual['mes']})"
                ),
                recomendacao=(
                    "Investigar causa do salto: clima, mudança de manejo ou novo patógeno. "
                    "Antecipar pulverização preventiva."
                ),
                dados_suporte={
                    "mes_atual": atual["mes"],
                    "pct_atual": round(pct_atual, 2),
                    "mes_anterior": anterior["mes"],
                    "pct_anterior": round(pct_ant, 2),
                    "multiplicador": round(pct_atual / pct_ant, 2),
                },
            ))
    return alertas


# Conjunto ordenado de regras (descrito também em LOGICA_DECISAO.md)
REGRAS = [
    ("R1", "Infestação regional",          r1_infestacao_regional),
    ("R2", "Cultura em risco",             r2_cultura_em_risco),
    ("R3", "Doença emergente no mês",      r3_doenca_emergente),
    ("R4", "Baixa qualidade do modelo",    r4_baixa_qualidade),
    ("R5", "Zona saudável",                r5_zona_saudavel),
    ("R6", "Tendência de piora mensal",    r6_tendencia_piora),
]
