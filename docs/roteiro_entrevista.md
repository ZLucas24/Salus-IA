# Roteiro de entrevista

> Gerado automaticamente por `python -m triagem.roteiro` a partir de
> [triagem/dados/questionario.json](../triagem/dados/questionario.json). **Não edite à mão:**
> altere o questionário e gere de novo.

Guia para o atendente conduzir a entrevista de triagem do Salus IA. Protótipo com
**dados simulados**; não use com pacientes reais. O questionário ainda aguarda revisão por
enfermeiro ou médico.

## Princípios

- Leia as perguntas **como estão escritas**, uma de cada vez, em linguagem simples.
- Registre o que o paciente **disse**, sem interpretar. O sistema não decide gravidade.
- Se o paciente **não souber** ou **não quiser responder**, registre `"nao_sabe"` ou `"recusou"`
  no lugar da resposta. Isso **não** vale como "não": o sistema mantém o aviso. Se a pergunta
  não se aplica ao paciente, use `"nao_se_aplica"`.
- Não insista em pergunta que o paciente não quer ou não consegue responder.
- Não peça medidas numéricas ao paciente: temperatura, saturação, pressão e pulso vêm da
  aferição da enfermagem.
- Se houver sinal de alerta grave, avise a enfermagem imediatamente, sem esperar o fim.
- Se o paciente piorar durante a entrevista, siga o protocolo do serviço.

## Antes de começar: cadastro e aferições

Só a **idade é obrigatória**. Aferição que não foi feita fica **em branco** e vale como
"não aferida", nunca como normal.

| Campo | Observação |
|---|---|
| `idade` | obrigatória, em anos |
| `sexo_biologico` | `feminino`, `masculino`, `intersexo` ou `ausente` (padrão). Se ausente, as perguntas ligadas ao sexo continuam valendo |
| `temperatura` (E01) | Temperatura (°C) |
| `saturacao` (E02) | Saturação de oxigênio (%) |
| `frequencia_cardiaca` (E04) | Frequência cardíaca (bpm) |
| `frequencia_respiratoria` (E05) | Frequência respiratória (irpm) |
| `glicemia` (E06) | Glicemia capilar (diabetes, confusão ou suspeita de hipoglicemia) (mg/dL) |
| `glasgow` (E07) | Escala de consciência (Glasgow) (3 a 15) |
| `pressao_sistolica` e `pressao_diastolica` (E03) | pressão arterial (mmHg), as duas juntas |

## Segurança (nunca pular por suposição)

#### Q08

**Pergunte:** "Você desmaiou, ficou confuso ou sentiu que ia apagar?"  
**Serve para:** Sinal de alerta  
**Registre:** `true` ou `false`  
**Exemplo:** `"Q08": true`

#### Q09

**Pergunte:** "Está com falta de ar ou dificuldade para respirar?"  
**Serve para:** Sinal de alerta  
**Registre:** `true` ou `false`  
**Exemplo:** `"Q09": true`

#### Q10

**Pergunte:** "Tem alergia a algum remédio, alimento ou contraste de exame?"  
**Serve para:** Segurança (não entra na pontuação)  
**Registre:**

- `resposta`: `true` ou `false`
- `tipos`: lista com: `medicamento`, `alimento`, `contraste` (`[]` = nenhuma) — só se `resposta` for `true` (opcional)
- `texto`: texto curto — só se `resposta` for `true`

**Exemplo:** `"Q10": {"resposta": true, "tipos": ["medicamento"], "texto": "texto curto"}`

#### Q11

**Pergunte:** "Usa algum remédio, chá ou suplemento todos os dias? Algum para afinar o sangue ou insulina?"  
**Serve para:** Segurança e risco de sangramento  
**Registre:**

- `resposta`: `true` ou `false`
- `anticoagulante`: `true` ou `false` — só se `resposta` for `true`
- `insulina`: `true` ou `false` — só se `resposta` for `true`
- `texto`: texto curto — só se `resposta` for `true`

**Exemplo:** `"Q11": {"resposta": true, "anticoagulante": true, "insulina": true, "texto": "texto curto"}`

#### Q12

**Pergunte:** "Tomou algum remédio hoje, inclusive para febre ou dor? Que horas?"  
**Serve para:** Pode mascarar febre e dor  
**Registre:**

- `resposta`: `true` ou `false`
- `classes`: lista com: `antitermico`, `analgesico`, `outro` (`[]` = nenhuma) — só se `resposta` for `true`
- `texto`: texto curto — só se `resposta` for `true`
- `ha`: número e unidade (minutos, horas, dias) — só se `resposta` for `true`

**Exemplo:** `"Q12": {"resposta": true, "classes": ["antitermico"], "texto": "texto curto", "ha": {"valor": 2, "unidade": "horas"}}`

#### Q13

**Pergunte:** "Tem alguma doença diagnosticada, como diabetes, pressão alta, problema no coração, pulmão ou rim?"  
**Serve para:** Comorbidades (lista vazia significa nenhuma)  
**Registre:** lista com: `diabetes`, `hipertensao`, `cardiopatia`, `pneumopatia`, `renopatia`, `outra` (`[]` = nenhuma)  
**Exemplo:** `"Q13": ["diabetes"]`

#### Q15

**Pergunte:** "(Mulheres em idade fértil) Existe chance de estar grávida ou está amamentando? A menstruação está atrasada?"  
**Serve para:** Gravidez  
**Quando se aplica:** Faixa de idade provisória, a validar pelo revisor clínico. Sexo ausente mantém a pergunta.  
**Registre:**

- `gravida_possivel`: `true` ou `false`
- `amamentando`: `true` ou `false`
- `menstruacao_atrasada`: `true` ou `false`

**Exemplo:** `"Q15": {"gravida_possivel": true, "amamentando": true, "menstruacao_atrasada": true}`

## Núcleo (todo paciente)

#### Q01

**Pergunte:** "O que você está sentindo e o que fez você procurar ajuda hoje?"  
**Serve para:** Queixa principal (relato livre)  
**Registre:** texto curto  
**Exemplo:** `"Q01": "texto curto"`

#### Q02

**Pergunte:** "Quando começou? Foi de repente ou aos poucos?"  
**Serve para:** Agudo ou crônico  
**Registre:**

- `inicio`: uma opção: `de_repente`, `aos_poucos`
- `duracao`: número e unidade (minutos, horas, dias, semanas, meses, anos)

**Exemplo:** `"Q02": {"inicio": "de_repente", "duracao": {"valor": 2, "unidade": "horas"}}`

#### Q03

**Pergunte:** "Desde que começou, está igual, melhorando ou piorando?"  
**Serve para:** Evolução  
**Registre:** uma opção: `igual`, `melhorando`, `piorando`  
**Exemplo:** `"Q03": "igual"`

#### Q04

**Pergunte:** "Como é o sintoma? (queimação, aperto, pontada, cólica)"  
**Serve para:** Caráter do sintoma  
**Registre:** uma opção: `queimacao`, `aperto`, `pontada`, `colica`, `outro`  
**Exemplo:** `"Q04": "queimacao"`

#### Q05

**Pergunte:** "De 0 a 10, quanto incomoda?"  
**Serve para:** Dor autorreferida (sinal fraco; nota baixa nunca reduz prioridade)  
**Registre:** número inteiro de 0 a 10  
**Exemplo:** `"Q05": 5`

#### Q06

**Pergunte:** "O sintoma vai ou se espalha para outra parte do corpo?"  
**Serve para:** Irradiação  
**Registre:**

- `resposta`: `true` ou `false`
- `para_onde`: texto curto — só se `resposta` for `true`

**Exemplo:** `"Q06": {"resposta": true, "para_onde": "texto curto"}`

#### Q07

**Pergunte:** "O que faz melhorar ou piorar?"  
**Serve para:** Fatores de piora e alívio  
**Registre:** texto curto  
**Exemplo:** `"Q07": "texto curto"`

#### Q14

**Pergunte:** "Já fez cirurgia, ficou internado ou recebeu transfusão de sangue?"  
**Serve para:** Histórico clínico (lista vazia significa nenhum)  
**Registre:** lista com: `cirurgia`, `internacao`, `transfusao` (`[]` = nenhuma)  
**Exemplo:** `"Q14": ["cirurgia"]`

## Módulos por queixa

### Módulo: Dor no peito

#### T01

**Pergunte:** "Está com suor frio, enjoo ou tontura junto com a dor?"  
**Serve para:** Sintomas associados à dor no peito  
**Registre:** `true` ou `false`  
**Exemplo:** `"T01": true`

#### T02

**Pergunte:** "A dor piora ao esforço ou ao respirar fundo?"  
**Serve para:** Relação com esforço e respiração  
**Registre:** `true` ou `false`  
**Exemplo:** `"T02": true`

#### T03

**Pergunte:** "Fez viagem longa ou cirurgia recente? Tem perna inchada ou dolorida?"  
**Serve para:** Risco tromboembólico  
**Registre:** `true` ou `false`  
**Exemplo:** `"T03": true`

### Módulo: Dor abdominal

#### A01

**Pergunte:** "Onde exatamente dói, e a dor mudou de lugar?"  
**Serve para:** Localização e migração da dor  
**Registre:**

- `local`: uma opção: `parte_superior`, `parte_inferior_direita`, `parte_inferior_esquerda`, `ao_redor_do_umbigo`, `toda_a_barriga`, `outro`
- `mudou_de_lugar`: `true` ou `false`

**Exemplo:** `"A01": {"local": "parte_superior", "mudou_de_lugar": true}`

#### A02

**Pergunte:** "Está vomitando? Tem sangue no vômito ou nas fezes?"  
**Serve para:** Vômito e sangramento digestivo  
**Registre:**

- `vomitando`: `true` ou `false`
- `episodios`: número — só se `vomitando` for `true`
- `sangue_vomito_ou_fezes`: `true` ou `false`

**Exemplo:** `"A02": {"vomitando": true, "episodios": 1, "sangue_vomito_ou_fezes": true}`

#### A03

**Pergunte:** "Está soltando gases e evacuando? Tem diarreia?"  
**Serve para:** Trânsito intestinal  
**Registre:**

- `gases_e_evacuando`: `true` ou `false`
- `diarreia`: `true` ou `false`

**Exemplo:** `"A03": {"gases_e_evacuando": true, "diarreia": true}`

#### A04

**Pergunte:** "A barriga está dura ou inchada?"  
**Serve para:** Abdome rígido ou distendido  
**Registre:** `true` ou `false`  
**Exemplo:** `"A04": true`

#### A05

**Pergunte:** "Está urinando normalmente?"  
**Serve para:** Alteração urinária (sim = urina normal)  
**Registre:** `true` ou `false`  
**Exemplo:** `"A05": true`

### Módulo: Febre e respiratório

#### R01

**Pergunte:** "Você sentiu febre ou calafrios?"  
**Serve para:** Febre referida (maior temperatura medida, se houver)  
**Registre:**

- `febre`: `true` ou `false`
- `maior_temperatura`: número — só se `febre` for `true`
- `calafrios`: `true` ou `false`

**Exemplo:** `"R01": {"febre": true, "maior_temperatura": 30, "calafrios": true}`

#### R02

**Pergunte:** "Consegue falar frases inteiras sem parar para respirar?"  
**Serve para:** Fala entrecortada (sim = fala frases inteiras)  
**Registre:** `true` ou `false`  
**Exemplo:** `"R02": true`

#### R03

**Pergunte:** "Tem chiado no peito ou tosse com sangue?"  
**Serve para:** Chiado e tosse com sangue  
**Registre:**

- `chiado`: `true` ou `false`
- `tosse_com_sangue`: `true` ou `false`

**Exemplo:** `"R03": {"chiado": true, "tosse_com_sangue": true}`

#### R04

**Pergunte:** "Esteve em contato com alguém doente ou viajou recentemente?"  
**Serve para:** Exposição  
**Registre:** `true` ou `false`  
**Exemplo:** `"R04": true`

#### R05

**Pergunte:** "Está conseguindo beber líquidos?"  
**Serve para:** Hidratação (sim = consegue beber)  
**Registre:** `true` ou `false`  
**Exemplo:** `"R05": true`

## Complementares (para o médico)

#### C01

**Pergunte:** "Há na família (pais, irmãos) histórico de infarto precoce, derrame, diabetes ou câncer?"  
**Serve para:** Histórico familiar (para o médico)  
**Registre:** texto curto  
**Exemplo:** `"C01": "texto curto"`

#### C02

**Pergunte:** "Você fuma, bebe ou usa alguma outra substância? Com que frequência?"  
**Serve para:** Hábitos (para o médico)  
**Registre:** texto curto  
**Exemplo:** `"C02": "texto curto"`

#### C03

**Pergunte:** "Como é o seu sono e como está o seu nível de estresse?"  
**Serve para:** Sono e estresse (para o médico)  
**Registre:** texto curto  
**Exemplo:** `"C03": "texto curto"`

#### C04

**Pergunte:** "Houve mudança recente no peso, no apetite ou no funcionamento do intestino e da urina?"  
**Serve para:** Mudanças recentes (para o médico)  
**Registre:** texto curto  
**Exemplo:** `"C04": "texto curto"`

## Depois da entrevista

1. Monte a ficha no formato descrito no [README](../README.md#formato-da-ficha).
2. Rode `python -m triagem ficha.json`.
3. Confira `perguntas_pendentes` e `alertas`. A `proxima_pergunta` é a mais importante que falta.
4. Relato e resposta direta podem divergir. A resposta direta prevalece, mas o sistema avisa
   (`alertas`) e a pontuação não diminui.
