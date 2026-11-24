# 7. Roteiros dos vídeos

Dois vídeos são exigidos:

| Vídeo | Duração | Foco |
|---|---|---|
| **A. Vídeo final** | 5 a 8 min | Demonstração da plataforma, fluxo, análise do processo, funcionamento completo |
| **B. Vídeo pitch** | até 5 min | O produto: problema, solução, diferencial, público, proposta de valor |

## Preparação (antes de gravar)

```bash
docker compose down -v            # começar do zero (banco vazio)
docker compose up -d --build
# esperar ~10-15 min rodando para ter dados e variações no event log
docker compose --profile analise run --rm process-mining
```

Deixe abertas as abas: Dashboard (`:8080`) · Grafana (`:3000`) · Prometheus Alerts (`:9090/alerts`)
· API docs (`:8000/docs`) · `process_mining/saida/relatorio_processo.md` · GitHub Actions (última execução verde).

Dicas: grave em 1080p, aumente o zoom do navegador (125%), feche notificações do sistema e
divida as falas entre os integrantes (cada um apresenta uma parte).

---

## A. Vídeo final (≈ 7 min)

| Tempo | Cena (tela) | Fala sugerida |
|---|---|---|
| 0:00–0:30 | Slide de capa / diagrama de arquitetura | "Somos a equipe AgroSmart. Nesta entrega final mostramos a plataforma completa funcionando de ponta a ponta: sensores, decisão automática, alertas, monitoramento e a análise do próprio processo." |
| 0:30–1:30 | `docs/img/arquitetura.png` | "A arquitetura junta tudo que construímos no ano. Na entrada, os sensores IoT da Fase 6 e o classificador de imagens das Fases 1 e 2. Tudo passa pelo Kafka, da Fase 4. O motor aplica as regras R1 a R6 da Fase 3, sem alteração, e a nova R7 de estresse hídrico. Na saída, o notificador manda WhatsApp, app ou e-mail; a API alimenta o dashboard; e o Prometheus e o Grafana monitoram tudo." |
| 1:30–2:00 | Terminal: `docker compose ps` | "A plataforma inteira sobe com um único comando. São 10 serviços, todos em container e rodando sem usuário root." |
| 2:00–3:15 | Dashboard → aba **Campo IoT** | "Aqui o produtor vê cada talhão ao vivo: temperatura, umidade do solo e o índice de estresse hídrico. Acima de 40 é alerta, acima de 60 é crítico. [apontar um talhão em alerta] Embaixo, as notificações que já foram enviadas, com o canal e o número de tentativas. No topo, a barra mostra que a plataforma está operacional." |
| 3:15–3:45 | Dashboard → aba **Automação** (botão "Ao vivo") | "Na aba Automação vemos os alertas das regras de sanidade, R1 a R6, calculados sobre as imagens classificadas, junto com os alertas R7 dos sensores." |
| 3:45–4:15 | `evidencias/exemplos/rastreio_caso_alerta_critico.txt` ou `docs/02_execucao.md` | "Um caso real: o talhão T01 ficou crítico. O motor decidiu em 4 milissegundos, o WhatsApp falhou na primeira tentativa, o sistema reenviou sozinho, e o gerente recebeu o alerta 8,5 segundos depois da leitura." |
| 4:15–5:00 | **Grafana** | "O Grafana mostra a saúde da operação: todos os serviços no ar, leituras por minuto, porcentagem de dados rejeitados, a fila de notificações e o índice de cada talhão. No Prometheus configuramos alertas operacionais, por exemplo se o motor parar ou se um sensor ficar offline." |
| 5:00–6:30 | `relatorio_processo.md` + `mapa_frequencia.png` + `mapa_desempenho.png` | "Cada passo de cada leitura gera um evento no event log. Com mineração de processos descobrimos o processo real. [mapa de frequência] Esta é a variante principal: a maioria das leituras termina com o solo ideal. As variações são: leitura rejeitada, alerta suprimido pelo cooldown, e falha com reenvio. [mapa de desempenho] O gargalo não está no processamento, que leva milissegundos. Está na borda: leituras que chegam atrasadas quando o sensor perde sinal. Por isso a primeira melhoria proposta é um gateway de borda no campo." |
| 6:30–7:00 | GitHub Actions (execução verde) | "Por fim, a cada push o pipeline DevSecOps faz lint, testes, análise de segurança do código, das dependências, de segredos e das imagens, e sobe a plataforma inteira para testar de ponta a ponta. Obrigado!" |

---

## B. Vídeo pitch (≈ 4 min 30 s)

> Use os slides (`docs/06_produto_pitch.md` → seção "Estrutura sugerida dos slides").
> Tom: conversa com um investidor ou um cliente, não aula técnica.

| Tempo | Slide | Fala sugerida |
|---|---|---|
| 0:00–0:20 | 1 · Capa | "O AgroSmart não mostra gráficos para o produtor. Ele avisa o produtor, no WhatsApp, o que fazer, onde e agora." |
| 0:20–1:00 | 2 · Problema | "Hoje o produtor descobre a seca no solo ou a doença na folha quando o estrago já aconteceu. [dado com fonte] Os dados até existem, mas ficam em painéis que ninguém olha o dia inteiro. E quando o alerta chega, chega atrasado ou chega demais, e o produtor passa a ignorar." |
| 1:00–1:40 | 3 · Solução | "O AgroSmart ouve, entende e age. Ouve: sensores em cada talhão e imagens das folhas analisadas por inteligência artificial. Entende: sete regras agronômicas, da seca à doença. Age: manda a recomendação certa, para a pessoa certa, no canal certo." |
| 1:40–2:20 | 5 · Demonstração | "Na nossa plataforma, o talhão de milho T01 entrou em estresse crítico. Em 8 segundos o gerente recebeu no WhatsApp: 'irrigar imediatamente'. Mesmo com falha na primeira tentativa de envio, o sistema reenviou sozinho." |
| 2:20–2:55 | 6 · Diferencial | "O que nos diferencia: juntamos sensores e visão computacional no mesmo motor, a plataforma decide sozinha, não faz spam, já que cortou mais de 90% dos alertas repetidos, e funciona mesmo com sinal ruim no campo." |
| 2:55–3:25 | 7 · Público-alvo | "Começamos pelo produtor de médio porte, que não tem um agrônomo em tempo integral, e pelas cooperativas, que levam a solução a centenas de cooperados." |
| 3:25–4:00 | 8 · Proposta de valor | "Para esse produtor, o AgroSmart é o agrônomo de plantão 24 horas: menos perda de safra, menos desperdício de água e defensivo. O modelo é por assinatura por hectare por safra, mais instalação dos sensores." |
| 4:00–4:30 | 10 · Próximos passos | "Nosso próximo passo é um piloto com uma cooperativa, para medir a economia real, e levar a decisão para a borda, direto no campo. Somos a equipe AgroSmart. Obrigado." |
