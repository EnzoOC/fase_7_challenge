"""Testes do processamento Bronze → Silver (fórmula e validação da Fase 6)."""

import pytest

from processamento import calcular_indice_estresse, classificar_status, processar, validar_leitura

BASE = {"leitura_id": "X-1", "device_id": "TINKER-TALHAO-01", "ts_coleta": "2026-11-24T12:00:00+00:00",
        "temperatura_c": 24.78, "umidade_solo_pct": 47.0, "luminosidade_pct": 56.0}


def test_indice_reproduz_exemplo_da_fase6():
    # Mesmo valor exibido no dashboard da Fase 6 (24.78 °C, 47% → 40.17)
    assert calcular_indice_estresse(24.78, 47.0) == 40.17


@pytest.mark.parametrize("indice,status", [(10, "IDEAL"), (40, "IDEAL"), (40.01, "ALERTA"),
                                           (60, "ALERTA"), (60.5, "CRÍTICO")])
def test_classificacao_por_faixa(indice, status):
    assert classificar_status(indice) == status


def test_leitura_valida_e_enriquecida():
    r = processar(BASE)
    assert r["valida"] and r["motivo_rejeicao"] is None
    assert r["indice_estresse"] == 40.17 and r["status_solo"] == "ALERTA"


@pytest.mark.parametrize("campo,valor", [("umidade_solo_pct", None), ("temperatura_c", 999.0),
                                          ("luminosidade_pct", -1.0), ("temperatura_c", "abc")])
def test_leitura_invalida_e_rejeitada(campo, valor):
    r = processar(dict(BASE, **{campo: valor}))
    assert r["valida"] is False
    assert campo in r["motivo_rejeicao"]
    assert r["indice_estresse"] is None


def test_sem_device_id():
    ok, motivo = validar_leitura(dict(BASE, device_id=""))
    assert not ok and "device_id" in motivo


def test_salto_implausivel_de_temperatura_e_rejeitado():
    # Valor dentro da faixa física, mas impossível 3 s depois de 24,7 °C (falha real observada)
    anterior = dict(BASE, temperatura_c=24.71)
    r = processar(dict(BASE, temperatura_c=-1.0), anterior)
    assert r["valida"] is False and "salto implausível" in r["motivo_rejeicao"]


def test_variacao_normal_de_temperatura_e_aceita():
    anterior = dict(BASE, temperatura_c=24.0)
    assert processar(dict(BASE, temperatura_c=25.1), anterior)["valida"] is True
