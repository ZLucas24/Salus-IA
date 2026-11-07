# Salus IA

Protótipo de **copiloto de triagem** para UPAs e prontos-socorros do SUS e da rede privada, feito para o hackathon
AKCIT Camp 2026.

O atendente faz a entrevista com o paciente e registra as respostas numa **ficha**. O Salus IA lê
essa ficha e devolve um JSON padronizado com:

- os **sinais** do paciente (o que está presente, o que foi negado, o que ninguém perguntou);
- as **perguntas que ainda faltam**, em ordem de prioridade, e qual fazer agora;
- os **alertas** para a enfermagem (sinal grave, divergência, aferição faltando etc.);
- uma **sugestão** de cor e de pontuação, com as regras que a geraram.

> **Aviso: todos os dados são simulados.** Não há pacientes reais no repositório e nenhum dado
> real deve ser colocado nele. Isto **não é um dispositivo médico** e não pode ser usado em
> atendimento real. **Os limites, as regras de cor e os pesos ainda não foram revisados por
> enfermeiro ou médico.** A decisão final é sempre do profissional de saúde.

## Sumário

1. [Princípios](#princípios)
2. [Início rápido](#início-rápido)
3. [Fluxo do agente](#fluxo-do-agente)
4. [O questionário](#o-questionário)
5. [Formato da ficha](#formato-da-ficha)
6. [Formato da saída](#formato-da-saída)
7. [Cor e pontuação (provisórias)](#cor-e-pontuação-provisórias)
8. [Alertas](#alertas)
9. [Extratores: mock e Ollama](#extratores-mock-e-ollama)
10. [Comandos](#comandos)
11. [Interface web](#interface-web)
12. [Avaliação do extrator](#avaliação-do-extrator)
13. [Testes](#testes)
14. [Estrutura do repositório](#estrutura-do-repositório)
15. [Como alterar perguntas, regras e pesos](#como-alterar-perguntas-regras-e-pesos)
16. [Limitações e pendências](#limitações-e-pendências)

## Princípios

Estas regras valem para todo o código (a lista completa está no [CLAUDE.md](CLAUDE.md)):

1. **A IA só lê o relato.** O modelo de linguagem transforma o texto livre do paciente em sinais.
   Ele **nunca** decide a gravidade.
2. **A gravidade vem de regras explícitas**, escritas em
   [triagem/dados/regras.json](triagem/dados/regras.json) e aplicadas por código.
3. **Só "negado" vale como "não".** "Não sabe", "recusou", "não mencionado" e "incerto" nunca
   viram ausência do sinal. Aferição não feita nunca vale como normal.
4. **Nada reduz a pontuação.** Não existe peso negativo. Informar mais coisas só pode manter ou
   subir a cor e a pontuação.
5. **Resposta direta vale mais que o relato.** Se os dois divergem, o sistema mostra a resposta
   direta, mas conta o sinal citado no relato e emite um alerta.
6. **Funciona sem internet.** O extrator padrão (`mock`) não usa rede; o modelo real roda local,
   via Ollama.

## Início rápido

Requer **Python 3.11 ou superior** e o **Git**. Escolha o terminal que você usa no Windows; só a
linha que ativa o ambiente virtual muda entre eles.

**PowerShell**

```powershell
git clone https://github.com/ZLucas24/Salus-IA.git
cd Salus-IA
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Se o PowerShell recusar o `Activate.ps1` dizendo que a execução de scripts está desabilitada, rode
antes `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`. Isso vale só para aquela janela.

**Prompt de Comando (cmd)**

```bat
git clone https://github.com/ZLucas24/Salus-IA.git
cd Salus-IA
python -m venv .venv
.venv\Scripts\activate.bat
pip install -r requirements.txt
```

**Git Bash**

```bash
git clone https://github.com/ZLucas24/Salus-IA.git
cd Salus-IA
python -m venv .venv
source .venv/Scripts/activate
pip install -r requirements.txt
```

Com o ambiente ativado, aparece `(.venv)` no começo da linha. Os comandos a seguir são iguais nos
três terminais.

Rodar uma ficha de exemplo (o JSON sai no terminal):

```bash
python -m triagem exemplos/ficha_exemplo.json
```

Abrir a interface web no navegador:

```bash
python -m triagem.interface --abrir
```

Rodar os testes:

```bash
python -m pytest
```

### Usando um modelo de verdade (opcional)

1. Instale o [Ollama](https://ollama.com/download).
2. Baixe o modelo padrão: `ollama pull llama3.1:8b` (cerca de 5 GB).
3. Rode com `--extrator ollama`:

```bash
python -m triagem exemplos/ficha_exemplo.json --extrator ollama
```

Para trocar o modelo ou o endereço do Ollama, copie `.env.example` para `.env` e preencha:

| Variável | Para que serve | Padrão |
|---|---|---|
| `TRIAGEM_MODELO` | modelo usado pelo extrator Ollama | `llama3.1:8b` |
| `OLLAMA_HOST` | endereço do Ollama | `http://127.0.0.1:11434` |
| `SUPABASE_URL`, `SUPABASE_KEY`, `HF_TOKEN` | reservados; **hoje não são usados** | vazio |

O `.env` nunca vai para o repositório.

## Fluxo do agente

O fluxo inteiro está em `processar_ficha`, em [triagem/entrevista.py](triagem/entrevista.py).
Só a etapa 3 usa IA. Todas as outras são código com regras fixas.

```
INPUTS                          LÓGICA                                    OUTPUTS
ficha.json ──┐
             ├─▶ 1. validar ──▶ 2. respostas fechadas ──┐
questionário ┘        │ erro                            │
regras.json           ▼                                 ▼
             ficha inválida             3. relato (IA) ─▶ 4. aferições ─▶ 5. mesclar
             (stderr, código 1)                                               │
                                                                              ▼
                       6. ajustes ─▶ 7. módulos ─▶ 8. alertas e pendências ─▶ 9. pontuar
                                                                              │
                                                                              ▼
                                                              JSON de saída (stdout, código 0)
```

### Inputs

| Entrada | De onde vem | O que traz |
|---|---|---|
| **Ficha** | arquivo JSON passado ao comando ou formulário da interface web | `dados_atendente` (idade e aferições) e `respostas` (por id de pergunta). Veja [Formato da ficha](#formato-da-ficha) |
| **Questionário** | [triagem/dados/questionario.json](triagem/dados/questionario.json) | as perguntas, o formato de cada resposta, a prioridade, o módulo e o sinal que cada resposta gera |
| **Regras** | [triagem/dados/regras.json](triagem/dados/regras.json) | limites das aferições, regras de cor, pesos e teto da pontuação |
| **Extrator** | opção `--extrator` (`mock`, que é o padrão, ou `ollama`) | quem lê o relato livre da Q01 |
| **Configuração** | `.env` (opcional) | `TRIAGEM_MODELO` e `OLLAMA_HOST`, só para o extrator Ollama |

### Lógica, etapa por etapa

| # | Etapa | Função | O que faz | Pode gerar |
|---|---|---|---|---|
| 1 | Validar | `validar_ficha` | confere a estrutura da ficha, a idade (obrigatória), os valores impossíveis de aferição, campos desconhecidos e ids de pergunta que não existem | erro |
| 2 | Respostas fechadas | `interpretar_respostas` | converte cada resposta (sim/não, nota, opção, lista) nos sinais que ela gera. Separa o relato (Q01), a duração (Q02) e as alergias (Q10). Marca o que veio incompleto, o que veio como "não sabe" ou "recusou" e as perguntas que não se aplicam ao paciente | erro (tipo errado, dado contraditório) |
| — | **Se houver qualquer erro nas etapas 1 e 2** | | o fluxo para e lista todos os problemas de uma vez. Não sai JSON | `FichaInvalida`, código 1 |
| 3 | Relato (IA) | `extrair_relato` | o extrator lê o texto livre e devolve uma `Extracao`: queixa principal, categorias de queixa, duração, sinais (cada um com o trecho do relato que o comprova) e alergias. O código descarta o que o modelo não consegue comprovar | `extracao_falhou`, `extracao_avisos` |
| 4 | Aferições | `sinais_medidos` | compara as aferições com os limites do `regras.json` e transforma em sinais medidos (ex.: `febre_atual`, `hipoxemia`, `taquicardia`). Abaixo de 18 anos, só temperatura e Glasgow são avaliadas | `limites_pediatricos` |
| 5 | Mesclar | `mesclar_sinais` | junta os sinais em uma lista única dos 39 sinais. A resposta direta e a aferição prevalecem sobre o relato. Quando eles discordam, o sinal mostra a resposta direta e guarda o que o relato disse. Sem resposta definitiva, vale o relato. Sem nada, o sinal fica `nao_mencionado` | `divergencia` |
| 6 | Ajustes | `processar_ficha` | marca como `nao_se_aplica` os sinais de perguntas que não valem para o paciente (ex.: gravidez). Compara a duração da Q02 com a do relato e a alergia da Q10 com a do relato | `duracao_divergente`, `alergia_divergente` |
| 7 | Módulos | `modulos_ativos` | ativa os módulos de perguntas (dor torácica, dor abdominal, respiratório e febre) a partir das respostas, das categorias de queixa do relato e dos sinais presentes | `sem_modulo` |
| 8 | Alertas e pendências | `_alertas_de_dados`, `calcular_pendencias`, `afericoes_faltando` | gera os alertas de dados, lista as perguntas que faltam em ordem de prioridade (segurança, núcleo, módulo; as complementares não entram) e as aferições que deviam ter sido feitas. Perguntas incompletas, divergentes ou com relato que falhou voltam para a lista | `dado_incompleto`, `dado_desconhecido`, `febre_mascarada`, `febre_nao_referida`, `afericao_faltando` |
| 9 | Pontuar | `pontuar` e `_alertas_graves` | aplica as regras de cor (cada uma define uma cor mínima; vale a mais alta), soma os pesos dos sinais presentes e, se a soma passar do teto, sobe a cor. Regra de cor laranja ou vermelha vira alerta imediato | `sinal_de_alerta` |

Três garantias valem em todas as etapas:

- **A falha do extrator não derruba a ficha.** Se o modelo estiver fora do ar ou responder algo
  inválido, a saída é montada só com as respostas diretas, com o alerta `extracao_falhou`, e a Q01
  volta para as pendências.
- **Dado desconhecido nunca vira "não".** Só `negado` conta como ausência do sinal.
- **Nada reduz a pontuação.** Mais informação só mantém ou sobe a cor e a pontuação.

### Outputs

| Saída | Onde | Quando |
|---|---|---|
| **JSON de triagem** | stdout, ou o arquivo de `--saida` | ficha válida (código 0). Traz sinais, alergias, duração, módulos ativos, perguntas pendentes e próxima pergunta, aferições faltando, alertas e a classificação (cor, pontuação e regras aplicadas). Veja [Formato da saída](#formato-da-saída) |
| **Lista de erros** | stderr | ficha inválida (código 1) |
| **Mensagens de andamento** | stderr | sempre. O stdout fica só com o JSON |

Códigos de saída do comando: `0` sucesso, `1` ficha inválida, `2` erro de uso (arquivo não
encontrado, ilegível, grande demais ou com JSON inválido), `3` erro interno.

## O questionário

O banco de perguntas foi definido pela equipe em [agente_triagem.md](agente_triagem.md) e está em
[triagem/dados/questionario.json](triagem/dados/questionario.json), que é a **fonte única**: o
código, a interface e o roteiro leem dali. O roteiro para o atendente, com cada pergunta, o formato
da resposta e um exemplo, está em [docs/roteiro_entrevista.md](docs/roteiro_entrevista.md).

São 32 perguntas e 7 aferições, em quatro níveis de prioridade:

| Nível | Perguntas | Regra |
|---|---|---|
| **S** — segurança | Q08 a Q13, Q15 | nunca pular por suposição; vêm primeiro nas pendências |
| **N** — núcleo | Q01 a Q07, Q14 | sempre feitas |
| **M** — módulo | T01–T03, A01–A05, R01–R05 | só quando o módulo está ativo |
| **C** — complementar | C01 a C04 | registradas, mas não entram na pontuação nem nas pendências |

**Módulos.** Cada módulo é ativado se o relato cita a queixa correspondente, se um sinal do módulo
está presente ou se alguma pergunta do módulo já foi respondida:

| Módulo | Perguntas | Exemplo de gatilho |
|---|---|---|
| Dor no peito (`dor_toracica`) | T01–T03 | "dor no peito", dor em aperto |
| Dor abdominal (`dor_abdominal`) | A01–A05 | "dor na barriga", vômito |
| Febre e respiratório (`respiratorio_febre`) | R01–R05 | "febre", falta de ar |

Se nenhum módulo se encaixar, sai o alerta `sem_modulo` e a entrevista segue só com o núcleo.

**Q15 (gravidez)** só se aplica a pacientes de 10 a 55 anos com sexo biológico feminino, intersexo
ou não informado. É uma regra provisória.

**Aferições** (feitas pela enfermagem, nunca perguntadas ao paciente):

| Id | Campo na ficha | Unidade | Quando |
|---|---|---|---|
| E01 | `temperatura` | °C | sempre |
| E02 | `saturacao` | % | sempre |
| E03 | `pressao_sistolica` e `pressao_diastolica` | mmHg | sempre (as duas juntas) |
| E04 | `frequencia_cardiaca` | bpm | sempre |
| E05 | `frequencia_respiratoria` | irpm | se houver falta de ar (Q09) |
| E06 | `glicemia` | mg/dL | se houver diabetes (Q13) ou alteração de consciência (Q08) |
| E07 | `glasgow` | 3 a 15 | se houver alteração de consciência (Q08) |

## Formato da ficha

A ficha é um JSON com duas partes, `dados_atendente` e `respostas`:

```json
{
  "dados_atendente": {
    "idade": 58,
    "sexo_biologico": "masculino",
    "temperatura": 36.8,
    "saturacao": 93,
    "pressao_sistolica": 150,
    "pressao_diastolica": 95,
    "frequencia_cardiaca": 102,
    "frequencia_respiratoria": 22
  },
  "respostas": {
    "Q01": "Dor forte no peito há 2 horas e falta de ar",
    "Q02": {"inicio": "de_repente", "duracao": {"valor": 2, "unidade": "horas"}},
    "Q03": "piorando",
    "Q04": "aperto",
    "Q05": 8,
    "Q06": {"resposta": true, "para_onde": "braço esquerdo"},
    "Q08": false,
    "Q09": true,
    "Q10": {"resposta": false},
    "Q11": {"resposta": true, "anticoagulante": false, "insulina": false, "texto": "losartana"},
    "Q13": ["hipertensao"],
    "T01": true
  }
}
```

### `dados_atendente`

- `idade` (anos, inteiro) é o **único campo obrigatório**.
- `sexo_biologico`: `feminino`, `masculino`, `intersexo` ou `ausente` (padrão). Só serve para
  decidir se a Q15 se aplica.
- Aferições: veja a tabela acima. Campo vazio ou ausente significa **não aferido**.
- Valores impossíveis são recusados como erro de digitação (ex.: temperatura fora de 30–45 °C,
  saturação fora de 0–100 %, Glasgow fora de 3–15). Isso não é limite clínico.
- Campo desconhecido é erro (evita erro de digitação silencioso).

### `respostas`

- A chave é o id da pergunta (`Q01`, `T02`, `R05`...). O formato de cada uma está no
  [roteiro](docs/roteiro_entrevista.md). Os formatos possíveis são:

| Formato | Exemplo |
|---|---|
| sim/não | `"Q09": true` |
| texto livre (Q01: até 200 caracteres) | `"Q01": "dor na barriga desde ontem"` |
| nota de 0 a 10 | `"Q05": 7` |
| uma opção | `"Q03": "piorando"` |
| lista de opções | `"Q13": ["diabetes", "hipertensao"]` (`[]` = nenhuma) |
| objeto com partes | `"Q06": {"resposta": true, "para_onde": "costas"}` |
| número com unidade | `{"valor": 2, "unidade": "horas"}` |

- **Não sabe, recusou, não se aplica:** escreva `"nao_sabe"`, `"recusou"` ou `"nao_se_aplica"` no
  lugar da resposta ou de uma parte dela. Nunca vale como "não"; numa pergunta de segurança gera o
  alerta `dado_desconhecido`.
- **Pergunta ausente** fica pendente. **Pergunta respondida pela metade** (falta parte obrigatória)
  também, e gera o alerta `dado_incompleto`.
- **Dado contraditório é erro**, não é descartado. Exemplo: `"Q11": {"resposta": false, "insulina": true}`.

### Fichas de exemplo

Em [exemplos/](exemplos/) há 16 fichas, cada uma mostrando um caso:

| Ficha | O que mostra |
|---|---|
| `ficha_exemplo.json` | dor no peito completa (é a do exemplo acima) |
| `ficha_01_caso_simples.json` | caso mínimo |
| `ficha_02_perguntas_sem_resposta.json` | pendências em ordem de prioridade |
| `ficha_03_febre_com_valor.json` | febre referida com temperatura aferida |
| `ficha_04_alergia_na_q10.json` | alergia registrada na Q10 |
| `ficha_05_alergia_so_no_relato.json` | alergia que só aparece no relato |
| `ficha_06_divergencia_relato_x_direta.json` | relato e resposta direta discordam |
| `ficha_07_relato_com_200_caracteres.json` | relato no limite de 200 caracteres |
| `ficha_11_nao_sabe_e_recusou.json` | marcadores `nao_sabe` e `recusou` |
| `ficha_12_gravidez_aplica_ou_nao.json` | quando a Q15 se aplica |
| `ficha_13_febre_mascarada.json` | febre referida + antitérmico + temperatura normal |
| `ficha_15_crianca_afericoes.json` | criança (limites pediátricos ainda não existem) |
| `ficha_08_relato_201_falha.json` | **falha de propósito:** relato com 201 caracteres |
| `ficha_09_sem_idade_falha.json` | **falha de propósito:** sem idade |
| `ficha_10_tipo_resposta_errado_falha.json` | **falha de propósito:** tipo errado |
| `ficha_14_dado_contraditorio_falha.json` | **falha de propósito:** dado contraditório |

## Formato da saída

O comando imprime **um único JSON** (versão do schema `0.2.0`, definido em
[triagem/schema.py](triagem/schema.py)). Os campos principais:

| Campo | O que traz |
|---|---|
| `queixa_principal`, `queixas` | a queixa em texto e as categorias reconhecidas |
| `modulos_ativos` | módulos de perguntas ativados |
| `duracao` | há quanto tempo começou (`valor` + `unidade`) |
| `sinais` | todos os 39 sinais, cada um com `status`, `origem` e, quando houver, `valor`, `itens` e `trecho` do relato |
| `alergias` | `status`, `tipos` (medicamento, alimento, contraste) e `itens` |
| `afericoes_faltando` | aferições esperadas que não foram feitas |
| `perguntas_pendentes`, `proxima_pergunta` | o que falta perguntar, na ordem, e a próxima |
| `alertas` | lista de `{codigo, mensagem, referencias}` (veja [Alertas](#alertas)) |
| `classificacao` | `cor`, `pontuacao`, `provisoria: true`, `regras_validadas: false` e `regras_aplicadas` |
| `extrator` | quem leu o relato (`mock` ou `ollama:<modelo>`) |

**Status de um sinal:** `presente`, `negado`, `nao_mencionado`, `nao_sabe`, `recusou`,
`nao_se_aplica` ou `incerto`.

**Origem de um sinal:** `resposta_direta` (pergunta fechada), `extraido_do_relato` (texto livre),
`medido_pelo_atendente` (aferição) ou `nenhuma`.

Trecho da saída da `ficha_exemplo.json`:

```json
{
  "queixa_principal": "dor forte no peito há 2 horas",
  "modulos_ativos": ["dor_toracica", "respiratorio_febre"],
  "sinais": [
    {"nome": "dor", "status": "presente", "valor": 8.0, "origem": "resposta_direta"},
    {"nome": "irradiacao", "status": "presente", "itens": ["braço esquerdo"], "origem": "resposta_direta"},
    {"nome": "taquicardia", "status": "presente", "valor": 102.0, "origem": "medido_pelo_atendente"}
  ],
  "perguntas_pendentes": ["R01", "R02", "R03", "R04", "R05"],
  "proxima_pergunta": "R01",
  "alertas": [
    {"codigo": "sinal_de_alerta", "mensagem": "Dor em aperto com irradiação (cor mínima laranja)",
     "referencias": ["RC-09"]}
  ],
  "classificacao": {
    "cor": "laranja",
    "pontuacao": 54,
    "provisoria": true,
    "regras_validadas": false,
    "regras_aplicadas": [
      {"id": "RC-08", "descricao": "Dor em aperto com suor frio, enjoo ou tontura", "efeito": "cor mínima laranja"},
      {"id": "RC-09", "descricao": "Dor em aperto com irradiação", "efeito": "cor mínima laranja"}
    ]
  },
  "extrator": "mock",
  "versao_schema": "0.2.0"
}
```

O JSON real traz todos os sinais e todas as regras aplicadas (inclusive os pesos somados).

## Cor e pontuação (provisórias)

Tudo o que segue está em [triagem/dados/regras.json](triagem/dados/regras.json), marcado
`"validado": false`. São **propostas da equipe para exercitar o motor**, não critérios clínicos.

### Cor

A cor começa em **verde**. Cada regra acionada impõe uma **cor mínima**; vale a mais alta.
Ordem: azul < verde < amarelo < laranja < vermelho.

| Regra | Quando | Cor mínima |
|---|---|---|
| RC-01 | alteração de consciência | laranja |
| RC-02 | Glasgow abaixo de 15 | laranja |
| RC-03 | Glasgow 8 ou menos | vermelho |
| RC-04 | alteração de consciência **e** saturação baixa | vermelho |
| RC-05 | saturação abaixo de 92 % | laranja |
| RC-06 | pressão sistólica abaixo de 90 | laranja |
| RC-07 | falta de ar **e** fala entrecortada | laranja |
| RC-08 | dor em aperto **e** suor frio, enjoo ou tontura | laranja |
| RC-09 | dor em aperto **e** irradiação | laranja |
| RC-10 | sangue no vômito ou nas fezes | laranja |
| RC-11 | tosse com sangue | laranja |
| RC-12 | dor abdominal **e** abdome rígido ou distendido | laranja |
| RC-13 | gravidez possível **e** dor abdominal | laranja |
| RC-14 | piora progressiva | amarelo |
| RC-15 | falta de ar | amarelo |
| RC-16 | dor com nota 8 ou mais | amarelo |
| RC-17 | febre referida **e** antitérmico recente | amarelo |

### Pontuação (0 a 100, dentro da cor)

- É a **soma dos pesos** dos sinais presentes. Exemplos: alteração de consciência 15, Glasgow
  reduzido 15, saturação baixa 12,5, hipotensão 12,5, sangue no vômito/fezes 12,5, falta de ar 10.
  A tabela completa está em `pontuacao.pesos`.
- A **dor** entra proporcional à nota (nota/10 do peso), mas nunca menos que metade do peso: dar
  uma nota baixa não pode reduzir a pontuação.
- Ao chegar a **100**, o paciente **sobe uma cor** e o excedente continua contando (regra
  `PROMOCAO` em `regras_aplicadas`). Vermelho é o teto.

### Limites das aferições

| Sinal | Limite (adulto) |
|---|---|
| febre | temperatura ≥ 37,8 °C (criança: ≥ 37,5 °C) |
| saturação baixa | abaixo de 92 % |
| taquicardia | FC acima de 100 bpm |
| taquipneia | FR acima de 20 irpm |
| hipotensão | PAS abaixo de 90 mmHg |
| glicemia alterada | abaixo de 70 ou acima de 250 mg/dL |
| Glasgow reduzido | abaixo de 15 |

Em menores de 18 anos, só a temperatura e o Glasgow são avaliados; os demais limites ainda não têm tabela
pediátrica e sai o alerta `limites_pediatricos`.

## Alertas

| Código | Quando aparece |
|---|---|
| `sinal_de_alerta` | uma regra de cor laranja ou vermelha foi acionada: avisar a enfermagem já |
| `divergencia` | relato e resposta direta discordam sobre um sinal |
| `alergia_divergente` | o relato cita alergia, mas a Q10 diz que não há |
| `duracao_divergente` | a duração da Q02 e a do relato não batem |
| `febre_mascarada` | febre referida, antitérmico recente e temperatura normal |
| `febre_nao_referida` | paciente nega febre, mas a temperatura aferida está alta |
| `dado_desconhecido` | pergunta de segurança respondida com "não sabe" ou "recusou" |
| `dado_incompleto` | pergunta respondida pela metade |
| `afericao_faltando` | aferição esperada não foi registrada |
| `limites_pediatricos` | paciente menor de 18 anos com aferições que ainda não sabemos avaliar |
| `sem_modulo` | nenhum módulo de perguntas se encaixou |
| `extracao_falhou` | o extrator não conseguiu ler o relato; revisar à mão |
| `extracao_avisos` | o extrator descartou itens inválidos |

## Extratores: mock e Ollama

O extrator lê **só o relato livre (Q01)**. Ele fica atrás da interface `Extrator`
([triagem/extracao.py](triagem/extracao.py)), então as implementações são intercambiáveis:

| Extrator | Como funciona | Rede |
|---|---|---|
| `mock` (padrão) | palavras-chave e negação local ("não tenho febre"), em [triagem/extrator_mock.py](triagem/extrator_mock.py) | não |
| `ollama` | modelo local (`llama3.1:8b`) com prompt e exemplos, em [triagem/extrator_ollama.py](triagem/extrator_ollama.py) | só se `OLLAMA_HOST` não for local (há aviso) |

O código **não confia no modelo**. Toda resposta passa por estes filtros:

- sinal sem um **trecho que exista de fato no relato** é descartado;
- "negado" só vale se o relato nega; negação inventada é descartada;
- alergia só pode sair como "presente" (o relato não serve para negar alergia);
- valor fora da faixa e item inválido são descartados com aviso, sem derrubar o resto;
- timeout de 120 s; nova tentativa só em erro de formato.

## Comandos

| Comando | O que faz |
|---|---|
| `python -m triagem ficha.json` | processa a ficha e imprime o JSON de saída |
| `python -m triagem.interface --abrir` | abre a interface web local |
| `python -m triagem.relato "dor no peito há 2 horas"` | só extrai um relato: queixa, sinais e duração |
| `python -m triagem.avaliar --alvo mock --alvo ollama:llama3.1:8b` | compara extratores com o gabarito simulado |
| `python -m triagem.roteiro` | gera de novo o [roteiro de entrevista](docs/roteiro_entrevista.md) |
| `python -m triagem.ajustar` | experimento de ajuste de pesos (só mostra; não altera nada) |

Opções do `python -m triagem`:

| Opção | Efeito |
|---|---|
| `--extrator mock\|ollama` | escolhe o extrator (padrão `mock`) |
| `--saida arquivo.json` | grava o JSON em arquivo (UTF-8) em vez de imprimir |
| `-q` | só avisos e erros no stderr |
| `-` no lugar do arquivo | lê a ficha do stdin (vale também para o relato do `triagem.relato`) |

- **stdout:** só o JSON, indentado, em UTF-8. **stderr:** logs e erros. Dá para encadear com
  outros programas sem filtrar nada.
- **Códigos de saída:**

| Código | Significado |
|---|---|
| `0` | sucesso |
| `1` | ficha inválida (o stderr diz qual pergunta e por quê) |
| `2` | uso incorreto, arquivo ilegível ou JSON quebrado |
| `3` | erro interno |
| `4` | só no `triagem.relato`: extrator indisponível ou resposta inválida |

## Interface web

```bash
python -m triagem.interface --abrir     # abre http://127.0.0.1:8765/
```

Opções: `--porta 9000` para outra porta; sem `--abrir`, só sobe o servidor. Encerre com `Ctrl+C`.

- **Esquerda:** cadastro, aferições e o formulário de entrevista, montado a partir do próprio
  questionário (segurança, núcleo, módulos e complementares), com botões de "não sabe",
  "recusou" e "não se aplica".
- **Direita:** cor e pontuação sugeridas (marcadas como provisórias), alertas, próxima pergunta e
  pendências (clicáveis), sinais com origem e trecho do relato, alergias, regras aplicadas e o
  JSON completo.
- Com o `mock`, o resultado se atualiza enquanto você digita. Com o Ollama, clique em **Analisar**.
- Há um seletor com as fichas de exemplo, inclusive as que falham de propósito.

**Segurança:** escuta só em `127.0.0.1` (não aparece na rede), confere os cabeçalhos `Host` e
`Origin`, limita o corpo a 1 MB, não carrega nada de fora (sem CDN nem fontes externas) e o texto
digitado nunca vira HTML. Usa só a biblioteca padrão do Python, em
[triagem/interface/](triagem/interface/).

## Avaliação do extrator

`python -m triagem.avaliar` compara o que o extrator achou com um gabarito escrito à mão
([avaliacao/relatos_simulados.json](avaliacao/relatos_simulados.json)): 16 relatos de
**desenvolvimento** e 8 de **teste**. Mede:

- **precisão:** dos sinais que o extrator apontou, quantos estavam certos;
- **revocação:** dos sinais que existiam, quantos ele achou;
- **erros que subestimam o risco** (contados à parte): sinal presente omitido ou dado como negado.

A partição de **teste** só pode ser usada uma vez por versão do prompt (`--teste`; o uso fica
registrado em `avaliacao/teste_usado.json`) e nunca entra em exemplos do prompt nem em ajuste.

Último resultado do `llama3.1:8b`: precisão 75 % e revocação 86 % no desenvolvimento; 93 % e 93 %
no teste. O `mock` empatou no teste. O gabarito é pequeno e não tem revisão clínica, então esses
números só servem para comparar versões entre si.

## Testes

```bash
python -m pytest
```

Os testes não usam rede (o modelo é sempre trocado por um extrator falso) e cobrem: vocabulário de
sinais, questionário, fluxo da entrevista, pontuação (inclusive um teste com sequências aleatórias
que confirma que nada reduz a pontuação), extratores, CLI, avaliador, roteiro gerado, interface e o
próprio README.

## Estrutura do repositório

```
triagem/
  __main__.py, cli.py     comando principal (python -m triagem)
  entrevista.py           o fluxo em etapas
  questionario.py         carrega e interpreta as respostas
  afericoes.py            aferições -> sinais medidos
  pontuacao.py, regras.py motor de cor e pontuação
  extracao.py             interface Extrator e contrato
  extrator_mock.py        extrator por palavras-chave
  extrator_ollama.py      extrator com modelo local
  schema.py, sinais.py    formato da saída e vocabulário de sinais
  texto.py                validação e normalização de texto
  relato.py, avaliar.py, roteiro.py, ajustar.py   comandos auxiliares
  dados/questionario.json perguntas e aferições (fonte única)
  dados/regras.json       limites, regras de cor e pesos (não validados)
  interface/              servidor e página da interface web
exemplos/                 fichas simuladas
avaliacao/                gabarito do extrator
docs/roteiro_entrevista.md  roteiro do atendente (gerado)
tests/                    testes automatizados
agente_triagem.md         instruções do agente e banco de perguntas (equipe)
arquivos de arquitetura/  projeto, riscos, legislação, linha do tempo, pontos de discussão (equipe)
geração_banco_dados.py, salus_treinamento.db   banco de casos simulados para testar o modelo
```

## Como alterar perguntas, regras e pesos

- **Pergunta nova ou texto alterado:** edite
  [triagem/dados/questionario.json](triagem/dados/questionario.json), rode `python -m triagem.roteiro`
  para gerar o roteiro de novo e `python -m pytest`. A interface se atualiza sozinha.
- **Limite, regra de cor ou peso:** edite [triagem/dados/regras.json](triagem/dados/regras.json).
  Nenhum número clínico fica no código Python. Peso negativo é recusado.
- **Sinal novo:** além do questionário, inclua o nome em `NomeSinal`
  ([triagem/sinais.py](triagem/sinais.py)) e um peso em `regras.json`.
- **Nunca** use relatos da partição de teste para escrever exemplos de prompt ou ajustar pesos.

## Limitações e pendências

- **Sem revisão clínica:** todos os limites, regras de cor e pesos precisam ser conferidos linha a
  linha por enfermeiro ou médico. Até lá, toda saída vem com `provisoria: true`.
- **Crianças:** ainda não há limites pediátricos para saturação, frequências, pressão e glicemia.
- **Azul** existe na escala, mas nenhuma regra leva a ele (a cor base é verde).
- **Duração** é registrada para a queixa principal, não para cada sintoma.
- **Faltam** identificação e horário do atendimento e do atendente.
- **Remédios:** nomes comerciais e genéricos ainda não são unificados (ex.: dipirona e Novalgina).
- **Banco de casos** (`salus_treinamento.db`): as pontuações-alvo são sorteadas, então não servem
  para ajustar pesos; o `triagem.ajustar` mostra isso (correlação perto de zero). Três casos têm
  pressão sistólica menor que a diastólica.
- **Supabase e Hugging Face** estão nas dependências, mas ainda não são usados.
