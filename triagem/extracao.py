"""Interface de extração a partir do relato breve (P01).

A IA (ou o mock) só entende linguagem e extrai dados; nunca decide gravidade.
Toda chamada a modelo fica atrás de `Extrator`, e as implementações são
intercambiáveis.
"""

from abc import ABC, abstractmethod

from pydantic import BaseModel, Field

from triagem.schema import AlergiasMedicamentosas, Duracao, Sinal

NOME_PADRAO = "mock"


class Extracao(BaseModel):
    """O que o extrator devolve: só o que o relato cita.

    `sinais` contém apenas sinais citados (presente ou negado); o código
    completa o resto como nao_mencionado.
    """

    queixa_principal: str | None = None
    duracao: Duracao | None = None
    sinais: list[Sinal] = Field(default_factory=list)
    alergias_medicamentosas: AlergiasMedicamentosas | None = None


class Extrator(ABC):
    nome: str

    @abstractmethod
    def extrair(self, relato: str) -> Extracao:
        """Extrai queixa, duração e sinais citados no texto do relato."""


def criar_extrator(nome: str) -> Extrator:
    if nome == "mock":
        from triagem.extrator_mock import MockExtrator

        return MockExtrator()
    if nome == "ollama":
        from triagem.extrator_ollama import OllamaExtrator

        return OllamaExtrator()
    raise ValueError(f"extrator desconhecido: {nome}")
