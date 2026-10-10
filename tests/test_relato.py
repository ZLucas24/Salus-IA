"""Testes do agente de relato; sem rede (o Ollama é substituído por um cliente falso)."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from triagem.extrator_ollama import ErroExtracao, OllamaExtrator
from triagem.sinais import NomeSinal, Origem, Status

RAIZ = Path(__file__).parent.parent


def rodar(*args):
    return subprocess.run([sys.executable, "-m", "triagem.relato", *args],
                          capture_output=True, cwd=RAIZ)


class ClienteFalso:
    def __init__(self, conteudo=None, erro=None):
        self.conteudo, self.erro, self.chamadas = conteudo, erro, []

    def chat(self, **kwargs):
        self.chamadas.append(kwargs)
        if self.erro:
            raise self.erro
        return {"message": {"content": self.conteudo}}


def test_comando_imprime_json_com_queixa_sinais_e_pontuacao_fixa():
    r = rodar("dor no peito há 2 horas")
    assert r.returncode == 0
    saida = json.loads(r.stdout.decode("utf-8"))  # stdout só tem o JSON
    assert "há" in r.stdout.decode("utf-8")  # acentos legíveis
    assert saida["queixa_principal"] == "dor no peito há 2 horas"
    assert saida["duracao"] == {"valor": 2.0, "unidade": "horas"}
    assert [(s["nome"], s["status"], s["origem"]) for s in saida["sinais"]] == [
        ("dor", "presente", "extraido_do_relato")]
    assert saida["pontuacao"] == 0 and saida["pontuacao_provisoria"] is True
    assert saida["extrator"] == "mock"


@pytest.mark.parametrize("relato", ["", "   ", "x" * 201])
def test_relato_vazio_ou_longo_falha_sem_stdout(relato):
    r = rodar(relato)
    assert r.returncode != 0
    assert r.stdout == b""
    assert r.stderr


def test_ollama_indisponivel_falha_com_mensagem_clara():
    r = rodar("dor no peito", "--extrator", "ollama")
    # sem servidor local o comando deve falhar limpo (ou funcionar, se houver um)
    if r.returncode != 0:
        assert r.stdout == b""
        assert b"modelo" in r.stderr


def test_ollama_extrator_converte_resposta_valida():
    cliente = ClienteFalso(json.dumps({
        "queixa_principal": "dor no peito",
        "duracao": {"valor": 2, "unidade": "horas"},
        "sinais": [{"nome": "dor", "status": "presente", "valor": None},
                   {"nome": "febre", "status": "negado"},
                   {"nome": "trauma", "status": "nao_mencionado"}],
    }))
    ext = OllamaExtrator(modelo="teste", cliente=cliente).extrair("dor no peito há 2 horas sem febre")
    assert ext.queixa_principal == "dor no peito"
    assert {s.nome: s.status for s in ext.sinais} == {
        NomeSinal.DOR: Status.PRESENTE, NomeSinal.FEBRE: Status.NEGADO}
    assert all(s.origem == Origem.EXTRAIDO_DO_RELATO for s in ext.sinais)
    chamada = cliente.chamadas[0]
    assert chamada["model"] == "teste"
    assert chamada["messages"][-1]["content"] == "dor no peito há 2 horas sem febre"


@pytest.mark.parametrize("conteudo", [
    "isso não é json",
    json.dumps({"sinais": [{"nome": "gravidade", "status": "presente"}]}),  # fora do vocabulário
])
def test_ollama_extrator_rejeita_resposta_fora_do_formato(conteudo):
    with pytest.raises(ErroExtracao):
        OllamaExtrator(cliente=ClienteFalso(conteudo)).extrair("dor")


def test_ollama_extrator_converte_falha_de_conexao():
    with pytest.raises(ErroExtracao):
        OllamaExtrator(cliente=ClienteFalso(erro=ConnectionError("sem servidor"))).extrair("dor")


def test_ollama_descarta_negado_inventado_quando_relato_nao_tem_negacao():
    cliente = ClienteFalso(json.dumps({
        "sinais": [{"nome": "dor", "status": "presente"},
                   {"nome": "febre", "status": "negado"}]}))
    ext = OllamaExtrator(cliente=cliente).extrair("dor no peito há 2 horas")
    assert {s.nome for s in ext.sinais} == {NomeSinal.DOR}


def test_ollama_mantem_negado_quando_relato_nega():
    cliente = ClienteFalso(json.dumps({"sinais": [{"nome": "febre", "status": "negado"}]}))
    ext = OllamaExtrator(cliente=cliente).extrair("tosse, não tenho febre")
    assert [(s.nome, s.status) for s in ext.sinais] == [(NomeSinal.FEBRE, Status.NEGADO)]
