"""Testes da regra R7 (estresse hídrico) e do controle de cooldown."""

from processamento import processar
from regras_iot import ControleCooldown, r7_estresse_hidrico

TALHAO = {"talhao": "T01", "regiao": "Zona Norte", "cultura": "Milho"}


def leitura(temp, umid):
    return processar({"leitura_id": "L1", "device_id": "D1", "ts_coleta": "2026-11-24T12:00:00+00:00",
                      "temperatura_c": temp, "umidade_solo_pct": umid, "luminosidade_pct": 50})


def test_r7_sem_alerta_quando_ideal():
    assert r7_estresse_hidrico(leitura(20, 70), TALHAO) is None


def test_r7_preventivo_quando_alerta():
    a = r7_estresse_hidrico(leitura(25, 45), TALHAO)
    assert a.regra_id == "R7" and a.severidade == "MEDIA"
    assert "T01" in a.alvo and a.dados_suporte["cultura"] == "Milho"


def test_r7_critico():
    a = r7_estresse_hidrico(leitura(33, 20), TALHAO)
    assert a.severidade == "CRITICA" and "irrigação" in a.recomendacao


def test_cooldown_suprime_repeticao_e_libera_apos_expirar():
    c = ControleCooldown(60)
    assert c.avaliar("D1", "ALERTA", 0) is True
    assert c.avaliar("D1", "ALERTA", 30) is False      # repetido dentro do cooldown
    assert c.avaliar("D1", "ALERTA", 61) is True       # expirou


def test_cooldown_libera_quando_piora():
    c = ControleCooldown(60)
    assert c.avaliar("D1", "ALERTA", 0) is True
    assert c.avaliar("D1", "CRÍTICO", 5) is True       # piorou → alerta imediato
    assert c.avaliar("D1", "ALERTA", 10) is False      # melhorou um pouco → não insiste


def test_cooldown_reinicia_quando_volta_ao_ideal():
    c = ControleCooldown(60)
    c.avaliar("D1", "ALERTA", 0)
    assert c.avaliar("D1", "IDEAL", 5) is False
    assert c.avaliar("D1", "ALERTA", 6) is True        # novo episódio


def test_cooldown_independente_por_dispositivo():
    c = ControleCooldown(60)
    assert c.avaliar("D1", "ALERTA", 0) is True
    assert c.avaliar("D2", "ALERTA", 1) is True
