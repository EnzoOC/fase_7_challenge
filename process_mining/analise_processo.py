"""
Mineração de processos da plataforma AgroSmart.

Lê o event log exportado pela API (`/api/event-log.csv`) e gera:

  saida/event_log.csv / event_log.xes   → log no formato padrão (case, activity, timestamp)
  saida/mapa_frequencia.png             → DFG: quantas vezes cada caminho ocorreu
  saida/mapa_desempenho.png             → DFG: tempo médio entre atividades (gargalos)
  saida/modelo_bpmn.png                 → modelo de processo descoberto (Inductive Miner)
  saida/variantes.csv                   → variantes (sequências distintas) e frequência
  saida/transicoes.csv                  → estatísticas de tempo por transição
  saida/relatorio_processo.md           → análise com gargalos, variações e melhorias

Uso:
  python analise_processo.py --url http://localhost:8000/api/event-log.csv
  python analise_processo.py --csv event_log.csv
"""

from __future__ import annotations

import argparse
import io
import os
import urllib.request
from datetime import datetime
from pathlib import Path

import pandas as pd
import pm4py

ATV_ALERTA = ("Alerta crítico gerado", "Alerta preventivo gerado")


def carregar(args) -> pd.DataFrame:
    if args.csv:
        df = pd.read_csv(args.csv)
    else:
        with urllib.request.urlopen(args.url, timeout=60) as r:  # noqa: S310  # nosec B310 - URL interna configurada
            df = pd.read_csv(io.BytesIO(r.read()))
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, format="ISO8601")
    df["ordem"] = range(len(df))
    return df.sort_values(["case_id", "timestamp", "ordem"]).reset_index(drop=True)


def dec(x: float, casas: int = 1) -> str:
    return f"{x:.{casas}f}".replace(".", ",")


def br(n: int) -> str:
    return f"{int(n):,}".replace(",", ".")


def fmt_seg(s: float) -> str:
    if pd.isna(s):
        return "—"
    if s < 1:
        return f"{s * 1000:.0f} ms"
    if s < 120:
        return f"{s:.1f} s".replace(".", ",")
    return f"{s / 60:.1f} min".replace(".", ",")


def transicoes(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    d["proxima"] = d.groupby("case_id")["activity"].shift(-1)
    d["ts_proxima"] = d.groupby("case_id")["timestamp"].shift(-1)
    d = d.dropna(subset=["proxima"])
    d["dur"] = (d["ts_proxima"] - d["timestamp"]).dt.total_seconds()
    t = d.groupby(["activity", "proxima"])["dur"].agg(
        ocorrencias="count", media_s="mean", mediana_s="median",
        p95_s=lambda x: x.quantile(0.95), max_s="max").reset_index()
    t["tempo_total_s"] = t["ocorrencias"] * t["media_s"]
    return t.sort_values("tempo_total_s", ascending=False)


def variantes(df: pd.DataFrame) -> pd.DataFrame:
    seq = df.groupby("case_id")["activity"].apply(lambda s: " → ".join(s))
    v = seq.value_counts().rename_axis("variante").reset_index(name="casos")
    v["pct"] = (100 * v["casos"] / v["casos"].sum()).round(1)
    dur = df.groupby("case_id")["timestamp"].agg(lambda s: (s.max() - s.min()).total_seconds())
    v["duracao_media_s"] = v["variante"].map(
        pd.DataFrame({"v": seq, "d": dur}).groupby("v")["d"].mean())
    return v


def salvar_visuais(log_pm: pd.DataFrame, saida: Path) -> list[str]:
    gerados = []
    try:
        dfg, sa, ea = pm4py.discover_dfg(log_pm)
        pm4py.save_vis_dfg(dfg, sa, ea, str(saida / "mapa_frequencia.png"))
        gerados.append("mapa_frequencia.png")
        perf, sa, ea = pm4py.discover_performance_dfg(log_pm)
        pm4py.save_vis_performance_dfg(perf, sa, ea, str(saida / "mapa_desempenho.png"),
                                       aggregation_measure="mean")
        gerados.append("mapa_desempenho.png")
        bpmn = pm4py.discover_bpmn_inductive(log_pm, noise_threshold=0.2)
        pm4py.save_vis_bpmn(bpmn, str(saida / "modelo_bpmn.png"))
        gerados.append("modelo_bpmn.png")
    except Exception as e:  # noqa: BLE001 - sem graphviz o relatório textual continua
        print(f"[aviso] visualizações não geradas: {e}")
    return gerados


def relatorio(df_all: pd.DataFrame, df: pd.DataFrame, trans: pd.DataFrame, var: pd.DataFrame,
              imagens: list[str]) -> str:
    casos = df["case_id"].nunique()
    inicio, fim = df["timestamp"].min(), df["timestamp"].max()
    por_caso = df.groupby("case_id")["activity"].apply(set)
    n = lambda atv: int(por_caso.apply(lambda s: atv in s).sum())  # noqa: E731
    rejeitadas, ideais = n("Leitura rejeitada"), n("Sem intervenção (solo ideal)")
    suprimidos = n("Alerta suprimido (cooldown)")
    alertas = int(por_caso.apply(lambda s: bool(s & set(ATV_ALERTA))).sum())
    descartadas = n("Notificação descartada")
    com_falha = int(df[df["activity"] == "Falha no envio"]["case_id"].nunique())

    # Leituras que chegaram atrasadas (buffer offline)
    col = df[df["activity"] == "Leitura coletada"].set_index("case_id")["timestamp"]
    rec = df[df["activity"] == "Leitura recebida no broker"].set_index("case_id")["timestamp"]
    atraso = (rec - col).dt.total_seconds().dropna()
    atrasadas = atraso[atraso > 10]

    # Ponta a ponta dos casos com alerta: coleta → notificação enviada
    env = df[df["activity"] == "Notificação enviada"].set_index("case_id")["timestamp"]
    e2e = (env - col.reindex(env.index)).dt.total_seconds().dropna()
    ger = df[df["activity"].isin(ATV_ALERTA)].set_index("case_id")["timestamp"]
    ini = df[df["activity"] == "Envio iniciado"].set_index("case_id")["timestamp"]
    fila = (ini - ger.reindex(ini.index)).dt.total_seconds().dropna()

    gargalo = trans.iloc[0] if len(trans) else None
    lenta = trans.sort_values("media_s", ascending=False).iloc[0] if len(trans) else None
    pct = lambda x: 100 * x / casos if casos else 0  # noqa: E731

    L = []
    L.append("# Análise de Processo — AgroSmart (mineração de processos)\n")
    L.append(f"_Gerado em {datetime.now():%d/%m/%Y %H:%M} a partir do event log da plataforma._\n")
    L.append("## 1. Escopo do log\n")
    L.append("| Indicador | Valor |\n|---|---|")
    L.append("| Processo analisado | Telemetria IoT → decisão → notificação |")
    L.append(f"| Casos (leituras) | {br(casos)} |")
    L.append(f"| Eventos | {br(len(df))} |")
    L.append(f"| Atividades distintas | {df['activity'].nunique()} |")
    L.append(f"| Variantes | {len(var)} |")
    L.append(f"| Janela observada | {inicio:%d/%m %H:%M:%S} → {fim:%d/%m %H:%M:%S} UTC "
             f"({fmt_seg((fim - inicio).total_seconds())}) |")
    outros = df_all[df_all["processo"] != "telemetria"]["case_id"].nunique()
    L.append(f"| Casos do processo de sanidade (R1–R6) | {br(outros)} |\n")

    L.append("## 2. Representação do processo\n")
    L.append("```mermaid\nflowchart LR\n"
             "  A[Leitura coletada] --> B[Recebida no broker]\n"
             "  B --> C{Validação}\n  C -->|inválida| R[Leitura rejeitada]\n"
             "  C -->|válida| D[Índice de estresse calculado]\n"
             "  D -->|IDEAL| I[Sem intervenção]\n"
             "  D -->|ALERTA/CRÍTICO| E{Cooldown?}\n"
             "  E -->|sim| S[Alerta suprimido]\n"
             "  E -->|não| G[Alerta gerado]\n"
             "  G --> H[Envio iniciado]\n  H --> F[Falha no envio] --> H2[reenvio]\n"
             "  H --> N[Notificação enviada]\n  H2 --> N\n  H2 --> X[Notificação descartada]\n```\n")
    for img, titulo in (("mapa_frequencia.png", "Mapa de frequência (DFG)"),
                        ("mapa_desempenho.png", "Mapa de desempenho — tempo médio entre atividades"),
                        ("modelo_bpmn.png", "Modelo BPMN descoberto (Inductive Miner)")):
        if img in imagens:
            L.append(f"**{titulo}**\n\n![{titulo}]({img})\n")

    L.append("## 3. Variantes (variações do fluxo)\n")
    L.append("| # | Casos | % | Duração média | Sequência |\n|---|---|---|---|---|")
    for i, r in var.head(10).iterrows():
        L.append(f"| {i + 1} | {r['casos']} | {dec(r['pct'])}% | {fmt_seg(r['duracao_media_s'])} | {r['variante']} |")
    L.append("")
    L.append("| Desfecho | Casos | % |\n|---|---|---|")
    for nome, v in (("Solo ideal — sem intervenção", ideais), ("Alerta gerado e notificado", alertas),
                    ("Alerta suprimido por cooldown", suprimidos), ("Leitura rejeitada (dado inválido)", rejeitadas)):
        L.append(f"| {nome} | {br(v)} | {dec(pct(v))}% |")
    L.append("")

    L.append("## 4. Desempenho e gargalos\n")
    L.append("| De → Para | Ocorrências | Média | Mediana | p95 | Tempo total acumulado |\n|---|---|---|---|---|---|")
    for _, r in trans.head(8).iterrows():
        L.append(f"| {r['activity']} → {r['proxima']} | {br(r['ocorrencias'])} | {fmt_seg(r['media_s'])} | "
                 f"{fmt_seg(r['mediana_s'])} | {fmt_seg(r['p95_s'])} | {fmt_seg(r['tempo_total_s'])} |")
    L.append("")
    if len(e2e):
        L.append(f"- **Ponta a ponta (coleta → produtor notificado):** mediana {fmt_seg(e2e.median())}, "
                 f"p95 {fmt_seg(e2e.quantile(0.95))}, máximo {fmt_seg(e2e.max())} ({len(e2e)} casos).")
    if len(fila):
        L.append(f"- **Espera na fila de notificação:** mediana {fmt_seg(fila.median())}, "
                 f"p95 {fmt_seg(fila.quantile(0.95))}, máximo {fmt_seg(fila.max())}.")
    L.append(f"- **Leituras entregues com atraso (> 10 s, buffer offline):** {len(atrasadas)} "
             f"({dec(pct(len(atrasadas)))}%), atraso médio {fmt_seg(atrasadas.mean() if len(atrasadas) else float('nan'))}.")
    L.append(f"- **Retrabalho no envio:** {com_falha} casos tiveram ao menos uma falha de envio; "
             f"{descartadas} notificações foram descartadas após todas as tentativas.\n")

    L.append("## 5. Insights\n")
    if gargalo is not None:
        L.append(f"1. **Principal gargalo (maior tempo acumulado):** `{gargalo['activity']} → {gargalo['proxima']}` "
                 f"— média {fmt_seg(gargalo['media_s'])}, p95 {fmt_seg(gargalo['p95_s'])}. ")
    if lenta is not None:
        L.append(f"2. **Transição mais lenta por caso:** `{lenta['activity']} → {lenta['proxima']}` "
                 f"(média {fmt_seg(lenta['media_s'])}).")
    L.append("3. **O processamento interno é praticamente instantâneo:** validação, cálculo do índice e "
             "decisão levam milissegundos. Todo o tempo relevante está nas bordas do processo — "
             "conectividade no campo (entrada) e gateways de mensagem (saída).")
    L.append(f"4. **Variação de entrada:** {dec(pct(rejeitadas))}% das leituras são rejeitadas por dado inválido "
             f"e {dec(pct(len(atrasadas)))}% chegam atrasadas por queda de conexão do nó IoT.")
    if alertas + suprimidos:
        L.append(f"5. **O cooldown evita {dec(100 * suprimidos / (alertas + suprimidos), 0)}% das mensagens** que "
                 f"seriam enviadas — sem ele, a fila do notificador seria várias vezes maior.\n")

    L.append("## 6. Oportunidades de melhoria\n")
    p_atraso, p_rej = pct(len(atrasadas)), pct(rejeitadas)
    fila_p95 = fila.quantile(0.95) if len(fila) else 0.0
    sup_pct = 100 * suprimidos / (alertas + suprimidos) if (alertas + suprimidos) else 0.0
    linhas = [
        # (relevante?, prioridade, problema observado, melhoria, impacto)
        (len(atrasadas) > 0, p_atraso,
         f"{dec(p_atraso)}% das leituras chegam com atraso médio de {fmt_seg(atrasadas.mean() if len(atrasadas) else 0)} (nó IoT offline)",
         "Gateway de borda (edge/LoRaWAN) no campo que decide localmente R7 mesmo sem internet; alerta operacional de nó offline (já no Grafana)",
         "Elimina o maior tempo acumulado do processo"),
        (rejeitadas > 0, p_rej,
         f"{dec(p_rej)}% das leituras rejeitadas por dado inválido",
         "Regra de manutenção: N rejeições seguidas do mesmo nó abrem ordem de serviço para trocar/calibrar o sensor",
         "Menos dados perdidos e menos pontos cegos"),
        (com_falha + descartadas > 0, 100 * (com_falha + descartadas) / max(1, alertas),
         f"{com_falha} casos com falha de envio, {descartadas} descartados",
         "Fallback automático de canal (WhatsApp → SMS → e-mail) e confirmação de leitura",
         "Zera notificações perdidas"),
        (fila_p95 > 2, fila_p95,
         f"Espera na fila de notificação com p95 de {fmt_seg(fila_p95)}",
         "Workers paralelos por canal e fila com prioridade (CRÍTICO na frente)",
         "Reduz o tempo até o produtor agir"),
        (suprimidos > 0, sup_pct / 10,
         f"{dec(sup_pct, 0)}% dos alertas R7 suprimidos pelo cooldown (episódios longos de estresse)",
         "Evoluir de cooldown para resumo periódico por fazenda (digest) + acionamento automático da irrigação",
         "Menos fadiga de alerta e ação sem intervenção humana"),
    ]
    L.append("_Ordenadas pelo impacto medido neste log._\n")
    L.append("| # | Problema observado (dado do log) | Melhoria proposta | Impacto esperado |\n|---|---|---|---|")
    for i, (_, _, prob, mel, imp) in enumerate(sorted([x for x in linhas if x[0]], key=lambda x: -x[1]), 1):
        L.append(f"| {i} | {prob} | {mel} | {imp} |")
    return "\n".join(L) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", default=os.getenv("EVENT_LOG_URL", "http://localhost:8000/api/event-log.csv"))
    ap.add_argument("--csv", help="usar um CSV local em vez da API")
    ap.add_argument("--saida", default=os.getenv("SAIDA", "/saida" if Path("/saida").is_dir() else "saida"))
    ap.add_argument("--processo", default="telemetria")
    args = ap.parse_args()

    saida = Path(args.saida)
    saida.mkdir(parents=True, exist_ok=True)
    df_all = carregar(args)
    df_all.to_csv(saida / "event_log.csv", index=False)
    df = df_all[df_all["processo"] == args.processo].copy()
    # Casos ainda em andamento no momento da exportação distorcem os tempos: ficam de fora.
    ultimos = df.groupby("case_id")["activity"].last()
    em_andamento = ultimos[ultimos.isin(ATV_ALERTA + ("Envio iniciado", "Falha no envio"))].index
    df = df[~df["case_id"].isin(em_andamento)]

    log_pm = pm4py.format_dataframe(df, case_id="case_id", activity_key="activity", timestamp_key="timestamp")
    pm4py.write_xes(log_pm, str(saida / "event_log.xes"))
    trans = transicoes(df)
    var = variantes(df)
    trans.to_csv(saida / "transicoes.csv", index=False)
    var.to_csv(saida / "variantes.csv", index=False)
    imagens = salvar_visuais(log_pm, saida)
    (saida / "relatorio_processo.md").write_text(relatorio(df_all, df, trans, var, imagens), encoding="utf-8")
    print(f"[ok] {df['case_id'].nunique()} casos analisados "
          f"({len(em_andamento)} em andamento ignorados) → {saida}/relatorio_processo.md")


if __name__ == "__main__":
    main()
