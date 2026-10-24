# Salus IA

Protótipo de um copiloto de triagem para UPAs e prontos-socorros do SUS, feito para o hackathon
AKCIT Camp 2026. O atendente conduz a entrevista; o sistema transforma a ficha em um JSON
padronizado com sinais, alertas, perguntas pendentes e uma **sugestão** de cor e pontuação.

A IA só entende linguagem e extrai dados do relato; **nunca decide gravidade**. A cor e a
pontuação vêm de regras explícitas em código, e a decisão final é sempre do profissional de saúde.

> **Aviso: todos os dados são simulados.** Não há pacientes reais no repositório e nenhum dado
> real deve ser colocado nele. Esta ferramenta não é um dispositivo médico e não deve ser usada
> em atendimento real. **As regras de pontuação ainda não foram revisadas por profissional de
> saúde** (veja [Pontuação](#pontuação-provisória)).

## Sobre o projeto



Protótipo de um agente de triagem hospitalar com foco no SUS, feito para um

## Como funciona

```
ficha (JSON) -> validação -> respostas fechadas -> sinais (código determinístico)
                                     |
 relato (Q01) -> extrator (mock | Ollama) -> sinais citados no relato
                                     v
         mesclagem (resposta direta prevalece; divergência vira alerta)
                                     v
    aferições -> sinais medidos -> motor de regras -> cor + pontuação (provisórias)
                                     v
         perguntas pendentes em ordem de prioridade + alertas + JSON final
```

O banco de perguntas (núcleo Q01–Q15, aferições E01–E07, módulos de dor no peito, dor abdominal
e febre/respiratório, complementares) vem de [agente_triagem.md](agente_triagem.md) e está em
[triagem/dados/questionario.json](triagem/dados/questionario.json). O roteiro para o atendente
é gerado a partir dele: [docs/roteiro_entrevista.md](docs/roteiro_entrevista.md).

## Instalação

Requer Python 3.11 ou superior.

```bash
python -m venv .venv
source .venv/Scripts/activate   # Windows (Git Bash); no PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env            # opcional: o comando principal funciona sem rede nem chaves
```

Para usar um modelo de verdade, instale o [Ollama](https://ollama.com/download) e baixe o modelo
(`ollama pull llama3.1:8b`). Supabase e Hugging Face são opcionais e hoje não são usados.

## Formato da ficha

```json
{
  "dados_atendente": {"idade": 58, "sexo_biologico": "masculino", "temperatura": 36.8,
                      "saturacao": 93, "pressao_sistolica": 150, "pressao_diastolica": 95},
  "respostas": {"Q01": "Dor forte no peito há 2 horas", "Q05": 8, "Q09": true,
                "Q10": {"resposta": false}, "T01": true}
}
```

- `dados_atendente`: só a `idade` é obrigatória. `sexo_biologico` (`feminino`, `masculino`,
  `intersexo`, `ausente`) decide se a Q15 (gravidez) se aplica; ausente mantém a pergunta.
  Aferições (`temperatura`, `saturacao`, `pressao_sistolica`, `pressao_diastolica`,
  `frequencia_cardiaca`, `frequencia_respiratoria`, `glicemia`, `glasgow`) são opcionais, e aferição
  em branco significa **não aferida**, nunca normal.
- `respostas`: por id de pergunta. Cada pergunta tem o formato próprio (sim/não, nota de 0 a 10,
  opção, lista, número com unidade ou objeto com partes); o roteiro lista todos, com exemplos.
- **Não sabe / recusou:** use `"nao_sabe"`, `"recusou"` ou `"nao_se_aplica"` no lugar da resposta
  (ou de uma parte dela). Isso **nunca** vale como "não".
- Pergunta ausente fica pendente; pergunta respondida pela metade também.
- Dado contraditório (ex.: Q11 `resposta: false` com `insulina: true`) é erro, não é descartado.

Há fichas de exemplo em [exemplos/](exemplos/), incluindo quatro que falham de propósito
(relato com 201 caracteres, sem idade, tipo de resposta errado e dado contraditório).

## Comandos

| Comando | O que faz |
|---|---|
| `python -m triagem ficha.json` | entrevista completa: JSON de saída no stdout |
| `python -m triagem.interface --abrir` | **interface web** local: formulário de entrevista e painel de resultado |
| `python -m triagem.relato "dor no peito há 2 horas"` | só a extração de um relato (queixa, sinais, duração) |
| `python -m triagem.avaliar --alvo mock --alvo ollama:llama3.1:8b` | compara extratores com o gabarito simulado |
| `python -m triagem.roteiro` | regenera o roteiro de entrevista a partir do questionário |
| `python -m triagem.ajustar` | **experimento** de ajuste de pesos no banco simulado (nada é aplicado) |

Opções do comando principal: `--extrator mock|ollama` (padrão `mock`), `--saida arquivo.json`
(grava em UTF-8), `-q` (só avisos e erros no stderr), e `-` no lugar do arquivo para ler a ficha
do stdin (o mesmo vale para o relato, que assim não fica no histórico do terminal).

- **stdout:** somente o JSON, indentado, em UTF-8 legível. **stderr:** logs e erros.
- **Códigos de saída:** `0` sucesso; `1` ficha inválida (o stderr diz qual pergunta falhou);
  `2` uso incorreto, arquivo ilegível ou JSON quebrado; `3` erro interno. No `triagem.relato`, `4`
  significa extrator indisponível ou com resposta inválida.
- **Se o modelo falhar**, a ficha continua: sai só com as respostas diretas, com o alerta
  `extracao_falhou`, e a Q01 permanece pendente.

## Interface web

```bash
python -m triagem.interface --abrir     # http://127.0.0.1:8765/
```

Formulário de entrevista gerado a partir do próprio questionário (perguntas de segurança, núcleo,
módulos e complementares), com cadastro e aferições, e um painel de resultado que se atualiza
enquanto você digita: **cor e pontuação sugeridas** (marcadas como provisórias), **alertas**,
**próxima pergunta** e pendências (clicáveis), sinais presentes com origem e trecho do relato,
alergias, as regras que geraram o resultado e o JSON completo. Há um seletor de fichas de exemplo,
inclusive as inválidas de propósito, e um botão para escolher o extrator (mock ou modelo local).

Roda só na sua máquina: escuta apenas em `127.0.0.1`, confere `Host` e `Origin`, não carrega nada
de fora (sem CDN nem fontes externas), e o texto digitado nunca vira HTML. Não usa nenhuma
dependência além da biblioteca padrão.

## Exemplo de saída

`python -m triagem exemplos/ficha_exemplo.json` (abreviado: sinais não mencionados, `respostas` e
parte das regras omitidos; o JSON real traz tudo):

```json
{
  "relato_original": "Dor forte no peito há 2 horas e falta de ar",
  "queixa_principal": "dor forte no peito há 2 horas",
  "queixas": [
    "dor_toracica",
    "respiratorio_febre"
  ],
  "modulos_ativos": [
    "dor_toracica",
    "respiratorio_febre"
  ],
  "duracao": {
    "valor": 2.0,
    "unidade": "horas"
  },
  "sinais": [
    {
      "nome": "inicio_subito",
      "status": "presente",
      "origem": "resposta_direta"
    },
    {
      "nome": "piora_progressiva",
      "status": "presente",
      "origem": "resposta_direta"
    },
    {
      "nome": "dor_em_aperto",
      "status": "presente",
      "origem": "resposta_direta"
    },
    {
      "nome": "dor",
      "status": "presente",
      "valor": 8.0,
      "origem": "resposta_direta"
    },
    {
      "nome": "irradiacao",
      "status": "presente",
      "itens": [
        "braço esquerdo"
      ],
      "origem": "resposta_direta"
    },
    {
      "nome": "alteracao_consciencia",
      "status": "negado",
      "origem": "resposta_direta"
    },
    {
      "nome": "dispneia",
      "status": "presente",
      "origem": "resposta_direta"
    },
    {
      "nome": "uso_anticoagulante",
      "status": "negado",
      "origem": "resposta_direta"
    },
    {
      "nome": "uso_insulina",
      "status": "negado",
      "origem": "resposta_direta"
    },
    {
      "nome": "antitermico_recente",
      "status": "negado",
      "origem": "resposta_direta"
    },
    {
      "nome": "doenca_cronica",
      "status": "presente",
      "itens": [
        "hipertensao"
      ],
      "origem": "resposta_direta"
    },
    {
      "nome": "cirurgia_internacao_previa",
      "status": "negado",
      "origem": "resposta_direta"
    },
    {
      "nome": "suor_frio_enjoo_tontura",
      "status": "presente",
      "origem": "resposta_direta"
    },
    {
      "nome": "dor_piora_esforco_respirar",
      "status": "presente",
      "origem": "resposta_direta"
    },
    {
      "nome": "risco_tromboembolico",
      "status": "negado",
      "origem": "resposta_direta"
    },
    {
      "nome": "febre_atual",
      "status": "negado",
      "valor": 36.8,
      "origem": "medido_pelo_atendente"
    },
    {
      "nome": "hipoxemia",
      "status": "negado",
      "valor": 93.0,
      "origem": "medido_pelo_atendente"
    },
    {
      "nome": "taquicardia",
      "status": "presente",
      "valor": 102.0,
      "origem": "medido_pelo_atendente"
    },
    {
      "nome": "taquipneia",
      "status": "presente",
      "valor": 22.0,
      "origem": "medido_pelo_atendente"
    },
    {
      "nome": "hipotensao",
      "status": "negado",
      "valor": 150.0,
      "origem": "medido_pelo_atendente"
    }
  ],
  "alergias": {
    "status": "negado",
    "tipos": [],
    "itens": []
  },
  "dados_atendente": {
    "idade": 58,
    "sexo_biologico": "masculino",
    "temperatura": 36.8,
    "saturacao": 93.0,
    "pressao_sistolica": 150.0,
    "pressao_diastolica": 95.0,
    "frequencia_cardiaca": 102.0,
    "frequencia_respiratoria": 22.0
  },
  "afericoes_faltando": [],
  "perguntas_pendentes": [
    "R01",
    "R02",
    "R03",
    "R04",
    "R05"
  ],
  "proxima_pergunta": "R01",
  "alertas": [
    {
      "codigo": "sinal_de_alerta",
      "mensagem": "Dor em aperto com suor frio, enjoo ou tontura (cor mínima laranja)",
      "referencias": [
        "RC-08"
      ]
    },
    {
      "codigo": "sinal_de_alerta",
      "mensagem": "Dor em aperto com irradiação (cor mínima laranja)",
      "referencias": [
        "RC-09"
      ]
    }
  ],
  "classificacao": {
    "cor": "laranja",
    "pontuacao": 54,
    "provisoria": true,
    "regras_validadas": false,
    "regras_aplicadas": [
      {
        "id": "RC-08",
        "descricao": "Dor em aperto com suor frio, enjoo ou tontura",
        "efeito": "cor mínima laranja"
      },
      {
        "id": "RC-09",
        "descricao": "Dor em aperto com irradiação",
        "efeito": "cor mínima laranja"
      },
      {
        "id": "RC-14",
        "descricao": "Piora progressiva relatada",
        "efeito": "cor mínima amarelo"
      },
      {
        "id": "...",
        "descricao": "...",
        "efeito": "..."
      }
    ]
  },
  "extrator": "mock",
  "versao_schema": "0.2.0"
}
```

## Pontuação provisória

- **Cor:** regras explícitas em [triagem/dados/regras.json](triagem/dados/regras.json). A maior
  cor mínima acionada vale.
- **Pontuação (0 a 100 dentro da cor):** soma de pesos dos sinais presentes (a dor entra
  proporcional à nota). Ao chegar a 100, o paciente sobe uma cor.
- **Nada reduz a pontuação:** pesos nunca são negativos, "não sabe/recusou/incerto" não contam
  como ausência, e se o relato cita um sinal que a resposta direta nega, o status mostrado é o da
  resposta, mas a pontuação o conta como presente (com alerta). Um teste com sequências aleatórias
  confirma que cor e pontuação só sobem.
- **Todos os limites, regras e pesos são propostas da equipe, sem revisão clínica.** Cada saída
  traz `provisoria: true` e `regras_validadas: false`, e `regras_aplicadas` mostra quais regras
  geraram o resultado.

## Extratores

A leitura do relato fica atrás da interface `Extrator` ([triagem/extracao.py](triagem/extracao.py)),
e as implementações são intercambiáveis:

- `mock`: palavras-chave, sem rede. Serve para testes e como linha de base.
- `ollama`: modelo local via Ollama (`TRIAGEM_MODELO`, padrão `llama3.1:8b`; `OLLAMA_HOST`). O
  texto só sai da máquina se o host não for local, e nesse caso há um aviso.

O contrato do extrator é imposto pelo código, não pelo modelo: só sinais citados no relato
(presente, negado ou incerto), com trecho conferido contra o texto; "negado" só se o relato
nega; alergia só como "presente"; valores fora da faixa são descartados; item inválido é
descartado com aviso, sem derrubar a extração.

## Avaliação

`python -m triagem.avaliar` mede precisão, revocação e, em separado, os **erros que subestimam o
risco** (sinal presente omitido ou dado como negado). O gabarito
([avaliacao/relatos_simulados.json](avaliacao/relatos_simulados.json)) é pequeno, escrito pela
equipe e sem revisão clínica. A partição `teste` só pode ser usada uma vez por versão do prompt
(`--teste`) e nunca entra em exemplos do prompt ou em ajuste.

## Testes

```bash
python -m pytest
```

Os testes não usam rede: o modelo é sempre trocado por um extrator falso.

## Documentos da equipe

[agente_triagem.md](agente_triagem.md) (instruções do agente e banco de perguntas) e a pasta
[arquivos de arquitetura/](arquivos%20de%20arquitetura/) (projeto, riscos, legislação, linha do
tempo do atendimento e pontos de discussão).
