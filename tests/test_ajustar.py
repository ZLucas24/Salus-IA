"""Experimento de ajuste de pesos: converte o banco simulado e nunca altera as regras."""

import hashlib
import json

import pytest

from helpers import RAIZ
from triagem import ajustar
from triagem.entrevista import FichaInvalida, processar_ficha
from triagem.extrator_mock import MockExtrator
from triagem.schema import SaidaTriagem
from triagem.sinais import NomeSinal

pytest.importorskip("scipy")


def test_banco_tem_100_casos_e_quase_todos_viram_ficha_valida():
    casos = ajustar.carregar_casos(ajustar.BANCO_PADRAO)
    assert len(casos) == 100
    invalidos = []
    for caso in casos:
        try:
            saida = processar_ficha(ajustar.caso_para_ficha(caso), MockExtrator())
            SaidaTriagem.model_validate(saida.model_dump())
            assert len(ajustar.vetor_de_atributos(saida)) == len(NomeSinal)
        except FichaInvalida as e:
            invalidos.append((caso["id_caso"], e.erros))
    # os únicos rejeitados são casos com pressão sistólica menor que a diastólica (dado impossível)
    assert all("menor que a diast" in erros[0] for _, erros in invalidos)
    assert len(invalidos) <= 5


def test_experimento_roda_e_nao_altera_as_regras(tmp_path, capsys):
    regras = RAIZ / "triagem" / "dados" / "regras.json"
    antes = hashlib.sha256(regras.read_bytes()).hexdigest()
    saida = tmp_path / "pesos.json"
    assert ajustar.main(["--saida", str(saida)]) == 0
    texto = capsys.readouterr().out
    assert "R² no teste" in texto and "NADA foi aprendido" in texto
    proposta = json.loads(saida.read_text(encoding="utf-8"))
    assert proposta["aplicado"] is False and all(v >= 0 for v in proposta["pesos"].values())
    assert hashlib.sha256(regras.read_bytes()).hexdigest() == antes
