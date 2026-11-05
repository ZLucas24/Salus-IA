"""Auxiliares dos testes. Nenhum teste usa rede: o modelo é sempre um falso."""

import subprocess
import sys
from pathlib import Path

from triagem.entrevista import processar_ficha
from triagem.extracao import Extracao, Extrator
from triagem.schema import Sinal
from triagem.sinais import Origem, Status

RAIZ = Path(__file__).parent.parent
EXEMPLOS = RAIZ / "exemplos"


class ExtratorFalso(Extrator):
    """Devolve sempre a mesma extração (ou levanta um erro), e registra as chamadas."""

    nome = "falso"

    def __init__(self, extracao: Extracao | None = None, erro: Exception | None = None):
        self.extracao = extracao or Extracao()
        self.erro = erro
        self.chamadas: list[str] = []

    def extrair(self, relato: str) -> Extracao:
        self.chamadas.append(relato)
        if self.erro:
            raise self.erro
        return self.extracao


def citado(nome, status=Status.PRESENTE, valor=None, itens=(), trecho=None) -> Sinal:
    return Sinal(nome=nome, status=status, valor=valor, itens=list(itens), trecho=trecho,
                 origem=Origem.EXTRAIDO_DO_RELATO)


def ficha(respostas=None, idade=30, sexo="masculino", **aferido):
    dados = {"idade": idade, "sexo_biologico": sexo, **aferido}
    return {"dados_atendente": dados, "respostas": respostas or {}}


def sinal(saida, nome):
    return next(s for s in saida.sinais if s.nome == nome)


def processar(f, extracao=None, erro=None):
    return processar_ficha(f, ExtratorFalso(extracao, erro))


def alerta(saida, codigo):
    return [a for a in saida.alertas if a.codigo == codigo]


def rodar(modulo, *args, entrada=None):
    return subprocess.run([sys.executable, "-m", modulo, *map(str, args)], capture_output=True,
                          cwd=RAIZ, input=entrada)
