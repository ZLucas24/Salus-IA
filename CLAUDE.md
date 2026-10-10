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
8. Dados somente simulados; a partição de teste nunca entra em treino.
9. Supabase e Hugging Face são opcionais: o comando principal roda sem rede.

## Modelo padrão

`TRIAGEM_MODELO` (padrão `llama3.2:3b`), servido via Ollama (`OLLAMA_HOST`).
