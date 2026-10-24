"""Avalia extratores contra relatos simulados com gabarito.

Uso:
  python -m triagem.avaliar --alvo mock --alvo ollama:llama3.1:8b [--detalhe] [--saida resultado.json]
  python -m triagem.avaliar --alvo ollama:llama3.1:8b --teste   # partição de teste (uma vez por prompt)

Por extrator, sobre os sinais do gabarito:
  precisão     dos sinais "presente" que o extrator citou, quantos o gabarito confirma
  revocação    dos sinais "presente" do gabarito, quantos o extrator achou
  subestimam   erros que escondem risco: sinal presente omitido ou dado como negado
  invenções    sinais citados que o gabarito não prevê (possível alucinação)
Uma resposta inválida do extrator conta como omissão de todos os sinais do caso.
O gabarito é pequeno e foi escrito à mão: serve para comparar extratores e prompts.
"""

import argparse
import hashlib
import json
import logging
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from triagem.cli import configurar_io
from triagem.extracao import Extracao, criar_extrator
from triagem.extrator_ollama import EXEMPLOS, INSTRUCOES, OllamaExtrator
from triagem.sinais import Status
from triagem.texto import normalizar_itens, sem_acentos

PASTA = Path(__file__).parent.parent / "avaliacao"
GABARITO = PASTA / "relatos_simulados.json"
REGISTRO_TESTE = PASTA / "teste_usado.json"
TOLERANCIA_DURACAO = 0.25
MINUTOS = {"minutos": 1, "horas": 60, "dias": 1440, "semanas": 10080, "meses": 43200, "anos": 525600}


def hash_do_prompt() -> str:
    return hashlib.sha256((INSTRUCOES + json.dumps(EXEMPLOS, ensure_ascii=False)).encode()).hexdigest()[:12]


def criar_alvo(alvo: str):
    if alvo.startswith("ollama:"):
        return OllamaExtrator(modelo=alvo.split(":", 1)[1])
    return criar_extrator(alvo)


def _chave(itens) -> set[str]:
    return {sem_acentos(i).lower() for i in normalizar_itens(list(itens))}


def avaliar_caso(extracao: Extracao | None, caso: dict) -> dict:
    esperado = caso["sinais"]
    obtido = {s.nome.value: s.status.value for s in (extracao.sinais if extracao else [])}
    r = {"acertos": [], "omitidos": [], "trocados": [], "invencoes": [], "subestimam": []}
    for nome, status in esperado.items():
        if nome not in obtido:
            r["omitidos"].append(f"{nome}={status}")
            if status == "presente":
                r["subestimam"].append(f"{nome} omitido")
        elif obtido[nome] != status:
            r["trocados"].append(f"{nome}: esperado {status}, veio {obtido[nome]}")
            if status == "presente":
                r["subestimam"].append(f"{nome} dado como {obtido[nome]}")
        else:
            r["acertos"].append(nome)
    if extracao is not None:
        r["invencoes"] = [f"{n}={s}" for n, s in obtido.items() if n not in esperado]
    r["citados_presentes"] = sum(1 for s in obtido.values() if s == "presente")
    r["acertos_presentes"] = sum(1 for n in r["acertos"] if esperado[n] == "presente")
    r["esperados_presentes"] = sum(1 for s in esperado.values() if s == "presente")

    d = extracao.duracao if extracao else None
    if "duracao" in caso:
        valor, unidade = caso["duracao"]
        alvo_min = valor * MINUTOS[unidade]
        r["duracao_ok"] = bool(d and abs(d.valor * MINUTOS[d.unidade.value] - alvo_min)
                               <= TOLERANCIA_DURACAO * alvo_min)
    else:
        r["duracao_inventada"] = d is not None
    esperado_al = _chave(caso.get("alergia", []))
    obtido_al = _chave(extracao.alergias.itens) if extracao and extracao.alergias else set()
    r["alergia_ok"] = esperado_al == obtido_al
    if "queixas" in caso:
        r["queixa_ok"] = bool(extracao) and set(caso["queixas"]) <= {q.value for q in extracao.queixas}
    return r


def avaliar_alvo(alvo: str, casos: list[dict], detalhe: bool) -> dict:
    extrator = criar_alvo(alvo)
    soma = {"acertos": 0, "omitidos": 0, "trocados": 0, "invencoes": 0, "subestimam": 0,
            "citados_presentes": 0, "acertos_presentes": 0, "esperados_presentes": 0,
            "duracao_ok": 0, "duracao_n": 0, "duracao_inventada": 0, "alergia_ok": 0,
            "queixa_ok": 0, "queixa_n": 0, "falhas": 0}
    tempos, por_caso = [], []
    for caso in casos:
        inicio = time.perf_counter()
        try:
            extracao, erro = extrator.extrair(caso["relato"]), None
        except Exception as e:
            extracao, erro = None, str(e)
            soma["falhas"] += 1
        tempos.append(time.perf_counter() - inicio)
        r = avaliar_caso(extracao, caso)
        for k in ("acertos", "omitidos", "trocados", "invencoes", "subestimam"):
            soma[k] += len(r[k])
        for k in ("citados_presentes", "acertos_presentes", "esperados_presentes", "alergia_ok"):
            soma[k] += int(r[k])
        if "duracao_ok" in r:
            soma["duracao_n"] += 1
            soma["duracao_ok"] += int(r["duracao_ok"])
        else:
            soma["duracao_inventada"] += int(r["duracao_inventada"])
        if "queixa_ok" in r:
            soma["queixa_n"] += 1
            soma["queixa_ok"] += int(r["queixa_ok"])
        por_caso.append({"id": caso["id"], "erro": erro, **{k: v for k, v in r.items()
                         if isinstance(v, (list, bool))}})
        if detalhe and (erro or r["omitidos"] or r["trocados"] or r["invencoes"]
                        or not r["alergia_ok"] or r.get("duracao_ok") is False):
            print(f"  [{caso['id']}] {caso['relato']!r}")
            if erro:
                print(f"      FALHA: {erro}")
            for k in ("omitidos", "trocados", "invencoes"):
                for item in r[k]:
                    print(f"      {k[:-1] if k != 'invencoes' else 'invenção'}: {item}")
            if not r["alergia_ok"]:
                print("      alergia incorreta")
            if r.get("duracao_ok") is False:
                print("      duração incorreta")
    soma["tempo_medio_s"] = round(statistics.mean(tempos), 2)
    soma["tempo_maximo_s"] = round(max(tempos), 2)
    soma["casos"] = por_caso
    return soma


def _taxa(a: int, b: int) -> str:
    return f"{a}/{b} ({a / b:.0%})" if b else "n/a"


def imprimir(alvo: str, t: dict, total_esperado: int, n_casos: int) -> None:
    print(f"== {alvo}")
    print(f"  sinais:    {t['acertos']}/{total_esperado} certos | {t['omitidos']} omitidos | "
          f"{t['trocados']} trocados | {t['invencoes']} invenções")
    print(f"  precisão:  {_taxa(t['acertos_presentes'], t['citados_presentes'])} | "
          f"revocação: {_taxa(t['acertos_presentes'], t['esperados_presentes'])}")
    print(f"  erros que subestimam o risco: {t['subestimam']}")
    print(f"  duração:   {_taxa(t['duracao_ok'], t['duracao_n'])} certas | "
          f"{t['duracao_inventada']} inventadas")
    print(f"  queixa:    {_taxa(t['queixa_ok'], t['queixa_n'])} | alergia: {_taxa(t['alergia_ok'], n_casos)}")
    print(f"  falhas do extrator: {t['falhas']} | tempo médio {t['tempo_medio_s']}s, "
          f"máximo {t['tempo_maximo_s']}s\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m triagem.avaliar")
    parser.add_argument("--alvo", action="append", required=True,
                        help="'mock' ou 'ollama:<modelo>'; pode repetir")
    parser.add_argument("--teste", action="store_true",
                        help="usa a partição de teste (só uma vez por versão do prompt)")
    parser.add_argument("--forcar", action="store_true", help="ignora o registro de uso da partição de teste")
    parser.add_argument("--detalhe", action="store_true", help="mostra os erros por caso")
    parser.add_argument("--saida", type=Path, help="grava o resultado completo em JSON")
    args = parser.parse_args(argv)
    configurar_io()
    logging.getLogger("httpx").setLevel(logging.WARNING)

    particao = "teste" if args.teste else "desenvolvimento"
    casos = [c for c in json.loads(GABARITO.read_text(encoding="utf-8"))["casos"]
             if c["particao"] == particao]
    prompt = hash_do_prompt()
    usados = json.loads(REGISTRO_TESTE.read_text(encoding="utf-8")) if REGISTRO_TESTE.exists() else {}
    if args.teste and not args.forcar:
        repetidos = [a for a in args.alvo if a.startswith("ollama") and f"{a}@{prompt}" in usados]
        if repetidos:
            print(f"A partição de teste já foi usada com este prompt ({prompt}) para: "
                  f"{', '.join(repetidos)}. Mude o prompt ou use --forcar.", file=sys.stderr)
            return 2

    esperados = sum(len(c["sinais"]) for c in casos)
    print(f"partição: {particao} | {len(casos)} casos, {esperados} sinais esperados | prompt {prompt}\n")
    resultados = {}
    for alvo in args.alvo:
        resultados[alvo] = avaliar_alvo(alvo, casos, args.detalhe)
        imprimir(alvo, resultados[alvo], esperados, len(casos))
        if args.teste and alvo.startswith("ollama"):
            usados[f"{alvo}@{prompt}"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    if args.teste:
        REGISTRO_TESTE.write_text(json.dumps(usados, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if args.saida:
        args.saida.write_text(json.dumps(
            {"data": datetime.now(timezone.utc).isoformat(timespec="seconds"), "particao": particao,
             "prompt": prompt, "resultados": resultados}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
