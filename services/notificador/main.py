"""
Notificador AgroSmart — saída "para o produtor" dos alertas do motor.

Consome o tópico `alertas` e simula o envio pelos canais do Business Model
Canvas (Fase 4): WhatsApp para alertas críticos, push no app para alertas
preventivos e e-mail para alertas de sanidade (R1..R6).

O envio é feito por um único worker que respeita o tempo de resposta do
gateway de cada canal e faz até N tentativas com backoff. Isso reproduz o
comportamento real de APIs externas — e é exatamente o tipo de ponto que a
mineração de processos revela como GARGALO.

Métricas Prometheus em :9102/metrics.
"""

from __future__ import annotations

import json
import random
import time
from datetime import UTC, datetime

from confluent_kafka import Consumer, TopicPartition
from prometheus_client import Counter, Gauge, Histogram, start_http_server

import db
from config import KAFKA_BOOTSTRAP, TOPICO_ALERTAS, env_float, env_int
from kafka_util import criar_topicos, esperar_kafka
from logs import get_logger

log = get_logger("notificador")

# Tempo de resposta (segundos) de cada gateway: (mínimo, máximo)
LATENCIA = {
    "whatsapp": (env_float("LAT_WHATSAPP_MIN", 2.0), env_float("LAT_WHATSAPP_MAX", 6.0)),
    "app": (env_float("LAT_APP_MIN", 0.3), env_float("LAT_APP_MAX", 1.2)),
    "email": (env_float("LAT_EMAIL_MIN", 0.8), env_float("LAT_EMAIL_MAX", 2.5)),
}
PROB_FALHA = env_float("PROB_FALHA_ENVIO", 0.08)
MAX_TENTATIVAS = env_int("MAX_TENTATIVAS", 3)
BACKOFF_SEG = env_float("BACKOFF_SEG", 3.0)

M_NOTIF = Counter("agrosmart_notificacoes_total", "Notificações processadas", ["canal", "resultado"])
M_FALHAS = Counter("agrosmart_notificacoes_falhas_tentativa_total", "Tentativas de envio com falha", ["canal"])
M_ESPERA = Histogram("agrosmart_notificacao_espera_seconds",
                     "Tempo que o alerta esperou na fila até o envio começar",
                     buckets=(0.5, 1, 2, 5, 10, 20, 30, 60, 120, 300, 600))
M_ENVIO = Histogram("agrosmart_notificacao_envio_seconds", "Duração do envio (inclui reenvios)",
                    ["canal"], buckets=(0.25, 0.5, 1, 2, 4, 8, 16, 32))
M_FILA = Gauge("agrosmart_notificador_fila", "Alertas aguardando envio (lag do consumidor)")

rng = random.Random()


def agora_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds")


def atualizar_fila(consumer: Consumer, msg) -> None:
    try:
        _, alto = consumer.get_watermark_offsets(TopicPartition(msg.topic(), msg.partition()), timeout=1)
        M_FILA.set(max(0, alto - msg.offset() - 1))
    except Exception as e:  # noqa: BLE001 - métrica auxiliar, não interrompe o envio
        log.debug("não foi possível medir a fila", extra={"erro": str(e)})


def enviar(alerta: dict) -> tuple[bool, int, list[dict]]:
    """Simula o envio com reenvio. Retorna (sucesso, tentativas, eventos)."""
    canal = alerta.get("canal", "app")
    lat_min, lat_max = LATENCIA.get(canal, (0.5, 1.5))
    eventos: list[dict] = []
    for tentativa in range(1, MAX_TENTATIVAS + 1):
        time.sleep(rng.uniform(lat_min, lat_max))
        if rng.random() >= PROB_FALHA:
            return True, tentativa, eventos
        M_FALHAS.labels(canal).inc()
        eventos.append({"atividade": "Falha no envio", "ts": agora_iso(), "recurso": f"gateway-{canal}",
                        "atributos": {"tentativa": tentativa}})
        log.warning("falha no envio — reenviando", extra={"case_id": alerta.get("case_id"),
                                                          "canal": canal, "tentativa": tentativa})
        if tentativa < MAX_TENTATIVAS:
            time.sleep(BACKOFF_SEG)
    return False, MAX_TENTATIVAS, eventos


def main() -> None:
    start_http_server(9102)
    esperar_kafka(log)
    criar_topicos(log)
    conn = db.get_conn()
    db.init_schema(conn)

    consumer = Consumer({
        "bootstrap.servers": KAFKA_BOOTSTRAP,
        "group.id": "notificador",
        "auto.offset.reset": "latest",
        "max.poll.interval.ms": 600000,
    })
    consumer.subscribe([TOPICO_ALERTAS])
    log.info("notificador pronto", extra={"canais": list(LATENCIA)})

    while True:
        msg = consumer.poll(1.0)
        if msg is None or msg.error():
            continue
        atualizar_fila(consumer, msg)
        try:
            alerta = json.loads(msg.value())
        except ValueError:
            log.error("mensagem de alerta inválida")
            continue

        case, proc, canal = alerta.get("case_id"), alerta.get("processo"), alerta.get("canal", "app")
        inicio = time.time()
        try:
            gerado = datetime.fromisoformat(alerta["gerado_em"]).timestamp()
            M_ESPERA.observe(max(0.0, inicio - gerado))
        except (KeyError, ValueError):
            pass

        eventos = [{"atividade": "Envio iniciado", "ts": agora_iso(), "recurso": f"gateway-{canal}"}]
        ok, tentativas, ev_falhas = enviar(alerta)
        eventos += ev_falhas
        M_ENVIO.labels(canal).observe(time.time() - inicio)
        if ok:
            eventos.append({"atividade": "Notificação enviada", "ts": agora_iso(),
                            "recurso": f"gateway-{canal}", "atributos": {"tentativas": tentativas}})
            M_NOTIF.labels(canal, "enviada").inc()
            db.inserir_notificacao(conn, {"case_id": case, "regra_id": alerta.get("regra_id"),
                                          "severidade": alerta.get("severidade"),
                                          "alvo": alerta.get("alvo"), "canal": canal,
                                          "tentativas": tentativas})
            log.info("notificação enviada", extra={"case_id": case, "canal": canal,
                                                   "tentativas": tentativas,
                                                   "regra": alerta.get("regra_id")})
        else:
            eventos.append({"atividade": "Notificação descartada", "ts": agora_iso(),
                            "recurso": f"gateway-{canal}"})
            M_NOTIF.labels(canal, "descartada").inc()
            log.error("notificação descartada após tentativas", extra={"case_id": case, "canal": canal})

        db.registrar_eventos(conn, [dict(e, case_id=case, processo=proc) for e in eventos])


if __name__ == "__main__":
    main()
