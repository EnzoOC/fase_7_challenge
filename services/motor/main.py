"""
Motor de decisão AgroSmart — o "cérebro" da plataforma.

Consome dois fluxos do Kafka e decide automaticamente:

  1. `telemetria-iot` (tempo real, por leitura)
       validação → índice de estresse (Fase 6) → regra R7 → alerta
  2. `imagens-classificadas` (janela deslizante, a cada AVALIAR_SEG)
       agregação → regras R1..R6 (Fase 3, reaproveitadas sem alteração) → alertas

Saídas:
  • PostgreSQL: telemetria Silver, classificações, ciclos, alertas;
  • tópico `alertas`: alertas que exigem notificação (consumido pelo notificador);
  • event log: cada passo de cada leitura (mineração de processos);
  • métricas Prometheus em :9101/metrics; logs JSON no stdout.
"""

from __future__ import annotations

import json
import re
import time
from collections import deque
from datetime import UTC, datetime, timedelta

from confluent_kafka import Consumer, Producer
from prometheus_client import Counter, Gauge, Histogram, start_http_server

import db
from agregacao import agregar, aplicar_regras
from config import (
    KAFKA_BOOTSTRAP,
    TALHAO_POR_DEVICE,
    TOPICO_ALERTAS,
    TOPICO_IMAGENS,
    TOPICO_TELEMETRIA,
    env_float,
    env_int,
    jdumps,
)
from kafka_util import criar_topicos, esperar_kafka
from logs import get_logger
from processamento import processar
from regras_iot import ControleCooldown, r7_estresse_hidrico

log = get_logger("motor")

JANELA = env_int("JANELA", 500)
AVALIAR_SEG = env_float("AVALIAR_SEG", 5.0)
COOLDOWN_SEG = env_float("COOLDOWN_ALERTA_SEG", 60.0)

PROC_TELEMETRIA = "telemetria"
PROC_SANIDADE = "sanidade"

# ─── Métricas ────────────────────────────────────────────────────────────────
M_LEITURAS = Counter("agrosmart_motor_leituras_total", "Leituras IoT processadas", ["resultado"])
M_STATUS = Counter("agrosmart_motor_status_solo_total", "Leituras por status do solo", ["status"])
M_ALERTAS = Counter("agrosmart_motor_alertas_total", "Alertas emitidos para notificação",
                    ["regra", "severidade"])
M_SUPRIMIDOS = Counter("agrosmart_motor_alertas_suprimidos_total", "Alertas R7 suprimidos por cooldown")
M_CLASSIF = Counter("agrosmart_motor_classificacoes_total", "Classificações de imagem consumidas")
M_CICLOS = Counter("agrosmart_motor_ciclos_total", "Ciclos de avaliação R1..R6")
M_ALERTAS_CICLO = Gauge("agrosmart_motor_alertas_ultimo_ciclo", "Alertas ativos no último ciclo",
                        ["severidade"])
M_INDICE = Gauge("agrosmart_indice_estresse", "Índice de estresse hídrico", ["device_id", "talhao"])
M_UMIDADE = Gauge("agrosmart_umidade_solo_pct", "Umidade do solo (%)", ["device_id", "talhao"])
M_TEMP = Gauge("agrosmart_temperatura_c", "Temperatura (°C)", ["device_id", "talhao"])
M_LATENCIA = Histogram("agrosmart_motor_latencia_ingestao_seconds",
                       "Tempo entre a coleta no sensor e o processamento no motor",
                       buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 30, 60, 120, 300))
M_PROC = Histogram("agrosmart_motor_processamento_seconds", "Tempo de processamento por mensagem",
                   buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1))
M_ULTIMO = Gauge("agrosmart_motor_ultimo_evento_timestamp_seconds", "Instante do último evento processado")


def agora_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds")


def _monotonico(eventos: list[dict]) -> list[dict]:
    """Garante timestamps estritamente crescentes dentro de um caso (ordem estável no event log)."""
    anterior = None
    for e in eventos:
        ts = datetime.fromisoformat(e["ts"])
        if anterior is not None and ts <= anterior:
            ts = anterior + timedelta(milliseconds=1)
            e["ts"] = ts.isoformat(timespec="milliseconds")
        anterior = ts
    return eventos


def _slug(t: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", t).strip("-").lower()


class Motor:
    def __init__(self, conn, prod):
        self.conn = conn
        self.prod = prod
        self.janela: deque[dict] = deque(maxlen=JANELA)
        self.cooldown = ControleCooldown(COOLDOWN_SEG)
        self.alertas_ativos: set[tuple[str, str]] = set()
        self.ultima_valida: dict[str, dict] = {}   # device → última leitura válida

    # ── Fluxo 1: telemetria IoT ─────────────────────────────────────────────
    def tratar_telemetria(self, leitura: dict, ts_broker: str) -> None:
        reg = processar(leitura, self.ultima_valida.get(leitura.get("device_id") or ""))
        if reg["valida"]:
            self.ultima_valida[reg["device_id"]] = reg
        talhao = TALHAO_POR_DEVICE.get(reg["device_id"] or "", {})
        reg.update({k: talhao.get(k) for k in ("talhao", "regiao", "cultura")})
        case = reg["leitura_id"] or f"sem-id-{time.time_ns()}"
        dev = reg["device_id"] or "desconhecido"
        buffer = bool(leitura.get("reenviada_buffer"))
        eventos = [
            {"atividade": "Leitura coletada", "ts": reg["ts_coleta"] or ts_broker, "recurso": dev,
             "atributos": {"talhao": reg.get("talhao"), "reenviada_buffer": buffer}},
            {"atividade": "Leitura recebida no broker", "ts": ts_broker, "recurso": "kafka"},
        ]

        if not reg["valida"]:
            M_LEITURAS.labels("rejeitada").inc()
            eventos.append({"atividade": "Leitura rejeitada", "ts": agora_iso(), "recurso": "motor",
                            "atributos": {"motivo": reg["motivo_rejeicao"]}})
            log.warning("leitura rejeitada", extra={"leitura_id": case, "motivo": reg["motivo_rejeicao"]})
        else:
            M_LEITURAS.labels("valida").inc()
            M_STATUS.labels(reg["status_solo"]).inc()
            lbl = (dev, reg.get("talhao") or "?")
            M_INDICE.labels(*lbl).set(reg["indice_estresse"])
            M_UMIDADE.labels(*lbl).set(float(reg["umidade_solo_pct"]))
            M_TEMP.labels(*lbl).set(float(reg["temperatura_c"]))
            eventos.append({"atividade": "Leitura validada", "ts": agora_iso(), "recurso": "motor"})
            eventos.append({"atividade": "Índice de estresse calculado", "ts": agora_iso(),
                            "recurso": "motor",
                            "atributos": {"indice": reg["indice_estresse"], "status": reg["status_solo"]}})
            alerta = r7_estresse_hidrico(reg, talhao)
            if alerta is None:
                eventos.append({"atividade": "Sem intervenção (solo ideal)", "ts": agora_iso(),
                                "recurso": "motor"})
            elif not self.cooldown.avaliar(dev, reg["status_solo"], time.time()):
                M_SUPRIMIDOS.inc()
                eventos.append({"atividade": "Alerta suprimido (cooldown)", "ts": agora_iso(),
                                "recurso": "motor", "atributos": {"status": reg["status_solo"]}})
            else:
                nome = "Alerta crítico gerado" if alerta.severidade == "CRITICA" else "Alerta preventivo gerado"
                eventos.append({"atividade": nome, "ts": agora_iso(), "recurso": "motor",
                                "atributos": {"severidade": alerta.severidade}})
                d = alerta.to_dict()
                db.inserir_alerta(self.conn, d, case_id=case)
                self.publicar_alerta(d, case, PROC_TELEMETRIA,
                                     canal="whatsapp" if alerta.severidade == "CRITICA" else "app")
                log.info("alerta R7 emitido", extra={"leitura_id": case, "severidade": alerta.severidade,
                                                      "indice": reg["indice_estresse"]})

        db.inserir_telemetria(self.conn, reg)
        db.registrar_eventos(self.conn, [dict(e, case_id=case, processo=PROC_TELEMETRIA) for e in _monotonico(eventos)])
        if reg["ts_coleta"]:
            try:
                coleta = datetime.fromisoformat(reg["ts_coleta"])
                M_LATENCIA.observe(max(0.0, time.time() - coleta.timestamp()))
            except ValueError:
                pass

    # ── Fluxo 2: classificações de imagem (R1..R6) ──────────────────────────
    def tratar_classificacao(self, evt: dict) -> None:
        M_CLASSIF.inc()
        self.janela.append({
            "cultura": evt["cultura"], "condicao": evt["condicao"], "label": evt["label"],
            "confianca": float(evt.get("confianca_pct", 0)), "correta": bool(evt.get("correta")),
            "mes": evt.get("mes", "Jan"), "regiao": evt.get("regiao", "Centro"),
        })
        db.inserir_classificacao(self.conn, evt)

    def avaliar_ciclo(self) -> None:
        inicio = agora_iso()
        ag = agregar(list(self.janela))
        alertas = aplicar_regras(ag)
        por_sev = {"INFO": 0, "BAIXA": 0, "MEDIA": 0, "ALTA": 0, "CRITICA": 0}
        for a in alertas:
            por_sev[a.severidade] = por_sev.get(a.severidade, 0) + 1
        g = ag["globais"]
        ciclo_id = db.inserir_ciclo(self.conn, {
            "total_amostras": g["total"], "acuracia": round(100 - g["pct_erro"], 2),
            "confianca_media": round(g["confianca_media"], 2), "total_alertas": len(alertas),
            "por_severidade": por_sev, "fonte": "stream:imagens-classificadas",
        })
        M_CICLOS.inc()
        for sev, n in por_sev.items():
            M_ALERTAS_CICLO.labels(sev).set(n)

        # Só NOVOS alertas graves geram notificação (os demais ficam no painel).
        ativos_agora = set()
        for a in alertas:
            d = a.to_dict()
            db.inserir_alerta(self.conn, d, ciclo_id=ciclo_id)
            chave = (a.regra_id, a.alvo)
            ativos_agora.add(chave)
            if a.severidade in ("ALTA", "CRITICA") and chave not in self.alertas_ativos:
                case = f"SAN-{ciclo_id}-{a.regra_id}-{_slug(a.alvo)}"
                db.registrar_eventos(self.conn, [
                    {"case_id": case, "processo": PROC_SANIDADE, "atividade": "Ciclo de regras avaliado",
                     "ts": inicio, "recurso": "motor", "atributos": {"amostras": g["total"]}},
                    {"case_id": case, "processo": PROC_SANIDADE, "atividade": "Alerta de sanidade gerado",
                     "ts": agora_iso(), "recurso": "motor",
                     "atributos": {"regra": a.regra_id, "severidade": a.severidade}},
                ])
                self.publicar_alerta(d, case, PROC_SANIDADE, canal="email")
        self.alertas_ativos = ativos_agora
        log.info("ciclo R1..R6 avaliado", extra={"ciclo": ciclo_id, "amostras": g["total"],
                                                  "alertas": len(alertas), "por_severidade": por_sev})

    def publicar_alerta(self, d: dict, case_id: str, processo: str, canal: str) -> None:
        M_ALERTAS.labels(d["regra_id"], d["severidade"]).inc()
        msg = dict(d, case_id=case_id, processo=processo, canal=canal, gerado_em=agora_iso())
        self.prod.produce(TOPICO_ALERTAS, key=case_id.encode(), value=jdumps(msg))
        self.prod.poll(0)


def main() -> None:
    start_http_server(9101)
    esperar_kafka(log)
    criar_topicos(log)
    conn = db.get_conn()
    db.init_schema(conn)

    consumer = Consumer({
        "bootstrap.servers": KAFKA_BOOTSTRAP,
        "group.id": "motor-decisao",
        "auto.offset.reset": "latest",
    })
    consumer.subscribe([TOPICO_TELEMETRIA, TOPICO_IMAGENS])
    motor = Motor(conn, Producer({"bootstrap.servers": KAFKA_BOOTSTRAP}))
    ultimo_ciclo = time.time()
    log.info("motor de decisão pronto", extra={"janela": JANELA, "avaliar_seg": AVALIAR_SEG,
                                                "cooldown_seg": COOLDOWN_SEG})
    try:
        while True:
            msg = consumer.poll(1.0)
            if msg is not None and not msg.error():
                t0 = time.perf_counter()
                try:
                    evt = json.loads(msg.value())
                    _, ts_ms = msg.timestamp()
                    ts_broker = datetime.fromtimestamp(ts_ms / 1000, UTC).isoformat(timespec="milliseconds")
                    if evt.get("tipo") == "telemetria":
                        motor.tratar_telemetria(evt, ts_broker)
                    elif evt.get("tipo") == "classificacao":
                        motor.tratar_classificacao(evt)
                    M_ULTIMO.set_to_current_time()
                except Exception:  # noqa: BLE001 - uma mensagem ruim não derruba o motor
                    log.exception("falha ao processar mensagem", extra={"topico": msg.topic()})
                M_PROC.observe(time.perf_counter() - t0)

            if time.time() - ultimo_ciclo >= AVALIAR_SEG and motor.janela:
                motor.avaliar_ciclo()
                ultimo_ciclo = time.time()
    finally:
        consumer.close()


if __name__ == "__main__":
    main()
