"""
Ingestão IoT — simulador dos nós de campo AgroSmart (evolução da Fase 6).

Cada talhão tem um nó Arduino/ESP32 (protótipo Tinkercad: TMP36 + LDR +
sensor de umidade do solo) que publica no tópico `telemetria-iot` o MESMO
payload JSON da Fase 6, agora de forma contínua e com comportamento físico:

  • ciclo dia/noite (temperatura e luminosidade);
  • o solo seca com o calor e é irrigado quando cai abaixo do limiar
    de irrigação de cada fazenda;
  • falhas reais de campo, para que o pipeline precise tratá-las:
      - leitura inválida (sensor com defeito / valor fora da faixa);
      - perda de conectividade: o nó guarda as leituras em buffer e as
        reenvia em lote quando volta a ficar online (offline-first).

Métricas Prometheus expostas em :9103/metrics.
"""

from __future__ import annotations

import math
import random
import time
from datetime import UTC, datetime, timedelta

from confluent_kafka import Producer
from prometheus_client import Counter, Gauge, start_http_server

from config import KAFKA_BOOTSTRAP, TALHOES, TOPICO_TELEMETRIA, env_float, env_int, jdumps
from kafka_util import criar_topicos, esperar_kafka
from logs import get_logger

log = get_logger("ingestao-iot")

INTERVALO = env_float("INTERVALO_IOT_SEG", 3.0)          # tempo real entre leituras
MINUTOS_SIM_POR_LEITURA = env_int("MINUTOS_SIM_POR_LEITURA", 10)
PROB_FALHA_SENSOR = env_float("PROB_FALHA_SENSOR", 0.03)
PROB_QUEDA_CONEXAO = env_float("PROB_QUEDA_CONEXAO", 0.012)

M_PUBLICADAS = Counter("agrosmart_iot_leituras_publicadas_total",
                       "Leituras publicadas no Kafka", ["device_id", "via"])
M_OFFLINE = Gauge("agrosmart_iot_device_offline", "1 se o nó está sem conexão", ["device_id"])
M_BUFFER = Gauge("agrosmart_iot_buffer_leituras", "Leituras guardadas no buffer offline", ["device_id"])

rng = random.Random()


class NoIoT:
    """Estado físico simplificado de um talhão."""

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.device_id = cfg["device_id"]
        self.umidade = rng.uniform(55, 75)
        # Cada fazenda tem um manejo diferente → gera variação no processo.
        self.limiar_irrigacao = rng.uniform(30, 42)
        self.offset_temp = rng.uniform(-2, 3)
        self.seq = 0
        self.offline_restante = 0
        self.buffer: list[dict] = []
        self.prefixo = datetime.now().strftime("%m%d%H%M")

    def ler(self, hora_sim: float) -> dict:
        self.seq += 1
        # Temperatura: mínima ~5h, máxima ~15h.
        temp = 23 + self.offset_temp + 7 * math.sin((hora_sim - 9) / 24 * 2 * math.pi) + rng.gauss(0, 0.6)
        luz = max(0.0, math.sin((hora_sim - 6) / 12 * math.pi)) * 100 if 6 <= hora_sim <= 18 else 0.0
        luz = min(100.0, max(0.0, luz + rng.gauss(0, 3)))

        # Evaporação proporcional ao calor; irrigação automática abaixo do limiar.
        self.umidade -= max(0.1, 0.35 + (temp - 22) * 0.06) + rng.gauss(0, 0.15)
        if self.umidade < self.limiar_irrigacao:
            self.umidade += rng.uniform(28, 40)
        self.umidade = min(95.0, max(5.0, self.umidade))

        leitura = {
            "tipo": "telemetria",
            "leitura_id": f"{self.device_id}-{self.prefixo}-{self.seq:05d}",
            "device_id": self.device_id,
            "ts_coleta": datetime.now(UTC).isoformat(timespec="milliseconds"),
            "temperatura_c": round(temp, 2),
            "luminosidade_pct": round(luz, 1),
            "umidade_solo_pct": round(self.umidade, 1),
            "firmware": "1.2.0",
        }
        if rng.random() < PROB_FALHA_SENSOR:
            defeito = rng.choice(["umidade_solo_pct", "temperatura_c", "luminosidade_pct"])
            leitura[defeito] = rng.choice([None, -1.0, 999.0])
        return leitura


def main() -> None:
    start_http_server(9103)
    esperar_kafka(log)
    criar_topicos(log)
    prod = Producer({"bootstrap.servers": KAFKA_BOOTSTRAP, "linger.ms": 20})
    nos = [NoIoT(c) for c in TALHOES]
    relogio = datetime(2026, 11, 1, 6, 0)
    log.info("simulador IoT iniciado", extra={"nos": len(nos), "intervalo_seg": INTERVALO})

    while True:
        hora = relogio.hour + relogio.minute / 60
        for no in nos:
            leitura = no.ler(hora)
            leitura["hora_simulada"] = relogio.strftime("%H:%M")

            if no.offline_restante == 0 and rng.random() < PROB_QUEDA_CONEXAO:
                no.offline_restante = rng.randint(6, 18)
                log.warning("nó perdeu conexão — bufferizando", extra={"device_id": no.device_id})

            if no.offline_restante > 0:
                no.buffer.append(leitura)
                no.offline_restante -= 1
                if no.offline_restante == 0:
                    for lb in no.buffer:
                        lb["reenviada_buffer"] = True
                        prod.produce(TOPICO_TELEMETRIA, key=no.device_id.encode(), value=jdumps(lb))
                        M_PUBLICADAS.labels(no.device_id, "buffer").inc()
                    log.info("nó reconectado — buffer reenviado",
                             extra={"device_id": no.device_id, "leituras": len(no.buffer)})
                    no.buffer.clear()
            else:
                prod.produce(TOPICO_TELEMETRIA, key=no.device_id.encode(), value=jdumps(leitura))
                M_PUBLICADAS.labels(no.device_id, "online").inc()

            M_OFFLINE.labels(no.device_id).set(1 if no.offline_restante > 0 else 0)
            M_BUFFER.labels(no.device_id).set(len(no.buffer))

        prod.poll(0)
        prod.flush(5)
        relogio += timedelta(minutes=MINUTOS_SIM_POR_LEITURA)
        time.sleep(INTERVALO)


if __name__ == "__main__":
    main()
