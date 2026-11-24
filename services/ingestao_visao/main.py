"""
Ingestão de visão computacional — eventos do classificador de imagens.

Reaproveita o produtor da Fase 4: publica no tópico `imagens-classificadas`
eventos amostrados do CSV REAL gerado pelo classificador Random Forest da
Fase 1 (`resultados_classificacao.csv`, dataset PlantVillage).

A cada ~20 lotes uma região diferente entra "em surto" (taxa de doença
elevada) e o relógio simulado avança 1 dia por lote, para que as regras
regionais (R1), por cultura (R2), sazonais (R3) e de tendência (R6) mudem
ao longo da demonstração.

Métricas Prometheus em :9104/metrics.
"""

from __future__ import annotations

import csv
import datetime as dt
import os
import random
import time

from confluent_kafka import Producer
from prometheus_client import Counter, Gauge, start_http_server

from config import KAFKA_BOOTSTRAP, MESES, REGIOES, TOPICO_IMAGENS, env_float, jdumps
from kafka_util import criar_topicos, esperar_kafka
from logs import get_logger

log = get_logger("ingestao-visao")

INTERVALO = env_float("INTERVALO_VISAO_SEG", 2.0)
CSV_PATH = os.getenv("CSV_PATH", "resultados_classificacao.csv")

M_EVENTOS = Counter("agrosmart_visao_classificacoes_publicadas_total",
                    "Classificações publicadas", ["label"])
M_SURTO = Gauge("agrosmart_visao_regiao_em_surto", "Região simulada em surto", ["regiao"])

rng = random.Random()


def carregar_combos(path: str) -> list[dict]:
    combos: list[dict] = []
    try:
        with open(path, encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                cultura = (row.get("cultura") or "").strip()
                if not cultura:
                    continue
                cond = (row.get("condicao_real") or "").strip().replace("Saudavel", "Saudável")
                det = (row.get("categoria_detectada") or "").strip()
                label = "Saudável" if det in ("Saudavel", "Saudável") else "Doente"
                combos.append({"cultura": cultura, "condicao": cond, "label": label})
    except FileNotFoundError:
        log.warning("CSV não encontrado; usando fallback sintético", extra={"csv": path})
    return combos


def main() -> None:
    start_http_server(9104)
    esperar_kafka(log)
    criar_topicos(log)

    combos = carregar_combos(CSV_PATH)
    saudaveis = [c for c in combos if c["label"] == "Saudável"] or \
        [{"cultura": "Milho", "condicao": "Saudável", "label": "Saudável"}]
    doentes = [c for c in combos if c["label"] == "Doente"] or [
        {"cultura": "Tomate", "condicao": "Requeima", "label": "Doente"}]

    prod = Producer({"bootstrap.servers": KAFKA_BOOTSTRAP, "linger.ms": 50})
    sim = dt.datetime(2026, 1, 1, 6, 0, 0)
    lote = 0
    surto_idx = 0
    log.info("stream de visão iniciado",
             extra={"saudaveis": len(saudaveis), "doentes": len(doentes), "intervalo_seg": INTERVALO})

    while True:
        lote += 1
        if lote % 20 == 0:
            surto_idx = (surto_idx + 1) % len(REGIOES)
        regiao_surto = REGIOES[surto_idx]
        for r in REGIOES:
            M_SURTO.labels(r).set(1 if r == regiao_surto else 0)

        n = rng.randint(6, 9)
        for i in range(n):
            reg = rng.choice(REGIOES)
            doente = rng.random() < (0.70 if reg == regiao_surto else 0.30)
            combo = rng.choice(doentes if doente else saudaveis)
            evt = {
                "tipo": "classificacao",
                "ts": sim.isoformat(),
                "cultura": combo["cultura"],
                "condicao": combo["condicao"],
                "label": combo["label"],
                "confianca_pct": round(rng.uniform(68, 99), 2),
                "correta": rng.random() > 0.08,
                "regiao": reg,
                "mes": MESES[sim.month - 1],
                "nome_arquivo": f"{combo['cultura']}_{lote:04d}_{i}.jpg",
            }
            prod.produce(TOPICO_IMAGENS, key=reg.encode(), value=jdumps(evt))
            M_EVENTOS.labels(combo["label"]).inc()

        prod.poll(0)
        prod.flush(5)
        if lote % 10 == 0:
            log.info("lote publicado", extra={"lote": lote, "data_sim": str(sim.date()),
                                               "surto": regiao_surto, "classificacoes": n})
        sim += dt.timedelta(days=1)
        time.sleep(INTERVALO)


if __name__ == "__main__":
    main()
