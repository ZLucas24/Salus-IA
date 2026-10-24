"""Mantém questionário, regras, enums, prompt e gabarito em sincronia."""

import json

import pytest

from helpers import RAIZ
from triagem.avaliar import GABARITO
from triagem.extracao import EXTRATORES, Extracao
from triagem.extrator_mock import PALAVRAS
from triagem.extrator_ollama import EXEMPLOS, FAIXAS_VALOR, SINAIS_DO_RELATO, OllamaExtrator, _Resposta
from triagem.questionario import carregar_questionario, ids_de_sinais_do_questionario
from triagem.regras import RegrasInvalidas, carregar_regras
from triagem.sinais import SINAIS_MEDIDOS, NomeSinal
from triagem.texto import sem_acentos

TODOS = {n.value for n in NomeSinal}
MEDIDOS = {n.value for n in SINAIS_MEDIDOS}


def test_todo_sinal_de_pergunta_existe_no_enum_e_o_contrario():
    do_questionario = ids_de_sinais_do_questionario()
    assert do_questionario <= TODOS
    assert TODOS - MEDIDOS == do_questionario, "sinal no enum sem pergunta (ou o inverso)"


def test_sinais_medidos_nao_vem_de_perguntas():
    assert not (ids_de_sinais_do_questionario() & MEDIDOS)


def test_todo_sinal_tem_peso_explicito_e_nenhum_e_negativo():
    pesos = carregar_regras()["pontuacao"]["pesos"]
    assert set(pesos) == TODOS
    assert all(p >= 0 for p in pesos.values())


def test_regras_de_cor_so_citam_sinais_do_enum():
    for r in carregar_regras()["pontuacao"]["regras_cor"]:
        for cond in r["todos"]:
            assert (cond if isinstance(cond, str) else cond["sinal"]) in TODOS


def test_ids_do_questionario_sao_unicos_e_afericoes_cobrem_e01_a_e07():
    q = carregar_questionario()
    ids = [p["id"] for p in q["perguntas"]]
    assert len(ids) == len(set(ids))
    assert [a["id"] for a in q["afericoes"]] == [f"E0{i}" for i in range(1, 8)]


def test_regras_marcadas_como_nao_validadas():
    regras = carregar_regras()
    assert regras["validado"] is False
    assert "PROPOSTAS DA EQUIPE" in regras["aviso"]


def test_arquivo_de_regras_invalido_e_rejeitado(monkeypatch, tmp_path):
    ruim = json.loads((RAIZ / "triagem" / "dados" / "regras.json").read_text(encoding="utf-8"))
    ruim["pontuacao"]["pesos"]["dor"] = -1
    arquivo = tmp_path / "regras.json"
    arquivo.write_text(json.dumps(ruim), encoding="utf-8")
    monkeypatch.setattr("triagem.regras.CAMINHO_REGRAS", arquivo)
    carregar_regras.cache_clear()
    try:
        with pytest.raises(RegrasInvalidas):
            carregar_regras()
    finally:
        carregar_regras.cache_clear()


def test_palavras_do_mock_e_dicas_do_prompt_usam_so_sinais_extraiveis():
    assert set(p.value for p in PALAVRAS) <= TODOS - MEDIDOS
    assert set(SINAIS_DO_RELATO) <= TODOS - MEDIDOS
    assert set(FAIXAS_VALOR) <= TODOS


def test_exemplos_do_prompt_sao_validos_para_o_contrato():
    """Se um sinal for renomeado, os exemplos do prompt não podem ensinar o nome antigo."""
    for relato, resposta in EXEMPLOS:
        r = _Resposta.model_validate(resposta)
        extracao = OllamaExtrator._converter(relato, r)
        assert isinstance(extracao, Extracao)
        assert not extracao.avisos, (relato, extracao.avisos)


def _normalizar(texto):
    return " ".join(sem_acentos(texto).lower().split())


def test_exemplos_do_prompt_nao_vazam_para_o_gabarito():
    """CLAUDE.md: a partição de teste (e o gabarito) nunca entra no prompt."""
    relatos = [_normalizar(c["relato"]) for c in json.loads(GABARITO.read_text(encoding="utf-8"))["casos"]]
    for texto, _ in EXEMPLOS:
        assert _normalizar(texto) not in relatos


def test_gabarito_usa_so_nomes_validos_e_tem_as_duas_particoes():
    casos = json.loads(GABARITO.read_text(encoding="utf-8"))["casos"]
    assert {c["particao"] for c in casos} == {"desenvolvimento", "teste"}
    assert len({c["id"] for c in casos}) == len(casos)
    for c in casos:
        assert set(c["sinais"]) <= TODOS - MEDIDOS
        assert set(c["sinais"].values()) <= {"presente", "negado"}


def test_registro_de_extratores():
    assert set(EXTRATORES) == {"mock", "ollama"}
