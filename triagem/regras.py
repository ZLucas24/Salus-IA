"""Carrega e valida `dados/regras.json` (limites, pesos e regras de cor).

Todos os números clínicos moram nesse arquivo, para o revisor clínico poder
ler e corrigir sem tocar em lógica.
"""

import json
from functools import lru_cache
from pathlib import Path

from triagem.sinais import Cor, NomeSinal

CAMINHO_REGRAS = Path(__file__).parent / "dados" / "regras.json"


class RegrasInvalidas(ValueError):
    pass


def _validar_condicao(regra_id: str, cond) -> None:
    nome = cond if isinstance(cond, str) else (cond or {}).get("sinal")
    if nome not in {n.value for n in NomeSinal}:
        raise RegrasInvalidas(f"{regra_id}: sinal desconhecido {nome!r}")
    if isinstance(cond, dict):
        extras = set(cond) - {"sinal", "valor_min", "valor_max"}
        if extras:
            raise RegrasInvalidas(f"{regra_id}: chaves desconhecidas {sorted(extras)}")


@lru_cache(maxsize=1)
def carregar_regras() -> dict:
    with open(CAMINHO_REGRAS, encoding="utf-8-sig") as f:
        regras = json.load(f)
    pont = regras["pontuacao"]
    nomes = {n.value for n in NomeSinal}
    for nome, peso in pont["pesos"].items():
        if nome not in nomes:
            raise RegrasInvalidas(f"peso para sinal desconhecido: {nome!r}")
        if not isinstance(peso, (int, float)) or peso < 0:
            raise RegrasInvalidas(f"peso de {nome!r} deve ser um número >= 0")
    if pont["cor_base"] not in {c.value for c in Cor}:
        raise RegrasInvalidas(f"cor_base inválida: {pont['cor_base']!r}")
    ids = set()
    for r in pont["regras_cor"]:
        if r["id"] in ids:
            raise RegrasInvalidas(f"id de regra repetido: {r['id']}")
        ids.add(r["id"])
        if r["cor_minima"] not in {c.value for c in Cor}:
            raise RegrasInvalidas(f"{r['id']}: cor_minima inválida")
        for cond in r["todos"]:
            _validar_condicao(r["id"], cond)
    return regras
