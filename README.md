# 🌱 AgroSmart — Plataforma de Monitoramento Agrícola Inteligente

**FIAP · Fase 7 — Entrega final do projeto (PBL)**

O AgroSmart monitora a lavoura em tempo real e **decide sozinho** quando o produtor precisa agir.
Sensores IoT no campo e visão computacional nas folhas alimentam um motor de regras que detecta
estresse hídrico e surtos de doenças e envia o alerta certo, pelo canal certo, para a pessoa certa.

Esta entrega consolida tudo o que foi construído ao longo do ano em uma plataforma única,
containerizada, monitorada, com pipeline DevSecOps e análise do processo por mineração de processos.

| Fase | O que foi construído | Onde está na plataforma |
|---|---|---|
| 1 | Classificador de doenças (Random Forest · PlantVillage) | `services/ingestao_visao/` (resultados reais do classificador) |
| 2 | Dashboard analítico em React | `services/dashboard/` (abas Visão Geral, Doenças, Tendências, Regiões) |
| 3 | Motor de regras R1–R6 e ações automáticas | `services/motor/regras.py` (reaproveitado **sem alteração**) |
| 4 | Pipeline de streaming Kafka + PostgreSQL + API + Docker | Base de toda a arquitetura |
| 5 | Data Lake, governança e qualidade de dados | Validação das leituras, camadas Bronze → Silver |
| 6 | Sensores IoT (Tinkercad) e índice de estresse hídrico | `services/ingestao_iot/` + regra **R7** em tempo real |
| **7** | **Execução automatizada, DevSecOps, monitoramento, process mining, produto** | **Esta entrega** |

---

## ▶️ Como executar

Pré-requisito: **Docker** (com Docker Compose) **ou Podman** (com `podman-compose`). ~1 GB de RAM livre.

```bash
cp .env.example .env            # ajuste as senhas se quiser
docker compose up -d --build    # ou: podman-compose up -d --build
```

Em ~1 minuto a plataforma inteira está rodando:

| O quê | Endereço |
|---|---|
| 🖥️ Dashboard (produto) | http://localhost:8080 |
| 📈 Grafana — monitoramento | http://localhost:3000 (usuário/senha do `.env`) |
| 🔥 Prometheus — métricas e alertas operacionais | http://localhost:9090 |
| ⚙️ API + documentação interativa | http://localhost:8000/docs |
| 🧾 Event log (process mining) | http://localhost:8000/api/event-log.csv |

Análise de mineração de processos (depois de alguns minutos rodando):

```bash
docker compose --profile analise run --rm process-mining
# resultados em process_mining/saida/ (relatório, mapas do processo, variantes, event log)
```

Parar: `docker compose down` (mantém o banco) · `docker compose down -v` (apaga tudo).

Testes e verificações locais:

```bash
pip install -r requirements-dev.txt -r services/motor/requirements.txt -r services/api/requirements.txt
pytest --cov          # testes unitários
ruff check .          # qualidade de código
bandit -c pyproject.toml -r services   # segurança do código
```

---

## 🗂️ Estrutura

```
├── services/
│   ├── ingestao_iot/      Simulador dos nós IoT de campo (Fase 6) → Kafka
│   ├── ingestao_visao/    Eventos do classificador de imagens (Fases 1-2) → Kafka
│   ├── motor/             Motor de decisão: validação, índice de estresse, regras R1–R7
│   ├── notificador/       Envio de alertas (WhatsApp / app / e-mail) com reenvio
│   ├── api/               API FastAPI (dados, status, event log, métricas)
│   ├── comum/             Código compartilhado (config, banco, logs, Kafka)
│   ├── dashboard/         Painel React (Campo IoT + análises das fases anteriores)
│   └── Dockerfile.python  Imagem única e sem root para os serviços Python
├── monitoring/            Prometheus (coleta + regras de alerta) e Grafana (painel pronto)
├── process_mining/        Análise de mineração de processos (pm4py)
├── tests/                 Testes automatizados (pytest)
├── .github/workflows/     Pipeline DevSecOps (GitHub Actions)
├── docs/                  Documentação de cada requisito da entrega
├── evidencias/            Prints, logs e exemplos de execução
└── docker-compose.yml     Toda a plataforma em um comando
```

## 📚 Documentação da entrega

| Requisito | Documento |
|---|---|
| 1. Arquitetura final | [docs/01_arquitetura.md](docs/01_arquitetura.md) |
| 2. Execução da plataforma | [docs/02_execucao.md](docs/02_execucao.md) |
| 3. Pipeline DevSecOps | [docs/03_devsecops.md](docs/03_devsecops.md) |
| 4. Monitoramento | [docs/04_monitoramento.md](docs/04_monitoramento.md) |
| 5. Análise de processo | [docs/05_analise_processo.md](docs/05_analise_processo.md) |
| 6. Produto (pitch) | [docs/06_produto_pitch.md](docs/06_produto_pitch.md) |
| Roteiros dos vídeos | [docs/07_roteiros_videos.md](docs/07_roteiros_videos.md) |
