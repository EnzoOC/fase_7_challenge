"""Testes das regras R1..R6 (Fase 3) aplicadas sobre a janela do stream (Fase 4)."""

from agregacao import agregar, aplicar_regras


def amostra(regiao, label, cultura="Milho", condicao=None, mes="Jan", correta=True, conf=90.0):
    return {"cultura": cultura, "condicao": condicao or ("Saudável" if label == "Saudável" else "Ferrugem Comum"),
            "label": label, "confianca": conf, "correta": correta, "mes": mes, "regiao": regiao}


def regras_disparadas(registros):
    return {(a.regra_id, a.alvo) for a in aplicar_regras(agregar(registros))}


def test_r1_infestacao_regional():
    janela = [amostra("Zona Norte", "Doente")] * 6 + [amostra("Zona Norte", "Saudável")] * 4
    assert ("R1", "Zona Norte") in regras_disparadas(janela)


def test_r5_zona_saudavel():
    janela = [amostra("Centro", "Saudável")] * 20
    assert ("R5", "Centro") in regras_disparadas(janela)


def test_r4_modelo_com_baixa_qualidade():
    janela = [amostra("Centro", "Saudável", correta=False, conf=60)] * 10
    assert any(r == "R4" for r, _ in regras_disparadas(janela))


def test_r6_tendencia_de_piora():
    jan = [amostra("Centro", "Doente", mes="Jan")] * 2 + [amostra("Centro", "Saudável", mes="Jan")] * 8
    fev = [amostra("Centro", "Doente", mes="Fev")] * 6 + [amostra("Centro", "Saudável", mes="Fev")] * 4
    assert ("R6", "Fev") in regras_disparadas(jan + fev)


def test_janela_vazia_nao_quebra():
    assert aplicar_regras(agregar([])) == []
