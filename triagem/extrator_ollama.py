"""Extrator que usa um modelo local via Ollama.

O modelo só entende o texto e devolve dados estruturados; nunca decide
gravidade. A saída é validada contra um schema fechado antes de ser aceita.
"""

import os

from pydantic import BaseModel, ValidationError

from triagem.extracao import Extracao, Extrator
from triagem.schema import AlergiasMedicamentosas, Duracao, Sinal
from triagem.sinais import NomeSinal, Origem, Status

MODELO_PADRAO = "llama3.2:3b"

INSTRUCOES = f"""Você extrai dados de um relato curto de paciente, em português.
Responda SOMENTE com JSON no formato pedido. Regras:
- Não avalie gravidade, não dê diagnóstico nem conselho.
- queixa_principal: a queixa em poucas palavras, em minúsculas.
- duracao: só se o relato disser há quanto tempo (unidade: minutos, horas, dias, semanas, meses ou anos); senão null.
- sinais: inclua SOMENTE sinais citados no relato, com status "presente" ou "negado" (ex.: "sem febre" = negado). Nunca invente.
  Nomes permitidos: {", ".join(n.value for n in NomeSinal)}.
  "valor" é opcional (nota da dor, temperatura em °C, local da dor).
- alergias_medicamentosas: só se o relato citar alergia a medicamento; senão null."""


class ErroExtracao(RuntimeError):
    """O modelo não respondeu ou respondeu algo fora do formato."""


class _Sinal(BaseModel):
    nome: NomeSinal
    status: Status
    valor: float | str | None = None


class _Resposta(BaseModel):
    queixa_principal: str | None = None
    duracao: Duracao | None = None
    sinais: list[_Sinal] = []
    alergias_medicamentosas: AlergiasMedicamentosas | None = None


class OllamaExtrator(Extrator):
    nome = "ollama"

    def __init__(self, modelo: str | None = None, host: str | None = None, cliente=None):
        self.modelo = modelo or os.environ.get("TRIAGEM_MODELO") or MODELO_PADRAO
        if cliente is None:
            import ollama

            cliente = ollama.Client(host=host or os.environ.get("OLLAMA_HOST") or None)
        self.cliente = cliente

    def extrair(self, relato: str) -> Extracao:
        try:
            resp = self.cliente.chat(
                model=self.modelo,
                messages=[{"role": "system", "content": INSTRUCOES},
                          {"role": "user", "content": relato}],
                format=_Resposta.model_json_schema(),
                options={"temperature": 0},
            )
            bruto = resp["message"]["content"]
        except Exception as e:  # rede, modelo ausente etc.
            raise ErroExtracao(f"falha ao consultar o modelo '{self.modelo}': {e}") from e
        try:
            r = _Resposta.model_validate_json(bruto)
        except ValidationError as e:
            raise ErroExtracao(f"resposta do modelo fora do formato: {e}") from e

        sinais = {
            s.nome: Sinal(nome=s.nome, status=s.status, valor=s.valor,
                          origem=Origem.EXTRAIDO_DO_RELATO)
            for s in r.sinais
            if s.status != Status.NAO_MENCIONADO
        }
        return Extracao(queixa_principal=r.queixa_principal, duracao=r.duracao,
                        sinais=list(sinais.values()),
                        alergias_medicamentosas=r.alergias_medicamentosas)
