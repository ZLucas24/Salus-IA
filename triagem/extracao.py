"""Contrato de extração a partir do relato livre (Q01).

A IA (ou o mock) só entende linguagem e extrai dados; nunca decide gravidade.
Toda chamada a modelo fica atrás de `Extrator`, e as implementações são
intercambiáveis. O contrato é aplicado pelo próprio modelo `Extracao`: o
extrator devolve só o que o relato cita, com origem `extraido_do_relato`.
"""

import importlib
from abc import ABC, abstractmethod

from pydantic import BaseModel, Field, model_validator

from triagem.schema import Alergias, Duracao, Sinal
from triagem.sinais import SINAIS_MEDIDOS, Origem, Queixa, Status

NOME_PADRAO = "mock"
ESTADOS_EXTRAIVEIS = frozenset({Status.PRESENTE, Status.NEGADO, Status.INCERTO})

# nome da linha de comando -> "módulo:Classe" (importado só quando usado)
EXTRATORES = {
    "mock": "triagem.extrator_mock:MockExtrator",
    "ollama": "triagem.extrator_ollama:OllamaExtrator",
}
NOMES_EXTRATORES = tuple(EXTRATORES)


class Extracao(BaseModel):
    """O que um extrator devolve. Violações do contrato viram erro de validação."""

    queixa_principal: str | None = None
    queixas: list[Queixa] = Field(default_factory=list)
    duracao: Duracao | None = None
    sinais: list[Sinal] = Field(default_factory=list)
    alergias: Alergias | None = None
    avisos: list[str] = Field(default_factory=list)  # o que foi descartado e por quê

    @model_validator(mode="after")
    def _contrato(self):
        for s in self.sinais:
            if s.nome in SINAIS_MEDIDOS:
                raise ValueError(f"{s.nome.value} vem das aferições, não do relato")
            if s.status not in ESTADOS_EXTRAIVEIS:
                raise ValueError(f"o relato só pode indicar presente, negado ou incerto "
                                 f"({s.nome.value}: {s.status.value})")
            if s.origem != Origem.EXTRAIDO_DO_RELATO:
                raise ValueError("sinais extraídos devem ter origem extraido_do_relato")
        if len({s.nome for s in self.sinais}) != len(self.sinais):
            raise ValueError("sinal repetido na extração")
        if self.alergias is not None and self.alergias.status != Status.PRESENTE:
            raise ValueError("alergia só pode vir do relato como 'presente'; "
                             "negar alergia é função da pergunta direta (Q10)")
        return self


class Extrator(ABC):
    """Interface de extração. `nome` identifica a implementação (e o modelo) na saída."""

    nome: str

    @abstractmethod
    def extrair(self, relato: str) -> Extracao:
        """Extrai queixa, duração, sinais e alergia citados no texto do relato."""


def criar_extrator(nome: str) -> Extrator:
    if nome not in EXTRATORES:
        raise ValueError(f"extrator desconhecido: {nome} (opções: {', '.join(NOMES_EXTRATORES)})")
    modulo, classe = EXTRATORES[nome].split(":")
    return getattr(importlib.import_module(modulo), classe)()
