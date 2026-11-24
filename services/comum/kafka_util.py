"""Helpers Kafka compartilhados (espera do broker e criação de tópicos)."""

from __future__ import annotations

import time

from confluent_kafka.admin import AdminClient, NewTopic

from config import KAFKA_BOOTSTRAP, TOPICOS


def esperar_kafka(log, tentativas: int = 60) -> None:
    for i in range(tentativas):
        try:
            AdminClient({"bootstrap.servers": KAFKA_BOOTSTRAP}).list_topics(timeout=5)
            return
        except Exception as e:  # noqa: BLE001 - qualquer falha = broker ainda subindo
            log.info("aguardando Kafka", extra={"tentativa": i, "erro": str(e)})
            time.sleep(2)
    raise SystemExit("Kafka indisponível")


def criar_topicos(log) -> None:
    admin = AdminClient({"bootstrap.servers": KAFKA_BOOTSTRAP})
    novos = [NewTopic(t, num_partitions=1, replication_factor=1) for t in TOPICOS]
    for topico, fut in admin.create_topics(novos).items():
        try:
            fut.result()
            log.info("tópico criado", extra={"topico": topico})
        except Exception:  # noqa: BLE001 - já existe
            log.debug("tópico já existe", extra={"topico": topico})
