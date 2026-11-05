"""Linha de comando. stdout: somente o JSON; logs e erros: stderr.

Códigos de saída: 0 sucesso; 1 ficha inválida; 2 uso incorreto, arquivo
ilegível ou JSON quebrado; 3 erro interno.
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path

from triagem.entrevista import FichaInvalida, processar_ficha
from triagem.extracao import NOME_PADRAO, NOMES_EXTRATORES, criar_extrator

TAMANHO_MAXIMO = 1_000_000  # bytes; uma ficha tem poucos KB
SAIDA_OK, SAIDA_FICHA_INVALIDA, SAIDA_USO, SAIDA_INTERNO = 0, 1, 2, 3


def configurar_io(silencioso: bool = False) -> None:
    """UTF-8 mesmo no terminal do Windows; logs somente no stderr."""
    for fluxo in (sys.stdout, sys.stderr):
        if hasattr(fluxo, "reconfigure"):
            fluxo.reconfigure(encoding="utf-8", newline="\n")  # bytes iguais em qualquer sistema
    if hasattr(sys.stdin, "reconfigure"):
        sys.stdin.reconfigure(encoding="utf-8")
    logging.basicConfig(stream=sys.stderr, level=logging.WARNING if silencioso else logging.INFO,
                        format="[%(levelname)s] %(message)s", force=True)
    logging.getLogger("httpx").setLevel(logging.WARNING)  # não loga cada chamada ao Ollama


def carregar_env() -> None:
    """Lê o .env (TRIAGEM_MODELO, OLLAMA_HOST...), se o pacote e o arquivo existirem."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv()


def escrever_saida(texto: str, destino: Path | None = None) -> None:
    """Escreve o JSON já montado por inteiro; nunca deixa um JSON truncado."""
    if destino is not None:
        destino.write_text(texto, encoding="utf-8")
        return
    try:
        sys.stdout.write(texto)
        sys.stdout.flush()
    except BrokenPipeError:  # ex.: `... | head`; sai sem traceback
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())


def ler_ficha(caminho: Path) -> dict:
    log = logging.getLogger("triagem")
    if str(caminho) == "-":
        bruto = sys.stdin.buffer.read(TAMANHO_MAXIMO + 1)
    else:
        if caminho.is_dir():
            raise OSError(f"'{caminho}' é uma pasta, não um arquivo")
        if caminho.stat().st_size > TAMANHO_MAXIMO:
            raise OSError(f"'{caminho}' é grande demais para uma ficha (máximo {TAMANHO_MAXIMO} bytes)")
        bruto = caminho.read_bytes()
    if len(bruto) > TAMANHO_MAXIMO:
        raise OSError("a entrada é grande demais para uma ficha")
    try:
        return json.loads(bruto.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        log.error("JSON inválido em '%s': %s", caminho, e)
        raise ValueError from e


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m triagem",
        description="Salus IA: triagem a partir de uma ficha JSON (somente dados simulados)")
    parser.add_argument("ficha", type=Path, help="arquivo JSON da ficha, ou - para ler do stdin")
    parser.add_argument("--extrator", choices=NOMES_EXTRATORES, default=NOME_PADRAO,
                        help="implementação do extrator (padrão: %(default)s)")
    parser.add_argument("--saida", type=Path, help="grava o JSON neste arquivo (UTF-8) em vez do stdout")
    parser.add_argument("-q", "--silencioso", action="store_true", help="só avisos e erros no stderr")
    args = parser.parse_args(argv)
    configurar_io(args.silencioso)
    log = logging.getLogger("triagem")
    try:
        carregar_env()
        try:
            ficha = ler_ficha(args.ficha)
        except FileNotFoundError:
            log.error("arquivo não encontrado: '%s'", args.ficha)
            return SAIDA_USO
        except OSError as e:
            log.error("não foi possível ler '%s': %s", args.ficha, e)
            return SAIDA_USO
        except ValueError:
            return SAIDA_USO

        try:
            saida = processar_ficha(ficha, criar_extrator(args.extrator))
        except FichaInvalida as e:
            log.error("ficha inválida (%d problema(s)):", len(e.erros))
            for erro in e.erros:
                logging.getLogger("triagem").error("  - %s", erro)
            return SAIDA_FICHA_INVALIDA

        log.info("ficha processada: cor sugerida %s, %d pergunta(s) pendente(s), %d alerta(s)",
                 saida.classificacao.cor.value, len(saida.perguntas_pendentes), len(saida.alertas))
        texto = json.dumps(saida.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n"
        escrever_saida(texto, args.saida)
        return SAIDA_OK
    except Exception:  # bug do sistema: não se confunde com ficha inválida (código 1)
        log.exception("erro interno inesperado")
        return SAIDA_INTERNO
