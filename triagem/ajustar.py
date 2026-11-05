"""EXPERIMENTO: ajuste de pesos por regressão com coeficientes não negativos.

Lê os casos simulados de `salus_treinamento.db`, passa cada um pelo fluxo real
da entrevista e ajusta pesos (mínimos quadrados não negativos) para prever
`pontuacao_alvo`. O resultado é uma PROPOSTA para o revisor clínico: este
comando nunca altera `dados/regras.json`.

Cuidados, que o próprio relatório repete:
  - no script que gera o banco, `pontuacao_alvo` é um número sorteado, sem
    relação com as respostas; então nenhum modelo deve aprender nada de útil;
  - os casos não têm idade nem sexo: o experimento assume idade 40, sexo ausente;
  - perguntas compostas viram uma única resposta Sim/Não no banco, então
    várias partes são preenchidas por suposição;
  - a partição de teste (id_caso múltiplo de 5) nunca entra no ajuste.

Uso: python -m triagem.ajustar [--banco salus_treinamento.db] [--saida avaliacao/pesos_propostos.json]
"""

import argparse
import json
import sqlite3
import sys
from pathlib import Path

from triagem.cli import configurar_io
from triagem.entrevista import FichaInvalida, processar_ficha
from triagem.extrator_mock import MockExtrator
from triagem.regras import carregar_regras
from triagem.sinais import NomeSinal, Status

BANCO_PADRAO = Path(__file__).parent.parent / "salus_treinamento.db"
IDADE_ASSUMIDA = 40
SIM_NAO = {"Sim": True, "Não": False}


def _b(valor):
    return SIM_NAO.get(valor)


def _quando(valor, mapa):
    return mapa.get(valor)


def caso_para_ficha(linha: dict) -> dict:
    """Converte uma linha do banco para o formato da ficha (com suposições documentadas)."""
    pressao = linha.get("E03_pressao") or ""
    sistolica, _, diastolica = pressao.partition("x")
    aferido = {
        "temperatura": linha["E01_temperatura"], "saturacao": linha["E02_saturacao"],
        "pressao_sistolica": float(sistolica) if sistolica else None,
        "pressao_diastolica": float(diastolica) if diastolica else None,
        "frequencia_cardiaca": linha["E04_f_cardiaca"], "frequencia_respiratoria": linha["E05_f_respiratoria"],
        "glicemia": linha["E06_glicemia"], "glasgow": linha["E07_glasgow"],
    }
    dados = {"idade": IDADE_ASSUMIDA, "sexo_biologico": "ausente",
             **{k: v for k, v in aferido.items() if v is not None}}
    L = linha
    inicio = {"De repente": "de_repente", "Aos poucos": "aos_poucos"}.get(L["Q02"], "nao_sabe")
    medicamento = L["Q11"]
    resposta = {
        "Q01": L["relato_livre"], "Q02": {"inicio": inicio},
        "Q03": L["Q03"].lower(),
        "Q04": {"Aperto": "aperto", "Queimação": "queimacao", "Pontada": "pontada", "Cólica": "colica"}[L["Q04"]],
        "Q05": L["Q05"], "Q06": {"resposta": L["Q06"] != "Não"},
        "Q07": "nao_sabe" if L["Q07"] == "Não sabe" else L["Q07"],
        "Q08": {"Sim": True, "Não": False}.get(L["Q08"], "nao_sabe"),
        "Q09": _b(L["Q09"]),
        "Q10": ({"resposta": True, "tipos": ["medicamento"], "texto": "não especificado"}
                if _b(L["Q10"]) else {"resposta": False}),
        "Q11": ({"resposta": False} if medicamento == "Nenhum" else
                {"resposta": True, "anticoagulante": medicamento == "AAS",
                 "insulina": medicamento == "Insulina", "texto": medicamento}),
        "Q12": ({"resposta": False} if L["Q12"] == "Não" else
                {"resposta": True, "classes": ["antitermico"], "texto": L["Q12"]}),
        "Q13": [] if L["Q13"] == "Nenhuma" else [
            {"Hipertensão": "hipertensao", "Diabetes": "diabetes", "Asma": "pneumopatia"}[L["Q13"]]],
        "Q14": ["cirurgia"] if _b(L["Q14"]) else [],
        "Q15": ("nao_se_aplica" if L["Q15"] == "Não se aplica" else
                {"gravida_possivel": L["Q15"] == "Sim", "amamentando": False, "menstruacao_atrasada": False}),
        "C01": L["C01"], "C02": L["C02"], "C03": L["C03"], "C04": L["C04"],
    }
    for pid in ("T01", "T02", "T03", "A04", "A05", "R02", "R04", "R05"):
        if L[pid] is not None:
            resposta[pid] = _b(L[pid])
    if L["A01"] is not None:
        resposta["A01"] = {"local": "parte_inferior_direita", "mudou_de_lugar": False}
        resposta["A02"] = {"vomitando": _b(L["A02"]), "sangue_vomito_ou_fezes": False}
        resposta["A03"] = {"gases_e_evacuando": _b(L["A03"]), "diarreia": False}
    if L["R01"] is not None:
        resposta["R01"] = {"febre": True, "calafrios": False}
        resposta["R03"] = {"chiado": _b(L["R03"]), "tosse_com_sangue": False}
    return {"dados_atendente": dados, "respostas": {k: v for k, v in resposta.items() if v is not None}}


def vetor_de_atributos(saida) -> list[float]:
    """1 se o sinal conta como presente (a dor entra proporcional à nota, com piso)."""
    piso = carregar_regras()["pontuacao"]["dor_fracao_minima"]
    por_nome = {s.nome: s for s in saida.sinais}
    x = []
    for nome in NomeSinal:
        s = por_nome[nome]
        presente = s.status == Status.PRESENTE
        x.append(max(piso, (s.valor or 0) / 10) if presente and nome == NomeSinal.DOR else float(presente))
    return x


def carregar_casos(banco: Path):
    conexao = sqlite3.connect(banco)
    conexao.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conexao.execute("select * from casos_treinamento order by id_caso")]
    finally:
        conexao.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m triagem.ajustar", description=__doc__.split("\n\n")[0])
    parser.add_argument("--banco", type=Path, default=BANCO_PADRAO)
    parser.add_argument("--saida", type=Path, help="grava a proposta de pesos (nunca aplicada) em JSON")
    args = parser.parse_args(argv)
    configurar_io(silencioso=True)
    try:
        import numpy as np
        from scipy.optimize import nnls
        from scipy.stats import spearmanr
    except ImportError:
        print("Este experimento precisa de numpy e scipy (pip install -r requirements.txt).", file=sys.stderr)
        return 2

    casos = carregar_casos(args.banco)
    extrator = MockExtrator()
    ids, X, y, motor, invalidos = [], [], [], [], []
    for caso in casos:
        try:
            saida = processar_ficha(caso_para_ficha(caso), extrator)
        except FichaInvalida as e:
            invalidos.append((caso["id_caso"], e.erros[:2]))
            continue
        ids.append(caso["id_caso"])
        X.append(vetor_de_atributos(saida))
        y.append(caso["pontuacao_alvo"])
        motor.append(saida.classificacao.cor.nivel * 100 + saida.classificacao.pontuacao)
    X, y = np.array(X), np.array(y, dtype=float)
    teste = np.array([i % 5 == 0 for i in ids])
    print(f"{len(ids)} de {len(casos)} casos passaram pelo fluxo real "
          f"({len(invalidos)} rejeitados pela validação)")
    for pid, erros in invalidos[:5]:
        print(f"  caso {pid}: {erros}")

    coef, _ = nnls(X[~teste], y[~teste])

    def r2(mascara):
        previsto, real = X[mascara] @ coef, y[mascara]
        return 1 - ((real - previsto) ** 2).sum() / ((real - real.mean()) ** 2).sum()

    rho = spearmanr(motor, y).statistic
    print(f"\najuste com {int((~teste).sum())} casos | teste (id múltiplo de 5): {int(teste.sum())} casos")
    print(f"  R² no ajuste: {r2(~teste):.3f} | R² no teste: {r2(teste):.3f}")
    print(f"  correlação (Spearman) entre o motor de regras atual e a pontuacao_alvo: {rho:.3f}")
    nomes = [n.value for n in NomeSinal]
    print("\ncoeficientes propostos (>= 0):")
    for nome, c in sorted(zip(nomes, coef), key=lambda p: -p[1]):
        if c > 0:
            print(f"  {nome:30s} {c:6.2f}")
    print("\nATENÇÃO: a pontuacao_alvo do banco é sorteada no script de geração e não tem relação com as "
          "respostas. Um R² de teste próximo de zero (ou negativo) é o esperado e mostra que NADA foi "
          "aprendido. Estes coeficientes NÃO devem ser usados; servem só para testar o pipeline de ajuste.")
    if args.saida:
        args.saida.write_text(json.dumps(
            {"aplicado": False, "aviso": "proposta de experimento; alvo sorteado; não validada",
             "r2_ajuste": round(float(r2(~teste)), 4), "r2_teste": round(float(r2(teste)), 4),
             "pesos": {n: round(float(c), 3) for n, c in zip(nomes, coef) if c > 0}},
            ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
