# 2. Execução da Plataforma (Sistema Funcional)

## 2.1 Como o sistema funciona

A plataforma roda **continuamente e sozinha**: depois do `docker compose up`, ninguém precisa
apertar nenhum botão. Cada parte faz o seu trabalho e passa o resultado adiante pelo Kafka.

| Etapa | O que acontece | Serviço |
|---|---|---|
| **Entrada** | 5 nós IoT enviam uma leitura a cada 3 s (temperatura, umidade do solo, luminosidade). O classificador de imagens envia de 6 a 9 classificações de folhas a cada 2 s. | `ingestao-iot`, `ingestao-visao` |
| **Processamento** | O motor valida cada leitura, calcula o índice de estresse hídrico e classifica o solo (IDEAL / ALERTA / CRÍTICO). As classificações de imagem entram numa janela das últimas 500 amostras. | `motor` |
| **Automação** | **R7** decide na hora se a leitura exige ação (com *cooldown* para não repetir alertas). **R1–R6** são reavaliadas a cada 5 s sobre a janela de imagens. | `motor` |
| **Saída** | Alertas viram mensagens: WhatsApp para o gerente (crítico), push no app do agrônomo (preventivo), e-mail (sanidade). O dashboard mostra tudo ao vivo e o Grafana mostra a saúde da operação. | `notificador`, `api`, `dashboard`, `grafana` |

### Comportamentos reais simulados (e tratados)

| Situação de campo | Como a plataforma reage |
|---|---|
| Sensor com defeito (valor nulo, −1 ou 999) | Leitura **rejeitada** com o motivo registrado; não gera decisão errada. |
| Nó perde a conexão | O nó guarda as leituras em **buffer** e reenvia tudo quando volta. O motor processa normalmente e o atraso fica registrado. |
| Talhão continua em ALERTA | **Cooldown** de 60 s por talhão: só alerta de novo se piorar ou se o tempo passar. |
| Gateway de mensagem falha | **Reenvio** automático (até 3 tentativas, com espera de 3 s). |
| Região entra em surto de doença | R1/R2/R3 disparam; apenas alertas **novos** e graves geram e-mail. |

## 2.2 Exemplo de entrada e saída (dados reais da execução)

### Entrada — leitura do sensor (tópico `telemetria-iot`)

Mesmo formato do protótipo Tinkercad da Fase 6, agora com identificador e horário de coleta:

```json
{
  "tipo": "telemetria",
  "leitura_id": "TINKER-TALHAO-01-11242155-00054",
  "device_id": "TINKER-TALHAO-01",
  "ts_coleta": "2026-11-24T21:58:31.809+00:00",
  "temperatura_c": 29.66,
  "luminosidade_pct": 74.2,
  "umidade_solo_pct": 33.8,
  "firmware": "1.2.0"
}
```

### Processamento — registro tratado (camada Silver, tabela `telemetria`)

| talhão | região | cultura | temp. | umidade | índice de estresse | status |
|---|---|---|---|---|---|---|
| T01 | Zona Norte | Milho | 29,66 °C | 33,8 % | **60,69** = 29,66 × 1,5 − 33,8 + 50 | **CRÍTICO** |

### Saída 1 — alerta gerado pelo motor (tópico `alertas`)

```json
{
  "regra_id": "R7",
  "regra_nome": "Estresse hídrico no talhão",
  "severidade": "CRITICA",
  "alvo": "T01 · Zona Norte (TINKER-TALHAO-01)",
  "mensagem": "Índice de estresse hídrico extremamente alto (60.69)",
  "recomendacao": "Iniciar irrigação imediatamente e suspender aplicação foliar devido à alta evaporação.",
  "canal": "whatsapp",
  "case_id": "TINKER-TALHAO-01-11242155-00054"
}
```

### Saída 2 — notificação ao produtor + rastreio completo (event log)

| Atividade | Horário (UTC) | Quem executou |
|---|---|---|
| Leitura coletada | 21:58:31.809 | TINKER-TALHAO-01 |
| Leitura recebida no broker | 21:58:31.810 | kafka |
| Leitura validada | 21:58:31.811 | motor |
| Índice de estresse calculado (60,69 → CRÍTICO) | 21:58:31.812 | motor |
| Alerta crítico gerado | 21:58:31.813 | motor |
| Envio iniciado | 21:58:32.321 | gateway-whatsapp |
| **Falha no envio** (tentativa 1) | 21:58:34.753 | gateway-whatsapp |
| **Notificação enviada** (2 tentativas) | 21:58:40.328 | gateway-whatsapp |

**Da coleta no campo até o WhatsApp do gerente: 8,5 segundos, incluindo uma falha e um reenvio automático.**
O processamento interno (validação → decisão) levou **4 ms**.

### Saída 3 — API e dashboard

- `GET /api/status` → `{"status": "operacional", "dispositivos_ativos": 5, ...}`
- `GET /api/telemetria` → última leitura de cada talhão + histórico (alimenta a aba **Campo IoT**)
- `GET /api/alertas.json` → alertas R1–R7 no formato que o dashboard já usava desde a Fase 3

Todos os arquivos de exemplo (gerados pela plataforma em execução) estão em
[`evidencias/exemplos/`](../evidencias/exemplos/):

| Arquivo | Conteúdo |
|---|---|
| `entrada_telemetria_iot.jsonl` | Mensagens reais do tópico de telemetria |
| `entrada_classificacao_imagem.jsonl` | Mensagens reais do classificador de imagens |
| `saida_alerta_kafka.jsonl` | Alertas publicados pelo motor |
| `rastreio_caso_alerta_critico.txt` | O caso acima, consultado direto no banco |
| `saida_api_*.json` | Respostas da API (status, telemetria, alertas, notificações, números) |

## 2.3 Evidências da execução

| Evidência | Arquivo |
|---|---|
| Containers em execução (`docker compose ps`) | `evidencias/01_containers_rodando.txt` |
| Dashboard — aba Campo IoT ao vivo | `evidencias/02_dashboard_campo_iot.png` e `02b_dashboard_campo_iot_topo.png` |
| API com documentação interativa | `evidencias/09_api_docs_swagger.png` |
| Consumo de recursos dos containers (~740 MB no total) | `evidencias/consumo_recursos.txt` |
| Logs estruturados dos serviços | `evidencias/logs/` |
| Execução completa no GitHub Actions (job "Teste ponta a ponta") | artefato `evidencias-execucao` do pipeline |
