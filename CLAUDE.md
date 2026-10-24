# Salus IA — regras do projeto

Protótipo de agente de triagem hospitalar com foco no SUS, feito para um hackathon.
Python 3.11+. Pacote `triagem`, executado com `python -m triagem`.

## Regras

1. A IA só entende linguagem e extrai dados do relato; nunca decide gravidade.
2. A pontuação de gravidade vem de regras explícitas escritas em código.
3. O stdout do comando contém apenas o JSON; logs e mensagens vão para o stderr.
4. Nunca commitar `.env` nem chaves de API (use `.env.example` sem valores).
5. Somente relatos simulados no repositório; não há pacientes reais.
6. A chamada ao modelo fica atrás da interface `Extrator`; as implementações
   (mock, Ollama etc.) são intercambiáveis.
7. Chaves e endereços só em `.env`, nunca no código.
8. Dados somente simulados; a partição de teste nunca entra em treino, em exemplo
   de prompt ou em ajuste de pesos.
9. Supabase e Hugging Face são opcionais: o comando principal roda sem rede.
10. Só o status `negado` conta como "não". `nao_mencionado`, `nao_sabe`, `recusou` e
    `incerto` nunca viram ausência de sinal, e aferição não feita nunca vale como normal.
11. Nada reduz a pontuação: pesos nunca são negativos e há teste com sequências
    aleatórias. Na divergência entre relato e resposta direta, o status exibido é o da
    resposta direta, mas a pontuação conta o sinal citado no relato (e há alerta).
12. Todo limite clínico, regra de cor e peso mora em `triagem/dados/regras.json`,
    marcado como NÃO validado até um revisor clínico conferir linha a linha.
13. O contrato do extrator é imposto pelo código (`Extracao`, filtros no extrator
    Ollama), nunca confiado ao modelo: sinal sem trecho comprovável no relato, negação
    inventada e alergia "negada" pelo relato são descartados.

## Mapa

- `triagem/dados/questionario.json`: banco de perguntas (fonte única). O roteiro em
  `docs/roteiro_entrevista.md` é GERADO por `python -m triagem.roteiro`; não editar à mão.
- `triagem/dados/regras.json`: limites das aferições, pesos e regras de cor.
- `triagem/entrevista.py`: fluxo em etapas (validar, interpretar, extrair, mesclar,
  pendências, alertas, pontuar).
- `agente_triagem.md` e `arquivos de arquitetura/`: documentos da equipe (Anna).

## Modelo padrão

`TRIAGEM_MODELO` (padrão `llama3.1:8b`), servido via Ollama (`OLLAMA_HOST`).
O extrator `mock` é o padrão do comando principal e funciona sem rede.
