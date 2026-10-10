"""Avalia extratores Ollama contra relatos simulados com gabarito.

Uso: python -m triagem.avaliar --modelo llama3.1:8b --modelo qwen2.5:7b [--detalhe]

Métricas por modelo, sobre os sinais do gabarito:
  acertos   sinal com o status esperado
  omitidos  sinal esperado que o modelo não citou
  trocados  sinal citado com status contrário ao esperado (ex.: negação perdida)
  extras    sinal citado que o gabarito não prevê (possível invenção)
Também mede duração e alergia. O gabarito é pequeno e foi escrito à mão: serve
para comparar modelos e prompts, não como prova de qualidade clínica.
"""

import argparse
import json
import logging
import sys
import time
from pathlib import Path

from triagem.cli import configurar_io
from triagem.extrator_ollama import ErroExtracao, OllamaExtrator

GABARITO = Path(__file__).parent.parent / "avaliacao" / "relatos_simulados.json"


def avaliar_relato(extracao, caso: dict) -> dict:
    esperado = caso.get("sinais", {})
    obtido = {s.nome.value: s.status.value for s in extracao.sinais}
    r = {"acertos": [], "omitidos": [], "trocados": [], "extras": []}
    for nome, status in esperado.items():
        if nome not in obtido:
            r["omitidos"].append(f"{nome}={status}")
        elif obtido[nome] != status:
            r["trocados"].append(f"{nome}: esperado {status}, veio {obtido[nome]}")
        else:
            r["acertos"].append(nome)
    r["extras"] = [f"{n}={s}" for n, s in obtido.items() if n not in esperado]

    d = extracao.duracao
    if "duracao" in caso:
        valor, unidade = caso["duracao"]
        r["duracao_ok"] = bool(d and d.valor == valor and d.unidade.value == unidade)
    else:
        r["duracao_inventada"] = d is not None
    al = extracao.alergias_medicamentosas
    r["alergia_ok"] = (al.status.value if al else None) == caso.get("alergia")
    return r


def avaliar_modelo(modelo: str, casos: list[dict], detalhe: bool) -> dict:
    extrator = OllamaExtrator(modelo=modelo)
    tot = {"acertos": 0, "omitidos": 0, "trocados": 0, "extras": 0, "extras_presente": 0, "duracao_ok": 0,
           "duracao_n": 0, "duracao_inventada": 0, "alergia_ok": 0, "falhas": 0}
    inicio = time.time()
    for caso in casos:
        try:
            r = avaliar_relato(extrator.extrair(caso["relato"]), caso)
        except ErroExtracao as e:
            tot["falhas"] += 1
            if detalhe:
                print(f"  [FALHA] {caso['relato']!r}: {e}")
            continue
        for k in ("acertos", "omitidos", "trocados", "extras"):
            tot[k] += len(r[k])
        tot["extras_presente"] += sum(e.endswith("=presente") for e in r["extras"])
        tot["alergia_ok"] += r["alergia_ok"]
        if "duracao_ok" in r:
            tot["duracao_n"] += 1
            tot["duracao_ok"] += r["duracao_ok"]
        else:
            tot["duracao_inventada"] += r["duracao_inventada"]
        if detalhe and (r["omitidos"] or r["trocados"] or r["extras"]
                        or not r["alergia_ok"] or r.get("duracao_ok") is False):
            print(f"  {caso['relato']!r}")
            for k in ("omitidos", "trocados", "extras"):
                for item in r[k]:
                    print(f"      {k[:-1]}: {item}")
            if not r["alergia_ok"]:
                print("      alergia incorreta")
            if r.get("duracao_ok") is False:
                print("      duração incorreta")
    tot["segundos"] = round(time.time() - inicio, 1)
    return tot


def main(argv: list[str] | None = None) -> int:
    configurar_io()
    logging.getLogger("httpx").setLevel(logging.WARNING)
    parser = argparse.ArgumentParser(prog="python -m triagem.avaliar")
    parser.add_argument("--modelo", action="append", required=True,
                        help="modelo Ollama; pode repetir")
    parser.add_argument("--detalhe", action="store_true", help="mostra os erros por relato")
    args = parser.parse_args(argv)

    casos = json.loads(GABARITO.read_text(encoding="utf-8"))
    esperados = sum(len(c.get("sinais", {})) for c in casos)
    print(f"{len(casos)} relatos, {esperados} sinais esperados\n")
    for modelo in args.modelo:
        print(f"== {modelo}")
        t = avaliar_modelo(modelo, casos, args.detalhe)
        print(f"  sinais: {t['acertos']}/{esperados} certos | {t['omitidos']} omitidos | "
              f"{t['trocados']} trocados | {t['extras']} extras "
              f"({t['extras_presente']} presentes, {t['extras'] - t['extras_presente']} negados)")
        print(f"  duração: {t['duracao_ok']}/{t['duracao_n']} certas | "
              f"{t['duracao_inventada']} inventadas")
        print(f"  alergia: {t['alergia_ok']}/{len(casos)} certas | "
              f"respostas inválidas: {t['falhas']} | tempo: {t['segundos']}s\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
