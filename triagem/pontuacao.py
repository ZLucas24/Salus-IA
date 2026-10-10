"""Pontuação de risco."""

from triagem.extracao import Extracao
from triagem.schema import SaidaTriagem


def pontuar(extracao: SaidaTriagem | Extracao) -> int:
    """Recebe a extração já estruturada (nunca o texto cru).

    STUB: devolve um número fixo. Deve ser substituído pelas regras explícitas
    de pontuação, escritas em código.
    """
    return 0
