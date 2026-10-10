# Salus IA — regras do projeto

Protótipo de agente de triagem hospitalar com foco no SUS, feito para um hackathon.
Python 3.11+. Pacote `triagem`, executado com `python -m triagem`.

## Regras

1. A IA só entende linguagem e extrai dados do relato; nunca decide gravidade.
2. A pontuação de gravidade vem de regras explícitas escritas em código.
3. O stdout do comando contém apenas o JSON; logs e mensagens vão para o stderr.
4. Nunca commitar `.env` nem chaves de API (use `.env.example` sem valores).
5. Somente relatos simulados no repositório; não há pacientes reais.
