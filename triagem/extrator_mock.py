"""Extrator simulado: regras de palavras-chave fixas, sem rede e sem modelo.

Só serve para exercitar o fluxo; não é uma extração real.
"""

import re
import unicodedata

from triagem.extracao import Extracao, Extrator
from triagem.schema import AlergiasMedicamentosas, Duracao, Sinal
from triagem.sinais import NomeSinal, Origem, Status

# sinal -> (padrão de presença, padrão de negação), sobre texto sem acentos
_REGRAS: dict[NomeSinal, tuple[str, str]] = {
    NomeSinal.DOR: (r"\bdor\b", r"\bsem dor\b"),
    NomeSinal.DISPNEIA: (r"falta de ar", r"\bsem falta de ar\b"),
    NomeSinal.SANGRAMENTO: (r"sangr", r"\bsem sangramento\b"),
    NomeSinal.CONVULSAO: (r"convuls", r"\bsem convuls"),
    NomeSinal.FEBRE: (r"febre", r"\bsem febre\b"),
    NomeSinal.VOMITO_PERSISTENTE: (r"vomit", r"\bsem vomit"),
    NomeSinal.TRAUMA: (r"\bqueda\b|pancada|acidente", r"\bsem (queda|pancada|acidente)"),
}
_DURACAO = r"\b(?:ha|faz)\s+(\d+)\s*(minuto|hora|dia|semana|mes|ano)(?:s|es)?\b"
_UNIDADES = {"minuto": "minutos", "hora": "horas", "dia": "dias",
             "semana": "semanas", "mes": "meses", "ano": "anos"}
_ALERGIA = r"alergi\w*\s+(?:a|ao|aos)\s+([^.;]+)|alergic[oa]s?\s+(?:a|ao|aos)\s+([^.;]+)"


def _sem_acentos(texto: str) -> str:
    # caractere a caractere, para manter os mesmos índices do texto original
    return "".join(
        "".join(c for c in unicodedata.normalize("NFD", ch) if not unicodedata.combining(c))[:1]
        or ch
        for ch in texto
    )


class MockExtrator(Extrator):
    nome = "mock"

    def extrair(self, relato: str) -> Extracao:
        original = relato.strip()
        t = _sem_acentos(original).lower()

        sinais = []
        for nome, (presente, negado) in _REGRAS.items():
            if re.search(negado, t):
                status = Status.NEGADO
            elif re.search(presente, t):
                status = Status.PRESENTE
            else:
                continue
            sinais.append(Sinal(nome=nome, status=status, origem=Origem.EXTRAIDO_DO_RELATO))

        duracao = None
        if m := re.search(_DURACAO, t):
            duracao = Duracao(valor=int(m.group(1)), unidade=_UNIDADES[m.group(2)])

        alergias = None
        if re.search(r"\bsem alergia", t):
            alergias = AlergiasMedicamentosas(status=Status.NEGADO)
        elif m := re.search(_ALERGIA, t):
            trecho = original[m.start(1 if m.group(1) else 2):m.end(1 if m.group(1) else 2)]
            meds = [x.strip() for x in re.split(r",|;|\be\b", trecho) if x.strip()]
            alergias = AlergiasMedicamentosas(status=Status.PRESENTE, medicamentos=meds)

        queixa = original.lower().rstrip(".!? ")[:60] or None
        return Extracao(queixa_principal=queixa, duracao=duracao, sinais=sinais,
                        alergias_medicamentosas=alergias)
