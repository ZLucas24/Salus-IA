"""Agente de relato: texto livre -> queixa e sinais em JSON.

Uso: python -m triagem.relato "dor no peito há 2 horas" [--extrator mock|ollama]
stdout: somente o JSON; logs e erros: stderr.
"""

import argparse
import json
import logging
import sys

from triagem.cli import configurar_io
from triagem.extracao import NOME_PADRAO, Extracao, criar_extrator
from triagem.pontuacao import pontuar

MAX_RELATO = 200


def analisar_relato(relato: str, extracao: Extracao, extrator: str) -> dict:
    return {
        "relato_original": relato,
        "extrator": extrator,
        "queixa_principal": extracao.queixa_principal,
        "duracao": extracao.duracao.model_dump(mode="json") if extracao.duracao else None,
        "sinais": [s.model_dump(mode="json") for s in extracao.sinais],
        "alergias_medicamentosas": (extracao.alergias_medicamentosas.model_dump(mode="json")
                                    if extracao.alergias_medicamentosas else None),
        "pontuacao": pontuar(extracao),
        "pontuacao_provisoria": True,
    }


def main(argv: list[str] | None = None) -> int:
    configurar_io()
    log = logging.getLogger("triagem")

    parser = argparse.ArgumentParser(
        prog="python -m triagem.relato",
        description="Extrai queixa e sinais de um relato em texto livre (dados simulados)")
    parser.add_argument("relato", help="texto do relato, até 200 caracteres")
    parser.add_argument("--extrator", choices=["mock", "ollama"], default=NOME_PADRAO,
                        help="implementação do extrator (padrão: %(default)s)")
    args = parser.parse_args(argv)

    relato = args.relato.strip()
    if not relato:
        log.error("o relato não pode ser vazio")
        return 1
    if len(relato) > MAX_RELATO:
        log.error("o relato tem %d caracteres; o máximo é %d", len(relato), MAX_RELATO)
        return 1

    from dotenv import load_dotenv

    load_dotenv()
    try:
        extrator = criar_extrator(args.extrator)
        extracao = extrator.extrair(relato)
    except Exception as e:  # ErroExtracao e falhas de conexão
        log.error("%s", e)
        return 1

    json.dump(analisar_relato(relato, extracao, extrator.nome), sys.stdout,
              ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
