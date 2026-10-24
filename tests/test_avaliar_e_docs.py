"""Avaliador (conta certa?), roteiro gerado e README em dia."""

import json

import pytest

from helpers import RAIZ, rodar
from triagem import avaliar, roteiro
from triagem.extracao import Extracao
from triagem.schema import Alergias, Duracao
from triagem.sinais import NomeSinal, Queixa, Status

from helpers import citado


def caso(**kw):
    return {"id": "x", "relato": "r", "sinais": {}, **kw}


def test_conta_acertos_omitidos_trocados_e_invencoes():
    ext = Extracao(sinais=[citado(NomeSinal.DOR), citado(NomeSinal.FEBRE_REFERIDA), citado(NomeSinal.CHIADO)])
    r = avaliar.avaliar_caso(ext, caso(sinais={"dor": "presente", "febre_referida": "negado",
                                              "dispneia": "presente"}))
    assert r["acertos"] == ["dor"]
    assert r["trocados"] == ["febre_referida: esperado negado, veio presente"]
    assert r["omitidos"] == ["dispneia=presente"]
    assert r["invencoes"] == ["chiado=presente"]
    assert r["subestimam"] == ["dispneia omitido"]  # omitir um sinal presente esconde risco


def test_negacao_perdida_conta_como_erro_que_subestima():
    ext = Extracao(sinais=[citado(NomeSinal.DISPNEIA, Status.NEGADO)])
    r = avaliar.avaliar_caso(ext, caso(sinais={"dispneia": "presente"}))
    assert r["subestimam"] == ["dispneia dado como negado"]


def test_falha_do_extrator_conta_como_omissao_de_tudo():
    r = avaliar.avaliar_caso(None, caso(sinais={"dor": "presente", "febre_referida": "negado"}))
    assert len(r["omitidos"]) == 2 and r["subestimam"] == ["dor omitido"]


def test_duracao_com_tolerancia_e_alergia_por_itens_e_queixa():
    ext = Extracao(duracao=Duracao(valor=24, unidade="horas"), queixas=[Queixa.DOR_TORACICA],
                   alergias=Alergias(status=Status.PRESENTE, itens=["Dipirona"]))
    r = avaliar.avaliar_caso(ext, caso(duracao=[1, "dias"], alergia=["dipirona"], queixas=["dor_toracica"]))
    assert r["duracao_ok"] and r["alergia_ok"] and r["queixa_ok"]
    errada = avaliar.avaliar_caso(Extracao(duracao=Duracao(valor=5, unidade="dias")), caso(duracao=[1, "dias"]))
    assert errada["duracao_ok"] is False
    assert avaliar.avaliar_caso(Extracao(duracao=Duracao(valor=1, unidade="dias")), caso())["duracao_inventada"]
    assert not avaliar.avaliar_caso(Extracao(alergias=Alergias(status=Status.PRESENTE, itens=["x"])), caso())["alergia_ok"]


def test_avaliar_mock_na_particao_de_desenvolvimento(tmp_path):
    destino = tmp_path / "resultado.json"
    r = rodar("triagem.avaliar", "--alvo", "mock", "--saida", destino)
    assert r.returncode == 0 and "precisão" in r.stdout.decode("utf-8")
    resultado = json.loads(destino.read_text(encoding="utf-8"))
    assert resultado["particao"] == "desenvolvimento" and "mock" in resultado["resultados"]
    assert resultado["resultados"]["mock"]["falhas"] == 0


def test_particao_de_teste_so_uma_vez_por_prompt(monkeypatch, tmp_path):
    monkeypatch.setattr(avaliar, "REGISTRO_TESTE", tmp_path / "usado.json")
    chave = f"ollama:modelo@{avaliar.hash_do_prompt()}"
    (tmp_path / "usado.json").write_text(json.dumps({chave: "2026-10-24T00:00:00+00:00"}), encoding="utf-8")
    assert avaliar.main(["--alvo", "ollama:modelo", "--teste"]) == 2  # recusado antes de chamar o modelo


def test_o_prompt_muda_o_hash():
    assert len(avaliar.hash_do_prompt()) == 12


# --- documentação gerada ------------------------------------------------------------------------

def test_roteiro_versionado_corresponde_ao_questionario():
    versionado = (RAIZ / "docs" / "roteiro_entrevista.md").read_text(encoding="utf-8")
    assert versionado == roteiro.gerar(), "rode: python -m triagem.roteiro"


def test_roteiro_cobre_todas_as_perguntas_e_o_marcador_nao_sabe():
    texto = roteiro.gerar()
    from triagem.questionario import perguntas_por_id

    assert all(f"#### {pid}" in texto for pid in perguntas_por_id())
    assert "nao_sabe" in texto and "recusou" in texto


@pytest.mark.parametrize("trecho", ["python -m triagem", "python -m triagem.relato", "python -m triagem.avaliar",
                                    "python -m triagem.roteiro", "todos os dados são simulados"])
def test_readme_documenta_os_comandos(trecho):
    texto = (RAIZ / "README.md").read_text(encoding="utf-8").lower()
    assert trecho.lower() in texto
