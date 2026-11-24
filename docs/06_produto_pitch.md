# 6. Apresentação do Produto (Pitch)

> Base para os slides e para o vídeo pitch (até 5 min). Mantém a coerência com o
> Business Model Canvas da Fase 4 e o modelo de negócio da Fase 5.
> Os itens marcados com **[fonte]** devem ser completados pela equipe com um dado
> público e citado (ex.: Embrapa, CONAB, IBGE) antes da apresentação.

## Frase de impacto

> **"O AgroSmart não mostra gráficos para o produtor. Ele avisa o produtor, no WhatsApp,
> o que fazer, onde e agora."**

## 1. Problema resolvido

- O produtor só descobre o **estresse hídrico** ou a **doença** quando a planta já mostra o
  dano, e aí parte da produção já foi perdida. **[fonte: perdas anuais por pragas/doenças/seca no Brasil]**
- Os dados existem (sensores, imagens, clima), mas estão **espalhados** e **ninguém olha
  o painel o tempo todo**. Dashboard sem ação não salva safra.
- Quando o alerta existe, ele chega **atrasado** (área sem sinal) ou **em excesso** (o produtor
  passa a ignorar), o que se chama fadiga de alerta.
- A aplicação de defensivo e de água é feita **na área toda e por calendário**, não onde e
  quando é necessário: mais custo e mais impacto ambiental.

## 2. Solução proposta

Uma plataforma que **lê o campo continuamente, decide sozinha e avisa a pessoa certa**:

| Ouve | Entende | Age |
|---|---|---|
| Sensores IoT em cada talhão (umidade do solo, temperatura, luz) + imagens de folhas analisadas por IA | Motor de decisão com 7 regras agronômicas: estresse hídrico em tempo real (R7) e surtos de doença por região, cultura e mês (R1–R6) | WhatsApp para o gerente no caso crítico ("irrigar agora"), push para o agrônomo no preventivo, e-mail com o plano de contenção do surto |

E a operação é confiável:
- funciona com **sensores defeituosos** (rejeita o dado ruim) e **sem sinal** (o nó guarda e reenvia);
- não faz spam: o **cooldown** cortou **mais de 90%** das mensagens repetidas na operação medida;
- **monitorada 24/7** (Grafana) e entregue por um **pipeline DevSecOps** com segurança verificada a cada versão.

**Demonstração (dado real da plataforma):** o sensor do talhão T01 (milho) mediu 29,7 °C e
33,8% de umidade, o que dá índice 60,7 → **CRÍTICO**. O gateway do WhatsApp falhou na primeira
tentativa, o sistema reenviou sozinho, e o gerente recebeu a recomendação **8,5 segundos depois da
leitura**. A decisão em si levou 4 milissegundos.

## 3. Diferencial competitivo

| | Planilha / caderno de campo | Dashboards de IoT comuns | **AgroSmart** |
|---|---|---|---|
| Junta IoT + visão computacional | ❌ | ⚠️ geralmente só sensores | ✅ as duas fontes no mesmo motor |
| Decide e avisa sozinho | ❌ | ❌ o usuário precisa olhar | ✅ 7 regras + notificação por canal |
| Evita excesso de alertas | — | ❌ | ✅ cooldown por talhão |
| Funciona com sinal ruim e sensor com defeito | — | ⚠️ | ✅ buffer offline + validação de dados |
| Mede e melhora o próprio processo | ❌ | ❌ | ✅ event log + mineração de processos |
| Segurança verificada em cada versão | ❌ | ⚠️ | ✅ pipeline DevSecOps |

**Nosso fosso (o que é difícil de copiar):** a base de dados que cresce a cada safra (leituras +
imagens + decisões + desfecho). Com ela as regras ficam mais precisas por região e cultura,
e a análise de processo mostra onde melhorar.

## 4. Público-alvo

| Segmento | Dor principal | Como o AgroSmart ajuda |
|---|---|---|
| **Produtor de médio porte** (grãos, hortaliças, fruticultura) — cliente inicial | Não tem agrônomo em tempo integral | Alerta prático no WhatsApp com a ação recomendada |
| **Agrônomo / consultor** que atende várias fazendas | Não consegue visitar todas a tempo | Triagem automática: sabe qual talhão visitar primeiro |
| **Cooperativas agrícolas** | Precisam dar suporte técnico a muitos cooperados | Visão regional de surtos (R1/R3) + revenda white-label |
| **Seguradoras e indústria de insumos** (fase 2 do negócio) | Falta de dado confiável de campo | Dados agregados e anônimos de risco regional (DaaS) |

## 5. Proposta de valor

> **Para o produtor de médio porte que não pode ter um agrônomo olhando a lavoura o dia todo,
> o AgroSmart é a plataforma que monitora o campo 24 horas, decide e avisa no WhatsApp o que
> fazer, ao contrário dos dashboards que só mostram dados e esperam alguém olhar.**

| Ganho | Como |
|---|---|
| **Menos perda de safra** | Detecção no início (estresse hídrico e surto de doença) e ação em segundos |
| **Menos custo com água e defensivos** | Ação localizada por talhão, não na área toda (meta da Fase 5: até 30% menos defensivos — **hipótese a validar em piloto**) |
| **Tempo do agrônomo** | Vai direto ao talhão que precisa |
| **Confiança** | Recomendações explicadas (índice, regra, dado que gerou o alerta) e plataforma monitorada |

### Modelo de receita (resumo do BMC)

- **SaaS por hectare/safra** (Fase 5: R$ 8 a R$ 15 por hectare/safra), com planos por número de talhões
- **Add-on "AI Advisor"**: recomendações em linguagem natural (IA generativa + RAG, Fase 5)
- **Setup**: instalação e calibração de sensores
- **White-label** para cooperativas · **DaaS** para seguradoras e indústria

### Próximos passos (roadmap)

1. **Piloto** com 1 cooperativa (3 a 5 fazendas) para medir a redução real de perdas e de insumos
2. **Gateway de borda** no campo (principal gargalo encontrado na mineração de processos)
3. **Acionamento automático da irrigação** (fechar o ciclo sem intervenção humana)
4. **AI Advisor** (IA generativa) explicando o alerta em linguagem natural

## Estrutura sugerida dos slides (10 slides · ~5 min)

| # | Slide | Conteúdo | Tempo |
|---|---|---|---|
| 1 | Capa | AgroSmart + frase de impacto | 15 s |
| 2 | Problema | 3 dores (descobre tarde · dado sem ação · alerta demais/atrasado) + 1 número **[fonte]** | 40 s |
| 3 | Solução | Ouve → Entende → Age | 40 s |
| 4 | Como funciona | Diagrama da arquitetura simplificado | 30 s |
| 5 | Demonstração | Print do dashboard + caso T01 (8,5 s até o WhatsApp) | 40 s |
| 6 | Diferencial | Tabela comparativa | 30 s |
| 7 | Público-alvo | Segmentos + cliente inicial | 25 s |
| 8 | Proposta de valor e receita | Frase de valor + modelo por hectare | 30 s |
| 9 | Confiabilidade | DevSecOps + monitoramento + process mining (1 número de cada) | 20 s |
| 10 | Próximos passos + equipe | Roadmap + nomes | 20 s |
