"""Extrator que usa um modelo local via Ollama.

O modelo só entende o texto e devolve dados estruturados; nunca decide
gravidade. A saída é validada contra um schema fechado antes de ser aceita.
"""

import json
import os
import re
import unicodedata

from pydantic import BaseModel, ValidationError

from triagem.extracao import Extracao, Extrator
from triagem.schema import AlergiasMedicamentosas, Duracao, Sinal
from triagem.sinais import NomeSinal, Origem, Status

MODELO_PADRAO = "llama3.1:8b"
LIMITE_TOKENS = 600  # evita geração sem fim (JSON truncado vira ErroExtracao)
TIMEOUT_S = 120

INSTRUCOES = f"""Você extrai dados de um relato curto de paciente, em português.
Responda SOMENTE com JSON no formato pedido. Regras:
- Não avalie gravidade, não dê diagnóstico nem conselho.
- queixa_principal: a queixa em poucas palavras, em minúsculas.
- duracao: só se o relato disser há quanto tempo (unidade: minutos, horas, dias, semanas, meses ou anos); senão null.
- sinais: inclua SOMENTE sinais citados no relato, com status "presente" ou "negado" (ex.: "sem febre" = negado). Nunca invente.
  Nomes permitidos: {", ".join(n.value for n in NomeSinal)}.
  "valor" é opcional (nota da dor, temperatura em °C, local da dor).
- "sem X", "não tenho X" e "nunca teve X" significam status "negado", NUNCA "presente".
- "ontem" = 1 dia; "esta manhã" = poucas horas. Converta para número + unidade.
- alergias_medicamentosas: se o relato citar alergia a medicamento, status "presente" e os nomes; se negar, status "negado"; se não falar de alergia, null."""


# Exemplos (relato -> JSON esperado) para ancorar negações, duração e alergia.
EXEMPLOS = [
    ("tosse seca há 3 dias, sem febre",
     {"queixa_principal": "tosse seca",
      "duracao": {"valor": 3, "unidade": "dias"},
      "sinais": [{"nome": "febre", "status": "negado"}],
      "alergias_medicamentosas": None}),
    ("falta de ar e dor forte no peito desde ontem, alérgico a penicilina",
     {"queixa_principal": "falta de ar e dor no peito",
      "duracao": {"valor": 1, "unidade": "dias"},
      "sinais": [{"nome": "dispneia", "status": "presente"},
                 {"nome": "dor", "status": "presente"},
                 {"nome": "local_dor", "status": "presente", "valor": "peito"}],
      "alergias_medicamentosas": {"status": "presente", "medicamentos": ["penicilina"]}}),
    ("barriga doendo há 5 horas, não tenho alergia a remédio, não bati nem caí",
     {"queixa_principal": "dor na barriga",
      "duracao": {"valor": 5, "unidade": "horas"},
      "sinais": [{"nome": "dor", "status": "presente"},
                 {"nome": "local_dor", "status": "presente", "valor": "abdome"},
                 {"nome": "trauma", "status": "negado"}],
      "alergias_medicamentosas": {"status": "negado", "medicamentos": []}}),
]


_NEGACAO = re.compile(r"\b(sem|nao|nada|nunca|nem|nenhum|nenhuma|ausencia)\b")


def _tem_negacao(texto: str) -> bool:
    base = unicodedata.normalize("NFD", texto.lower())
    base = "".join(c for c in base if not unicodedata.combining(c))
    return bool(_NEGACAO.search(base))


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

            cliente = ollama.Client(host=host or os.environ.get("OLLAMA_HOST") or None,
                                    timeout=TIMEOUT_S)
        self.cliente = cliente

    @staticmethod
    def _mensagens(relato: str) -> list[dict]:
        msgs = [{"role": "system", "content": INSTRUCOES}]
        for texto, resposta in EXEMPLOS:
            msgs.append({"role": "user", "content": texto})
            msgs.append({"role": "assistant", "content": json.dumps(resposta, ensure_ascii=False)})
        msgs.append({"role": "user", "content": relato})
        return msgs

    def extrair(self, relato: str) -> Extracao:
        try:
            resp = self.cliente.chat(
                model=self.modelo,
                messages=self._mensagens(relato),
                format=_Resposta.model_json_schema(),
                options={"temperature": 0, "num_predict": LIMITE_TOKENS},
            )
            bruto = resp["message"]["content"]
        except Exception as e:  # rede, modelo ausente etc.
            raise ErroExtracao(f"falha ao consultar o modelo '{self.modelo}': {e}") from e
        try:
            r = _Resposta.model_validate_json(bruto)
        except ValidationError as e:
            raise ErroExtracao(f"resposta do modelo fora do formato: {e}") from e

        # "negado" só vale se o relato traz alguma negação; modelos pequenos
        # costumam inventar negativas para sinais que o texto nem menciona.
        aceita_negado = _tem_negacao(relato)
        sinais = {
            s.nome: Sinal(nome=s.nome, status=s.status, valor=s.valor,
                          origem=Origem.EXTRAIDO_DO_RELATO)
            for s in r.sinais
            if s.status == Status.PRESENTE or (s.status == Status.NEGADO and aceita_negado)
        }
        alergias = r.alergias_medicamentosas
        if alergias and alergias.status == Status.NAO_MENCIONADO:
            alergias = None if not alergias.medicamentos else AlergiasMedicamentosas(
                status=Status.PRESENTE, medicamentos=alergias.medicamentos)
        return Extracao(queixa_principal=r.queixa_principal, duracao=r.duracao,
                        sinais=list(sinais.values()), alergias_medicamentosas=alergias)
