"""Laboratório de extração: relato em texto livre -> queixa e sinais em JSON.

Uso: python -m triagem.relato "dor no peito há 2 horas" [--extrator mock|ollama]
     echo "dor no peito" | python -m triagem.relato -

Só extrai (não pontua): a pontuação depende de respostas e aferições que um
relato sozinho não tem. stdout: somente o JSON; logs e erros: stderr.
Códigos de saída: 0 sucesso; 1 relato inválido; 2 uso incorreto; 3 erro
interno; 4 extrator indisponível ou com resposta inválida.
"""

import argparse
import json
import logging
import sys

from triagem.cli import SAIDA_INTERNO, SAIDA_OK, SAIDA_USO, carregar_env, configurar_io, escrever_saida
from triagem.extracao import NOME_PADRAO, NOMES_EXTRATORES, criar_extrator
from triagem.texto import validar_relato

SAIDA_RELATO_INVALIDO, SAIDA_EXTRACAO = 1, 4


def analisar_relato(relato: str, extrator) -> dict:
    extracao = extrator.extrair(relato)
    return {"relato_original": relato, "extrator": extrator.nome, **extracao.model_dump(mode="json")}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m triagem.relato",
        description="Extrai queixa e sinais de um relato em texto livre. Use apenas dados "
                    "simulados; o relato nunca deve conter dados reais de pacientes.")
    parser.add_argument("relato", help="texto do relato (até 200 caracteres), ou - para ler do stdin")
    parser.add_argument("--extrator", choices=NOMES_EXTRATORES, default=NOME_PADRAO,
                        help="implementação do extrator (padrão: %(default)s)")
    parser.add_argument("-q", "--silencioso", action="store_true", help="só avisos e erros no stderr")
    args = parser.parse_args(argv)
    configurar_io(args.silencioso)
    log = logging.getLogger("triagem")
    try:
        texto = sys.stdin.read() if args.relato == "-" else args.relato
        try:
            relato = validar_relato(texto)
        except ValueError as e:
            log.error("%s", e)
            return SAIDA_RELATO_INVALIDO
        carregar_env()
        try:
            resultado = analisar_relato(relato, criar_extrator(args.extrator))
        except Exception as e:  # ErroExtracao, conexão, pacote ausente
            log.error("%s", e)
            return SAIDA_EXTRACAO
        escrever_saida(json.dumps(resultado, ensure_ascii=False, indent=2) + "\n")
        return SAIDA_OK
    except Exception:
        log.exception("erro interno inesperado")
        return SAIDA_INTERNO


if __name__ == "__main__":
    sys.exit(main())
