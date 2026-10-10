"""Extração de queixa e sinais a partir do relato breve (P01)."""

from dataclasses import dataclass

from triagem.schema import Sinal
from triagem.sinais import NomeSinal, Origem, Status


@dataclass
class Extracao:
    queixa_principal: str
    sinais: list[Sinal]


def extrair(relato: str, mock: bool = True) -> Extracao:
    """Só o modo mock existe por enquanto: devolve valores fixos e válidos,
    independentes do texto. A IA só extrai dados; nunca decide gravidade."""
    if not mock:
        raise NotImplementedError("extração real ainda não implementada; use --mock")
    return Extracao(
        queixa_principal="dor no peito",
        sinais=[
            Sinal(nome=NomeSinal.DOR, status=Status.PRESENTE,
                  origem=Origem.EXTRAIDO_DO_RELATO),
            Sinal(nome=NomeSinal.DISPNEIA, status=Status.PRESENTE,
                  origem=Origem.EXTRAIDO_DO_RELATO),
        ],
    )
