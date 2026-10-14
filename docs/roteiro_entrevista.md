# Roteiro de entrevista

Guia para o atendente conduzir a entrevista de triagem do Salus IA. As perguntas
vêm de [triagem/dados/questionario.json](../triagem/dados/questionario.json). Se o questionário mudar, este roteiro deve mudar junto.

> Protótipo com **dados simulados**. Não use com pacientes reais.

## Princípios

- Leia as perguntas **como estão escritas**, na ordem, com calma e em linguagem simples.
- Registre o que o paciente **disse**, sem interpretar. Quem organiza os dados é o sistema, e ele **não decide gravidade**.
- Não insista nem sugira respostas. Se o paciente não souber ou não quiser responder, **deixe a pergunta em branco**: ela ficará como pendente, e isso é melhor que um chute.
- Se o paciente piorar ou aparentar urgência durante a entrevista, siga o protocolo do serviço e acione a equipe clínica. O roteiro não substitui esse julgamento.

## Antes de começar: dados do atendente

Preencha o que for medido ou observado. Só a **idade é obrigatória**.

| Dado | Observação |
|---|---|
| Idade | obrigatória, em anos |
| Temperatura | °C, se medida |
| Frequência cardíaca | batimentos por minuto |
| Pressão arterial | sistólica e diastólica (ex.: 120 e 80) |
| Saturação | %, se medida |

## Perguntas

### P01. Relato breve
**Pergunte:** "Em poucas palavras, o que trouxe você aqui hoje?"
**Registre:** as palavras do paciente, **no máximo 200 caracteres**. Não corrija nem
traduza para termos técnicos. Se ficar longo, resuma sem mudar o sentido.
**Alimenta:** queixa principal e qualquer sinal citado no relato.

### P02. Duração
**Pergunte:** "Há quanto tempo isso começou?"
**Registre:** número e unidade (minutos, horas, dias, semanas, meses ou anos).
Ex.: 2 horas.
**Dica:** se disser "desde ontem", converta com o paciente ("umas 20 horas? 1 dia?") e registre o que ele confirmar.

### P03. Início súbito
**Pergunte:** "Começou de repente?"
**Registre:** sim ou não.

### P04. Dor
**Pergunte:** "Está com dor? De 0 a 10, quanto?"
**Registre:** sim ou não e, se sim, a nota de 0 a 10.
**Dica:** explique a escala: 0 é sem dor e 10 é a pior dor imaginável. A nota é
obrigatória quando a resposta é sim.

### P05. Local da dor
**Pergunte:** "Onde é a dor?"
**Registre:** uma opção: cabeça, peito, abdome, costas, membros ou outro.
**Quando perguntar:** se o paciente negou dor na P04, pode deixar em branco.

### P06. Falta de ar
**Pergunte:** "Está com falta de ar?"
**Registre:** sim ou não.

### P07. Sangramento
**Pergunte:** "Há sangramento? Está sangrando agora?"
**Registre:** sim ou não para "há sangramento" e, se sim, sim ou não para
"sangrando agora". Não marque "agora" se não há sangramento.

### P08. Consciência e convulsão
**Pergunte:** "Desmaiou, ficou confuso ou teve convulsão?"
**Registre:** sim ou não **para cada item**: (a) desmaiou ou ficou confuso;
(b) teve convulsão.

### P09. Febre
**Pergunte:** "Teve febre? Mediu quanto?"
**Registre:** sim ou não e, se mediu, a temperatura em °C.
**Dica:** "febre" é o que o paciente relata. Se ele não mediu, registre só o sim e deixe o valor em branco.

### P10. Vômitos
**Pergunte:** "Está vomitando sem parar?"
**Registre:** sim ou não.

### P11. Trauma
**Pergunte:** "Sofreu queda, pancada ou acidente?"
**Registre:** sim ou não.

### P12. Gravidez e doenças crônicas
**Pergunte:** "Está grávida? Tem doença crônica (diabetes, coração, pressão, pulmão)?"
**Registre:** (a) grávida: sim ou não; (b) as doenças que o paciente citar entre diabetes, coração, pressão e pulmão. Se nenhuma, lista vazia.
**Cuidado:** faça a pergunta da gravidez com respeito e só quando fizer sentido para o paciente; se ela não se aplica ou o paciente prefere não responder, deixe em branco.

### P13. Alergia a medicamento
**Pergunte:** "Tem alergia a algum medicamento? Qual?"
**Registre:** sim ou não e, se sim, o nome de cada medicamento, separados por vírgula.
**Importante:** a alergia **não entra na pontuação**. É informação de segurança
para a equipe, então vale insistir gentilmente nesta pergunta.

## Depois da entrevista

1. Monte a ficha no formato descrito no [README](../README.md#formato-da-ficha).
2. Rode `python -m triagem ficha.json`.
3. Confira `perguntas_pendentes` no resultado: se der tempo, volte ao paciente e
   complete essas perguntas.
4. Lembre que o relato (P01) e as respostas fechadas podem divergir. Nesse caso
   **a resposta direta prevalece**, e o sistema registra a origem de cada sinal.

## Resumo para consulta rápida

| # | Pergunta | Resposta |
|---|---|---|
| P01 | O que trouxe você aqui hoje? | texto, até 200 caracteres |
| P02 | Há quanto tempo começou? | número + unidade |
| P03 | Começou de repente? | sim / não |
| P04 | Está com dor? De 0 a 10? | sim / não + nota |
| P05 | Onde é a dor? | uma opção |
| P06 | Falta de ar? | sim / não |
| P07 | Sangramento? Agora? | sim / não + sim / não |
| P08 | Desmaio/confusão? Convulsão? | sim / não para cada |
| P09 | Febre? Quanto? | sim / não + °C |
| P10 | Vomitando sem parar? | sim / não |
| P11 | Queda, pancada ou acidente? | sim / não |
| P12 | Grávida? Doença crônica? | sim / não + doenças |
| P13 | Alergia a medicamento? Qual? | sim / não + nomes |
