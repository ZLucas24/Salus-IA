# SalUS.ia — Linha do tempo do atendimento

Da chegada do paciente até a chamada para o médico. Versão de trabalho (19/10/2026).
As decisões clínicas (limites, sinais de alerta, intervalos) ainda precisam de revisão por enfermeiro ou médico.

---

## 1. Visão geral

O paciente chega, passa pela triagem (entrevista e aferições), recebe uma cor e uma posição na fila, espera com a possibilidade de voltar à triagem a qualquer momento e, por fim, é chamado para o atendimento médico.

Princípios que valem em todas as etapas:

- A **decisão final é sempre do profissional de saúde.**
- A IA **nunca reduz** uma pontuação.
- A pontuação e a cor vêm de **regras explícitas e de um modelo de classificação**, nunca do modelo de linguagem.
- Todo o processo gera **log de auditoria** (entrada, regra ou coeficiente aplicado, resultado, horário).

## 2. Linha do tempo

| # | Momento | Quem | O que acontece | O que fica registrado |
|---|---|---|---|---|
| 0 | Chegada e cadastro | Recepção | Identificação básica e entrada na ficha | Horário de chegada, idade, sexo |
| 1 | Início da triagem | Enfermagem e agente | O agente conduz o núcleo de perguntas (4.1). Sinal de alerta grave avisa a enfermagem na hora | Respostas, trechos do relato, horário de início |
| 2 | Aferições | Enfermagem (em paralelo à etapa 1) | Temperatura, saturação, pressão, frequências, glicemia e Glasgow, conforme o caso (4.2) | Valores, horário e responsável |
| 3 | Escolha de módulos | Agente | Com base no relato, principalmente no núcleo, ativa um ou mais módulos (4.3) e faz as perguntas correspondentes | Respostas dos módulos |
| 4 | Conferência | Profissional | Revisa na tela o que o agente marcou, com o trecho do relato, e corrige se preciso | Achados confirmados |
| 5 | Classificação | Script | Regras explícitas para achados gravíssimos, depois o modelo de classificação ordinal. Gera a cor sugerida e a pontuação dentro da cor | Cor e pontuação sugeridas, regra ou coeficientes aplicados |
| 6 | Decisão | Enfermeiro | Confirma ou altera a cor. A decisão final é humana | Cor final, divergência em relação à sugestão, horário |
| 7 | Entrada na fila | Sistema | Posição ordenada por cor e pontuação. QR code ou senha impressa com posição e previsão de espera em faixa | Horário de entrada na fila |
| 8 | Espera e reavaliação | Enfermagem e paciente | O paciente pode **voltar à triagem a qualquer momento**. Reaferições e botão de piora (mini-questionário). Sinal grave alerta a enfermagem. A tabela é atualizada e o modelo roda de novo, podendo subir a pontuação ou a cor | Cada reaferição, cada alerta, cada mudança de cor |
| 9 | Chamada | Equipe | O paciente sai da fila e vai ao atendimento médico | Horário da chamada |

## 3. Detalhes por etapa

### Etapa 1 e 2 — Entrevista e aferições

- O agente sempre conduz o **núcleo (4.1)**. A enfermagem registra as **aferições (4.2)** em paralelo.
- O agente não espera as aferições para seguir, mas confere se estão preenchidas e avisa o que falta.
- Aferição não feita fica como **"não aferido"**, nunca como normal.

### Etapa 3 — Módulos

- A escolha do módulo parte da interpretação do que o paciente disse. Se as aferições já estiverem disponíveis, ajudam a decidir.
- Pode haver **mais de um módulo** (por exemplo, dor no peito com falta de ar ativa o de peito e o respiratório).
- Se nada se encaixar, fica só o núcleo e o agente avisa o profissional.

### Etapa 4 — Conferência

- O agente converte o relato em achados estruturados (lista fechada de IDs do banco de perguntas).
- A tela mostra cada achado com o trecho do relato que o originou.
- O profissional corrige antes de seguir. Achado incerto é sinalizado, não escondido.

### Etapa 5 — Classificação

1. **Regras explícitas** tratam os achados gravíssimos e sobrepõem o modelo.
2. O **modelo de classificação ordinal** define a cor a partir da tabela de achados e aferições.
3. A **pontuação de 0 a 100** dentro da cor ordena a fila. Ao chegar a 100, o paciente sobe de cor.
4. A pontuação só pode aumentar com novos achados ou novas aferições.

### Etapa 6 — Decisão do enfermeiro

- O enfermeiro confirma ou altera a cor sugerida.
- Quando a cor final diverge da sugestão, a **divergência é registrada** com o horário. Esse registro é a base para melhorar o modelo no futuro, sempre com revisão clínica antes de qualquer ajuste.

### Etapa 8 — Espera e reavaliação

- **O paciente pode voltar à triagem a qualquer momento**, sem restrição de intervalo ou de cor.
- Na volta, repetem-se as aferições necessárias e, se for o caso, perguntas do núcleo e dos módulos.
- O botão de piora usa um mini-questionário. O aviso **não substitui chamar a equipe**, e isso deve estar claro na página.
- Sinal grave no questionário alerta a enfermagem imediatamente.
- Cada reavaliação atualiza a tabela, roda o modelo de novo e pode mudar posição, pontuação ou cor, sempre sem reduzir.

## 4. Emergência: atalho direto ao médico

Se na etapa 1 aparecer um **sinal gravíssimo** (vermelho evidente), o paciente vai direto ao médico, sem esperar a entrevista completa. A classificação é feita em seguida, apenas como registro.

A lista de sinais que acionam o atalho precisa ser definida e validada pelo revisor clínico.

## 5. Horários registrados e tempo de espera

Os horários abaixo permitem calcular o tempo de espera por cor sem trabalho extra:

| Horário | Etapa |
|---|---|
| `t_chegada` | 0 |
| `t_inicio_triagem` | 1 |
| `t_cor_sugerida` | 5 |
| `t_cor_final` | 6 |
| `t_entrada_fila` | 7 |
| `t_reavaliacao` (um por volta à triagem) | 8 |
| `t_chamada` | 9 |

Indicadores possíveis: tempo entre chegada e início da triagem, duração da triagem, tempo de fila por cor, número de reavaliações e de subidas de cor. Esses dados são **agregados e anonimizados** quando usados fora do atendimento (LGPD).

## 6. Decisões tomadas

1. **Emergência:** sinal gravíssimo leva o paciente direto ao médico, com a classificação feita depois como registro.
2. **Reavaliação livre:** todos os pacientes podem voltar à triagem a qualquer momento.
3. **Decisão da cor:** o enfermeiro confirma ou altera, e a divergência em relação à sugestão é registrada.

## 7. Pontos em aberto

- Lista de sinais gravíssimos que acionam o atalho direto ao médico (revisão clínica).
- Se a UPA exigirá também uma reavaliação ativa pela enfermagem em intervalos, além da volta livre pelo paciente (decisão clínica).
- Forma de avisar o paciente com pouco acesso a celular (senha impressa, painel na sala de espera).
- Quais dados da entrevista e das reavaliações são guardados e por quanto tempo (LGPD).
- Forma de calcular e exibir a previsão de espera em faixa, com parâmetros marcados como hipótese.
