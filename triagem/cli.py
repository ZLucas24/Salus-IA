"""Linha de comando. stdout: somente o JSON; logs: stderr."""

import argparse
import json
import logging
import sys
from pathlib import Path

from triagem.entrevista import FichaInvalida, processar_ficha
from triagem.extracao import NOME_PADRAO, criar_extrator


def configurar_io() -> None:
    """UTF-8 mesmo no terminal do Windows; logs somente no stderr."""
    for fluxo in (sys.stdout, sys.stderr):
        fluxo.reconfigure(encoding="utf-8")
    logging.basicConfig(stream=sys.stderr, level=logging.INFO,
                        format="[%(levelname)s] %(message)s")


def main(argv: list[str] | None = None) -> int:
    configurar_io()
    log = logging.getLogger("triagem")

    parser = argparse.ArgumentParser(
        prog="triagem", description="Salus IA: triagem (somente dados simulados)")
    parser.add_argument("ficha", type=Path, help="arquivo JSON com a ficha do paciente")
    parser.add_argument("--extrator", choices=["mock", "ollama"], default=NOME_PADRAO,
                        help="implementação do extrator (padrão: %(default)s)")
    args = parser.parse_args(argv)

    try:
        with open(args.ficha, encoding="utf-8-sig") as f:
            ficha = json.load(f)
    except OSError as e:
        log.error("não foi possível ler '%s': %s", args.ficha, e)
        return 2
    except json.JSONDecodeError as e:
        log.error("JSON inválido em '%s': %s", args.ficha, e)
        return 2

    try:
        saida = processar_ficha(ficha, criar_extrator(args.extrator))
    except FichaInvalida as e:
        log.error("ficha inválida (%d problema(s)):", len(e.erros))
        for erro in e.erros:
            print(f"  - {erro}", file=sys.stderr)
        return 1

    log.info("ficha processada; perguntas pendentes: %d", len(saida.perguntas_pendentes))
    json.dump(saida.model_dump(mode="json"), sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0
