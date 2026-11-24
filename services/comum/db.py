"""
Camada de acesso ao PostgreSQL (SQL direto via psycopg2, sem ORM).

Escrita: motor, notificador.  Leitura: API.
O esquema é criado em runtime (CREATE ... IF NOT EXISTS) protegido por um
advisory lock, para que vários serviços subindo ao mesmo tempo não colidam.
"""

from __future__ import annotations

import json
import os
import time

import psycopg2

DDL = """
CREATE TABLE IF NOT EXISTS telemetria (
    id               BIGSERIAL PRIMARY KEY,
    leitura_id       TEXT UNIQUE,
    device_id        TEXT,
    talhao           TEXT,
    regiao           TEXT,
    cultura          TEXT,
    ts_coleta        TIMESTAMPTZ,
    ts_processado    TIMESTAMPTZ DEFAULT now(),
    temperatura_c    NUMERIC,
    umidade_solo_pct NUMERIC,
    luminosidade_pct NUMERIC,
    indice_estresse  NUMERIC,
    status_solo      TEXT,
    valida           BOOLEAN,
    motivo_rejeicao  TEXT
);
CREATE INDEX IF NOT EXISTS ix_telemetria_device ON telemetria (device_id, id DESC);

CREATE TABLE IF NOT EXISTS classificacoes (
    id        BIGSERIAL PRIMARY KEY,
    ts        TIMESTAMPTZ,
    cultura   TEXT,
    condicao  TEXT,
    label     TEXT,
    confianca NUMERIC,
    correta   BOOLEAN,
    regiao    TEXT,
    mes       TEXT,
    criado_em TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ciclos (
    id              BIGSERIAL PRIMARY KEY,
    gerado_em       TIMESTAMPTZ DEFAULT now(),
    total_amostras  INT,
    acuracia        NUMERIC,
    confianca_media NUMERIC,
    total_alertas   INT,
    por_severidade  JSONB,
    fonte           TEXT
);

CREATE TABLE IF NOT EXISTS alertas (
    id            BIGSERIAL PRIMARY KEY,
    ciclo_id      BIGINT REFERENCES ciclos(id) ON DELETE CASCADE,
    case_id       TEXT,
    regra_id      TEXT,
    regra_nome    TEXT,
    severidade    TEXT,
    escopo        TEXT,
    alvo          TEXT,
    mensagem      TEXT,
    recomendacao  TEXT,
    dados_suporte JSONB,
    gerado_em     TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_alertas_regra ON alertas (regra_id, id DESC);

CREATE TABLE IF NOT EXISTS notificacoes (
    id          BIGSERIAL PRIMARY KEY,
    case_id     TEXT,
    regra_id    TEXT,
    severidade  TEXT,
    alvo        TEXT,
    canal       TEXT,
    tentativas  INT,
    enviada_em  TIMESTAMPTZ DEFAULT now()
);

-- Event log para mineração de processos (formato XES-like: case, activity, timestamp)
CREATE TABLE IF NOT EXISTS event_log (
    id        BIGSERIAL PRIMARY KEY,
    case_id   TEXT NOT NULL,
    processo  TEXT NOT NULL,
    atividade TEXT NOT NULL,
    ts        TIMESTAMPTZ NOT NULL,
    recurso   TEXT,
    atributos JSONB
);
CREATE INDEX IF NOT EXISTS ix_event_log_case ON event_log (case_id, ts);
"""


def get_conn(retries: int = 40, delay: float = 2.0):
    """Conecta ao Postgres com retry (espera o container subir)."""
    ultimo: Exception | None = None
    for _ in range(retries):
        try:
            conn = psycopg2.connect(
                host=os.getenv("PGHOST", "localhost"),
                port=int(os.getenv("PGPORT", "5432")),
                dbname=os.getenv("PGDATABASE", "agrosmart"),
                user=os.getenv("PGUSER", "agrosmart"),
                password=os.environ.get("PGPASSWORD", ""),
                connect_timeout=5,
            )
            conn.autocommit = True
            return conn
        except Exception as e:  # noqa: BLE001
            ultimo = e
            time.sleep(delay)
    raise RuntimeError(f"Postgres indisponível: {ultimo}")


def init_schema(conn) -> None:
    with conn.cursor() as cur:
        cur.execute("SELECT pg_advisory_lock(7007)")
        try:
            cur.execute(DDL)
        finally:
            cur.execute("SELECT pg_advisory_unlock(7007)")


# ─── Escrita ─────────────────────────────────────────────────────────────────
def inserir_telemetria(conn, t: dict) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO telemetria
                 (leitura_id, device_id, talhao, regiao, cultura, ts_coleta,
                  temperatura_c, umidade_solo_pct, luminosidade_pct,
                  indice_estresse, status_solo, valida, motivo_rejeicao)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
               ON CONFLICT (leitura_id) DO NOTHING""",
            (t["leitura_id"], t["device_id"], t.get("talhao"), t.get("regiao"),
             t.get("cultura"), t["ts_coleta"], t.get("temperatura_c"),
             t.get("umidade_solo_pct"), t.get("luminosidade_pct"),
             t.get("indice_estresse"), t.get("status_solo"), t["valida"],
             t.get("motivo_rejeicao")),
        )


def inserir_classificacao(conn, e: dict) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO classificacoes
                 (ts, cultura, condicao, label, confianca, correta, regiao, mes)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
            (e.get("ts"), e.get("cultura"), e.get("condicao"), e.get("label"),
             e.get("confianca_pct"), e.get("correta"), e.get("regiao"), e.get("mes")),
        )


def inserir_ciclo(conn, s: dict) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO ciclos
                 (total_amostras, acuracia, confianca_media,
                  total_alertas, por_severidade, fonte)
               VALUES (%s,%s,%s,%s,%s,%s) RETURNING id""",
            (s["total_amostras"], s["acuracia"], s["confianca_media"],
             s["total_alertas"], json.dumps(s["por_severidade"]), s.get("fonte", "stream")),
        )
        return cur.fetchone()[0]


def inserir_alerta(conn, d: dict, ciclo_id: int | None = None, case_id: str | None = None) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO alertas
                 (ciclo_id, case_id, regra_id, regra_nome, severidade, escopo,
                  alvo, mensagem, recomendacao, dados_suporte)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (ciclo_id, case_id, d["regra_id"], d["regra_nome"], d["severidade"],
             d["escopo"], d["alvo"], d["mensagem"], d["recomendacao"],
             json.dumps(d.get("dados_suporte", {}), default=str)),
        )


def inserir_notificacao(conn, n: dict) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO notificacoes (case_id, regra_id, severidade, alvo, canal, tentativas)
               VALUES (%s,%s,%s,%s,%s,%s)""",
            (n.get("case_id"), n.get("regra_id"), n.get("severidade"),
             n.get("alvo"), n.get("canal"), n.get("tentativas")),
        )


def registrar_eventos(conn, eventos: list[dict]) -> None:
    """Grava eventos no event log. Cada item: case_id, processo, atividade, ts, recurso, atributos."""
    if not eventos:
        return
    with conn.cursor() as cur:
        cur.executemany(
            """INSERT INTO event_log (case_id, processo, atividade, ts, recurso, atributos)
               VALUES (%s,%s,%s,%s,%s,%s)""",
            [(e["case_id"], e["processo"], e["atividade"], e["ts"], e.get("recurso"),
              json.dumps(e.get("atributos") or {}, default=str)) for e in eventos],
        )
