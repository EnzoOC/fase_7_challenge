"""
API AgroSmart (FastAPI) — camada de leitura da plataforma.

Endpoints:
  GET /api/health                → liveness + conexão com o banco
  GET /api/status                → status operacional do pipeline (frescor de cada etapa)
  GET /api/stats                 → números gerais
  GET /api/telemetria            → última leitura de cada talhão + histórico recente
  GET /api/alertas.json          → alertas no formato consumido pelo dashboard (Fases 3/4)
  GET /api/notificacoes          → últimas notificações enviadas
  GET /api/event-log             → event log (JSON) para inspeção
  GET /api/event-log.csv         → event log completo para mineração de processos
  GET /metrics                   → métricas Prometheus
"""

from __future__ import annotations

import csv
import io
import json
import os
import time
from contextlib import contextmanager

import psycopg2.extras
from fastapi import FastAPI, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse
from prometheus_client import Counter, Histogram, make_asgi_app
from psycopg2.pool import ThreadedConnectionPool

import db
from logs import get_logger

log = get_logger("api")
app = FastAPI(title="AgroSmart · API", version="7.0.0",
              description="Plataforma AgroSmart — Fase 7 (entrega final)")
app.mount("/metrics", make_asgi_app())

M_REQ = Counter("agrosmart_api_requisicoes_total", "Requisições HTTP", ["rota", "status"])
M_LAT = Histogram("agrosmart_api_latencia_seconds", "Latência HTTP", ["rota"],
                  buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2))

_pool: ThreadedConnectionPool | None = None


def pool() -> ThreadedConnectionPool:
    global _pool
    if _pool is None:
        c = db.get_conn()
        db.init_schema(c)
        dsn = c.dsn
        c.close()
        _pool = ThreadedConnectionPool(1, 8, dsn=dsn, password=os.environ.get("PGPASSWORD", ""))
    return _pool


@contextmanager
def cursor():
    p = pool()
    conn = p.getconn()
    try:
        conn.autocommit = True
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            yield cur
    finally:
        p.putconn(conn)


def q(sql: str, args=(), one: bool = False):
    with cursor() as cur:
        cur.execute(sql, args)
        return cur.fetchone() if one else cur.fetchall()


@app.middleware("http")
async def metricas(request: Request, call_next):
    t0 = time.perf_counter()
    rota = request.url.path if not request.url.path.startswith("/metrics") else "/metrics"
    try:
        resp = await call_next(request)
    except Exception:
        M_REQ.labels(rota, "500").inc()
        log.exception("erro na requisição", extra={"rota": rota})
        return JSONResponse({"erro": "interno"}, status_code=500)
    M_REQ.labels(rota, str(resp.status_code)).inc()
    M_LAT.labels(rota).observe(time.perf_counter() - t0)
    return resp


@app.get("/api/health")
def health():
    try:
        q("SELECT 1 AS ok", one=True)
        return {"status": "ok", "banco": "ok"}
    except Exception as e:  # noqa: BLE001
        return JSONResponse({"status": "erro", "banco": str(e)}, status_code=503)


@app.get("/api/status")
def status():
    """Frescor de cada etapa: se uma etapa para de produzir, o status degrada."""
    r = q("""SELECT
               EXTRACT(EPOCH FROM now() - (SELECT max(ts_processado) FROM telemetria))  AS idade_telemetria,
               EXTRACT(EPOCH FROM now() - (SELECT max(gerado_em) FROM ciclos))          AS idade_ciclo,
               EXTRACT(EPOCH FROM now() - (SELECT max(enviada_em) FROM notificacoes))   AS idade_notificacao,
               (SELECT count(*) FROM telemetria WHERE ts_processado > now() - interval '1 minute') AS leituras_ultimo_min,
               (SELECT count(*) FROM telemetria WHERE NOT valida AND ts_processado > now() - interval '10 minutes') AS rejeitadas_10min,
               (SELECT count(DISTINCT device_id) FROM telemetria WHERE ts_processado > now() - interval '1 minute') AS dispositivos_ativos
          """, one=True)

    def etapa(idade, limite):
        if idade is None:
            return "sem dados"
        return "ok" if float(idade) <= limite else "atrasado"

    etapas = {
        "ingestao_iot_motor": etapa(r["idade_telemetria"], 30),
        "regras_r1_r6": etapa(r["idade_ciclo"], 30),
        "notificador": etapa(r["idade_notificacao"], 600),
    }
    geral = "operacional" if all(v == "ok" for v in etapas.values()) else "degradado"
    return {"status": geral, "etapas": etapas,
            "dispositivos_ativos": r["dispositivos_ativos"],
            "leituras_ultimo_min": r["leituras_ultimo_min"],
            "rejeitadas_10min": r["rejeitadas_10min"],
            "idade_seg": {k: (round(float(v), 1) if v is not None else None)
                          for k, v in r.items() if k.startswith("idade")}}


@app.get("/api/stats")
def stats():
    return q("""SELECT
                  (SELECT count(*) FROM telemetria)                  AS total_leituras,
                  (SELECT count(*) FROM telemetria WHERE NOT valida) AS leituras_rejeitadas,
                  (SELECT count(*) FROM classificacoes)              AS total_classificacoes,
                  (SELECT count(*) FROM ciclos)                      AS total_ciclos,
                  (SELECT count(*) FROM alertas WHERE regra_id='R7') AS alertas_r7,
                  (SELECT count(*) FROM notificacoes)                AS notificacoes_enviadas,
                  (SELECT count(DISTINCT case_id) FROM event_log)    AS casos_event_log""", one=True)


@app.get("/api/telemetria")
def telemetria(historico: int = Query(60, ge=1, le=500)):
    ultimas = q("""SELECT DISTINCT ON (device_id) *
                     FROM telemetria WHERE valida
                    ORDER BY device_id, id DESC""")
    hist = q("""SELECT device_id, talhao, ts_coleta, temperatura_c, umidade_solo_pct,
                       luminosidade_pct, indice_estresse, status_solo
                  FROM (SELECT *, row_number() OVER (PARTITION BY device_id ORDER BY id DESC) AS rn
                          FROM telemetria WHERE valida) t
                 WHERE rn <= %s ORDER BY ts_coleta""", (historico,))
    return {"ultimas": ultimas, "historico": hist}


@app.get("/api/alertas.json")
def alertas_json():
    """Mesmo formato do `alertas.json` da Fase 3 + alertas R7 (IoT) dos últimos 15 min."""
    vazio = {"gerado_em": None, "fonte_csv": "stream", "total_amostras": 0, "acuracia_modelo": 0,
             "confianca_media": 0, "total_alertas": 0,
             "por_severidade": {"INFO": 0, "BAIXA": 0, "MEDIA": 0, "ALTA": 0, "CRITICA": 0},
             "alertas": []}
    c = q("SELECT * FROM ciclos ORDER BY id DESC LIMIT 1", one=True)
    if not c:
        return vazio
    campos = "regra_id, regra_nome, severidade, escopo, alvo, mensagem, recomendacao, dados_suporte"
    al = q(f"SELECT {campos} FROM alertas WHERE ciclo_id = %s ORDER BY id", (c["id"],))  # noqa: S608  # nosec B608
    r7 = q(f"""SELECT DISTINCT ON (alvo) {campos} FROM alertas  -- colunas fixas
               WHERE regra_id = 'R7' AND gerado_em > now() - interval '15 minutes'
               ORDER BY alvo, id DESC""")  # noqa: S608  # nosec B608 - colunas fixas, sem entrada do usuário
    por_sev = dict(c["por_severidade"])
    for a in r7:
        por_sev[a["severidade"]] = por_sev.get(a["severidade"], 0) + 1
    return {
        "gerado_em": c["gerado_em"].isoformat() if c["gerado_em"] else None,
        "fonte_csv": c.get("fonte") or "stream",
        "total_amostras": c["total_amostras"],
        "acuracia_modelo": float(c["acuracia"] or 0),
        "confianca_media": float(c["confianca_media"] or 0),
        "total_alertas": c["total_alertas"] + len(r7),
        "por_severidade": por_sev,
        "alertas": list(r7) + list(al),
    }


@app.get("/api/notificacoes")
def notificacoes(limit: int = Query(30, ge=1, le=500)):
    return q("SELECT * FROM notificacoes ORDER BY id DESC LIMIT %s", (limit,))


@app.get("/api/event-log")
def event_log(limit: int = Query(200, ge=1, le=5000), processo: str | None = None):
    if processo:
        return q("SELECT * FROM event_log WHERE processo=%s ORDER BY id DESC LIMIT %s", (processo, limit))
    return q("SELECT * FROM event_log ORDER BY id DESC LIMIT %s", (limit,))


@app.get("/api/event-log.csv")
def event_log_csv(processo: str | None = None):
    """Exporta o event log (case_id, activity, timestamp, resource...) para pm4py/Disco/Celonis."""
    sql = "SELECT case_id, processo, atividade, ts, recurso, atributos FROM event_log"
    args: tuple = ()
    if processo:
        sql += " WHERE processo = %s"
        args = (processo,)
    sql += " ORDER BY case_id, ts, id"
    linhas = q(sql, args)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["case_id", "processo", "activity", "timestamp", "resource", "atributos"])
    for r in linhas:
        w.writerow([r["case_id"], r["processo"], r["atividade"], r["ts"].isoformat(),
                    r["recurso"], json.dumps(r["atributos"], ensure_ascii=False)])
    buf.seek(0)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=event_log.csv"})
