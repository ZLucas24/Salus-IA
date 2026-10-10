# Salus IA

Protótipo de um agente de triagem hospitalar com foco no SUS, feito para um
hackathon. A entrevista é conduzida por um atendente, com perguntas estruturadas.
O sistema transforma a ficha em um JSON padronizado com sinais, duração, alergias
e perguntas pendentes.

A IA só entende linguagem e extrai dados do relato; **nunca decide gravidade**. A
pontuação virá de regras explícitas em código (hoje é um *stub* que devolve um
número fixo, e o resultado sai marcado como provisório).

> **Aviso: todos os dados são simulados.** Não há pacientes reais no repositório
> e nenhum dado real deve ser colocado nele. Esta ferramenta não é um dispositivo
> médico e não deve ser usada em atendimento real.

## Sobre o projeto

Startup que usa inteligência artificial para acelerar a qualidade da saúde

Aqui vamos iniciar o desenvolvimento de um agente de IA com foco em atendimento e triagem de pacientes. Inicialmente pensamos no problema da demora do SUS no atendimento, mas após debates e tempestades de ideias observamos uma coisa diferente. É necessário que utilizemos o agente para além disso, devemos expandir a tecnologia para todo e qualquer hospital.

## Instalação

Requer Python 3.11 ou superior.

```bash
python -m venv .venv
source .venv/Scripts/activate   # Windows (Git Bash); no PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env            # opcional: o comando principal não precisa de chaves
```

Supabase e Hugging Face são opcionais, e o comando principal roda sem rede.

## Formato da ficha

Um arquivo JSON com os dados do atendente e as respostas por id de pergunta. Só a
`idade` é obrigatória; pergunta sem resposta fica como `nao_mencionado` e entra em
`perguntas_pendentes`. As perguntas e seus tipos estão em
[triagem/dados/questionario.json](triagem/dados/questionario.json).

| Pergunta | Formato da resposta |
|---|---|
| P01 relato breve | texto, até 200 caracteres |
| P02 duração | `{"valor": 2, "unidade": "horas"}` (minutos, horas, dias, semanas, meses, anos) |
| P03, P06, P10, P11 | `true` ou `false` |
| P04 dor | `{"resposta": true, "escala": 8}` (escala de 0 a 10, obrigatória se sim) |
| P05 local da dor | `"cabeca"`, `"peito"`, `"abdome"`, `"costas"`, `"membros"` ou `"outro"` |
| P07 sangramento | `{"ha_sangramento": true, "sangrando_agora": false}` |
| P08 consciência | `{"desmaiou_ou_confuso": false, "convulsao": false}` |
| P09 febre | `{"resposta": true, "valor": 38.5}` (`valor` opcional, em °C) |
| P12 risco | `{"gravida": false, "doenca_cronica": ["diabetes"]}` (diabetes, coracao, pressao, pulmao) |
| P13 alergia | `{"resposta": true, "texto": "dipirona, penicilina"}` |

Dados do atendente: `idade` (obrigatória), `temperatura`, `frequencia_cardiaca`,
`pressao_sistolica`, `pressao_diastolica` e `saturacao` (opcionais).

Há fichas de exemplo em [exemplos/](exemplos/), incluindo três que falham de
propósito (P01 com 201 caracteres, sem idade e resposta com tipo errado).

## Uso

```bash
python -m triagem exemplos/ficha_exemplo.json
python -m triagem exemplos/ficha_exemplo.json --extrator mock   # igual ao anterior
```

- **stdout**: somente o JSON, indentado e em UTF-8.
- **stderr**: logs e mensagens de erro.
- **Código de saída**: `0` sucesso; `1` ficha inválida (o stderr diz qual pergunta
  falhou); `2` arquivo ilegível, JSON quebrado ou argumento inválido.

Para salvar a saída: `python -m triagem ficha.json > saida.json`.

### Testar só o relato (texto livre)

```bash
python -m triagem.relato "dor no peito há 2 horas"
python -m triagem.relato "dor no peito há 2 horas" --extrator ollama   # exige Ollama rodando
```

Devolve em JSON a queixa, a duração e só os sinais citados, com `pontuacao` fixa
(stub) e `pontuacao_provisoria: true`. O extrator `ollama` usa `TRIAGEM_MODELO`
(padrão `llama3.1:8b`) e `OLLAMA_HOST` do `.env`; se o servidor não estiver
disponível, o comando falha com mensagem no stderr.

### Extratores

A leitura do relato (P01) fica atrás da interface `Extrator`
([triagem/extracao.py](triagem/extracao.py)), então as implementações são
intercambiáveis. Por enquanto existe só o `mock` (padrão), que usa palavras-chave
e não faz chamadas de rede. Ele devolve apenas o que o relato cita (sinal
presente ou negado), com origem `extraido_do_relato`. O código completa o resto
como `nao_mencionado`. Se o relato e uma pergunta fechada divergirem, a **resposta
direta prevalece**.

## Exemplo

`python -m triagem exemplos/ficha_05_alergia_so_na_extracao.json`: o relato cita
alergia à dipirona, mas a P13 não foi respondida; por isso a alergia aparece e a
P13 continua pendente para confirmação.

```json
{
  "relato_original": "Coceira e manchas na pele, sou alérgico a dipirona",
  "respostas": [
    {
      "id_pergunta": "P01",
      "resposta_bruta": "Coceira e manchas na pele, sou alérgico a dipirona"
    },
    {
      "id_pergunta": "P02",
      "resposta_bruta": "{\"valor\": 2, \"unidade\": \"dias\"}"
    }
  ],
  "queixa_principal": "coceira e manchas na pele, sou alérgico a dipirona",
  "duracao": {
    "valor": 2.0,
    "unidade": "dias"
  },
  "sinais": [
    {
      "nome": "inicio_subito",
      "status": "nao_mencionado",
      "valor": null,
      "origem": "resposta_direta"
    },
    {
      "nome": "dor",
      "status": "nao_mencionado",
      "valor": null,
      "origem": "resposta_direta"
    },
    {
      "nome": "local_dor",
      "status": "nao_mencionado",
      "valor": null,
      "origem": "resposta_direta"
    },
    {
      "nome": "dispneia",
      "status": "nao_mencionado",
      "valor": null,
      "origem": "resposta_direta"
    },
    {
      "nome": "sangramento",
      "status": "nao_mencionado",
      "valor": null,
      "origem": "resposta_direta"
    },
    {
      "nome": "alteracao_consciencia",
      "status": "nao_mencionado",
      "valor": null,
      "origem": "resposta_direta"
    },
    {
      "nome": "convulsao",
      "status": "nao_mencionado",
      "valor": null,
      "origem": "resposta_direta"
    },
    {
      "nome": "febre",
      "status": "nao_mencionado",
      "valor": null,
      "origem": "resposta_direta"
    },
    {
      "nome": "vomito_persistente",
      "status": "nao_mencionado",
      "valor": null,
      "origem": "resposta_direta"
    },
    {
      "nome": "trauma",
      "status": "nao_mencionado",
      "valor": null,
      "origem": "resposta_direta"
    },
    {
      "nome": "gravidez",
      "status": "nao_mencionado",
      "valor": null,
      "origem": "resposta_direta"
    },
    {
      "nome": "doenca_cronica",
      "status": "nao_mencionado",
      "valor": null,
      "origem": "resposta_direta"
    }
  ],
  "alergias_medicamentosas": {
    "status": "presente",
    "medicamentos": [
      "dipirona"
    ]
  },
  "dados_atendente": {
    "idade": 29,
    "temperatura": null,
    "frequencia_cardiaca": null,
    "pressao_sistolica": null,
    "pressao_diastolica": null,
    "saturacao": null
  },
  "perguntas_pendentes": [
    "P03",
    "P04",
    "P05",
    "P06",
    "P07",
    "P08",
    "P09",
    "P10",
    "P11",
    "P12",
    "P13"
  ],
  "pontuacao": 0,
  "pontuacao_provisoria": true,
  "versao_schema": "0.1.0",
  "extrator": "mock"
}
```

## Testes

```bash
python -m pytest
```

Os testes não usam rede: trocam o extrator por um `ExtratorFalso`.
