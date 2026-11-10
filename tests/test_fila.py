"""Fila de atendimento, página do paciente (QR) e rotas da fila no servidor do enfermeiro."""

import http.client
import json
import random
import threading

import pytest

from helpers import RAIZ
from triagem.fila import FAIXAS, Fila, explicacoes, faixa, ordem_das_cores
from triagem.interface.paciente import criar_servidor_paciente
from triagem.interface.servidor import criar_servidor
from triagem.regras import RegrasInvalidas, carregar_regras
from triagem.schema import Classificacao, RegraAplicada
from triagem.sinais import Cor


class Relogio:
    def __init__(self):
        self.t = 1_000_000.0

    def __call__(self):
        return self.t


def cls(cor: str, pontuacao: int = 0, regras: tuple[str, ...] = ()) -> Classificacao:
    return Classificacao(cor=Cor(cor), pontuacao=pontuacao,
                         regras_aplicadas=[RegraAplicada(id=r, descricao=r, efeito="x") for r in regras])


@pytest.fixture
def relogio():
    return Relogio()


@pytest.fixture
def fila(relogio):
    f = Fila(":memory:", relogio=relogio)
    yield f
    f.fechar()


def ordem(fila):
    return [p["numero"] for p in fila.listar() if p["estado"] == "aguardando"]


# --- ordem da fila ---------------------------------------------------------------------

def test_ordem_e_cor_depois_pontuacao_depois_chegada(fila, relogio):
    a = fila.entrar(cls("verde", 10))["numero"]
    relogio.t += 60
    b = fila.entrar(cls("amarelo", 5))["numero"]
    relogio.t += 60
    c = fila.entrar(cls("amarelo", 40))["numero"]
    relogio.t += 60
    d = fila.entrar(cls("verde", 10))["numero"]  # empata com `a`, mas chegou depois
    assert ordem(fila) == [c, b, a, d]


def test_quem_chega_mais_grave_passa_na_frente(fila):
    tokens = [fila.entrar(cls("verde"))["token"] for _ in range(3)]
    assert fila.status_paciente(tokens[2])["faixa"] == faixa(2)
    grave = fila.entrar(cls("vermelho"))
    assert ordem(fila)[0] == grave["numero"]
    assert fila.status_paciente(grave["token"])["faixa"] == "Você é o próximo"
    assert fila.status_paciente(tokens[2])["faixa"] == faixa(3)


def test_ordem_aleatoria_sempre_respeita_a_cor(fila, relogio):
    rnd = random.Random(7)
    for _ in range(60):
        relogio.t += rnd.randint(0, 120)
        fila.entrar(cls(rnd.choice(list(Cor)).value, rnd.randint(0, 99)))
    linhas = [p for p in fila.listar() if p["estado"] == "aguardando"]
    chaves = [(-Cor(p["cor"]).nivel, -p["pontuacao"]) for p in linhas]
    assert chaves == sorted(chaves)
    assert [p["posicao"] for p in linhas] == list(range(1, 61))


# --- faixas -----------------------------------------------------------------------------

@pytest.mark.parametrize("a_frente, esperado", [
    (0, "Você é o próximo"), (1, "De 1 a 3"), (3, "De 1 a 3"), (4, "De 4 a 6"), (6, "De 4 a 6"),
    (7, "De 7 a 10"), (10, "De 7 a 10"), (11, "Mais de 10"), (500, "Mais de 10")])
def test_faixas(a_frente, esperado):
    assert faixa(a_frente).startswith(esperado)


def test_faixas_cobrem_tudo_sem_buraco():
    for (_, fim, _), (ini, _, _) in zip(FAIXAS, FAIXAS[1:]):
        assert ini == fim + 1
    with pytest.raises(ValueError):
        faixa(-1)


# --- o que o paciente vê ------------------------------------------------------------------

def test_paciente_ve_cor_motivo_faixa_e_nunca_a_pontuacao(fila):
    t = fila.entrar(cls("laranja", 73, ("RC-09",)))["token"]
    s = fila.status_paciente(t)
    assert s["cor"] == "laranja" and s["nome_cor"].startswith("Laranja")
    assert s["motivos"] == ["Dor em aperto que se espalha para outra parte do corpo"]
    assert s["faixa"] == "Você é o próximo" and s["tempo_alvo_min"] == 10
    assert "pontuacao" not in s and "73" not in json.dumps(s)
    assert "posicao" not in s and "token" not in s


def test_paciente_nao_ve_dados_de_outros(fila):
    fila.entrar(cls("vermelho", 90, ("RC-11",)))
    t = fila.entrar(cls("verde"))["token"]
    texto = json.dumps(fila.status_paciente(t), ensure_ascii=False)
    assert "Tosse com sangue" not in texto


@pytest.mark.parametrize("token", ["", "curto", "a" * 65, "../../etc/passwd", "x" * 30 + "<", None, 123])
def test_codigo_invalido_nao_revela_nada(fila, token):
    fila.entrar(cls("verde"))
    assert fila.status_paciente(token) is None
    assert fila.status_paciente("A" * 32) is None  # formato certo, mas não existe


def test_codigo_deixa_de_valer_depois_do_atendimento(fila):
    e = fila.entrar(cls("amarelo"))
    assert fila.chamar(e["numero"])
    s = fila.status_paciente(e["token"])
    assert s["estado"] == "chamado" and s["faixa"] is None
    assert fila.concluir(e["numero"])
    assert fila.status_paciente(e["token"]) is None
    assert not fila.concluir(e["numero"]) and not fila.chamar(e["numero"])


@pytest.mark.parametrize("numero", [999, True, "1", None, 1.0])
def test_chamar_ou_concluir_numero_invalido(fila, numero):
    fila.entrar(cls("verde"))
    assert not fila.chamar(numero) and not fila.concluir(numero)


def test_tokens_sao_unicos_e_longos(fila):
    tokens = {fila.entrar(cls("verde"))["token"] for _ in range(200)}
    assert len(tokens) == 200 and all(len(t) >= 32 for t in tokens)


def test_fila_sobrevive_a_reinicio(tmp_path, relogio):
    caminho = str(tmp_path / "fila.db")
    f = Fila(caminho, relogio=relogio)
    t = f.entrar(cls("amarelo", 20, ("RC-15",)))["token"]
    f.fechar()
    f = Fila(caminho, relogio=relogio)
    assert f.status_paciente(t)["motivos"] == ["Falta de ar"]
    f.fechar()


# --- explicações -----------------------------------------------------------------------

def test_explicacoes():
    regras = carregar_regras()
    assert explicacoes(cls("verde")) == [regras["fila"]["explicacao_sem_regra"]]
    assert explicacoes(cls("amarelo", 0, ("PROMOCAO",))) == [regras["fila"]["explicacao_promocao"]]
    assert explicacoes(cls("laranja", 0, ("RC-15", "PESO-dispneia", "RC-15", "RC-07"))) == [
        "Falta de ar", "Falta de ar que atrapalha a fala"]


def test_toda_regra_de_cor_tem_explicacao_e_toda_cor_tem_tempo():
    regras = carregar_regras()
    assert all(r["explicacao_paciente"].strip() for r in regras["pontuacao"]["regras_cor"])
    assert [c["cor"] for c in ordem_das_cores()] == ["vermelho", "laranja", "amarelo", "verde", "azul"]
    assert "NÃO validados" in regras["fila"]["nota"]


@pytest.mark.parametrize("estragar", [
    lambda r: r["pontuacao"]["regras_cor"][0].pop("explicacao_paciente"),
    lambda r: r["fila"]["tempos_alvo_minutos"].pop("azul"),
    lambda r: r["fila"]["tempos_alvo_minutos"].__setitem__("verde", -5),
])
def test_regras_sem_explicacao_ou_tempo_sao_rejeitadas(monkeypatch, tmp_path, estragar):
    ruim = json.loads((RAIZ / "triagem" / "dados" / "regras.json").read_text(encoding="utf-8"))
    estragar(ruim)
    arquivo = tmp_path / "regras.json"
    arquivo.write_text(json.dumps(ruim), encoding="utf-8")
    monkeypatch.setattr("triagem.regras.CAMINHO_REGRAS", arquivo)
    carregar_regras.cache_clear()
    try:
        with pytest.raises(RegrasInvalidas):
            carregar_regras()
    finally:
        carregar_regras.cache_clear()


# --- servidores ----------------------------------------------------------------------------

def _rodar(s):
    threading.Thread(target=s.serve_forever, daemon=True).start()
    return s


@pytest.fixture
def servidores():
    f = Fila(":memory:")
    pac = _rodar(criar_servidor_paciente(f, "127.0.0.1", 0))
    base = f"http://127.0.0.1:{pac.server_address[1]}"
    enf = _rodar(criar_servidor(0, f, base))
    yield enf, pac, f
    for s in (enf, pac):
        s.shutdown()
        s.server_close()
    f.fechar()


def chamar(srv, metodo, caminho, corpo=None):
    porta = srv.server_address[1]
    con = http.client.HTTPConnection("127.0.0.1", porta, timeout=10)
    cab = {}
    dados = None
    if corpo is not None:
        dados = json.dumps(corpo).encode()
        cab = {"Content-Type": "application/json", "Content-Length": str(len(dados))}
    con.request(metodo, caminho, body=dados, headers=cab)
    r = con.getresponse()
    return r.status, r.read()


FICHA_GRAVE = {"dados_atendente": {"idade": 50}, "respostas": {"Q04": "aperto", "Q06": {"resposta": True, "para_onde": "braço"}}}


def test_colocar_na_fila_devolve_numero_qr_e_link(servidores):
    enf, pac, _ = servidores
    status, corpo = chamar(enf, "POST", "/api/fila", {"ficha": FICHA_GRAVE})
    r = json.loads(corpo)
    assert status == 200 and r["numero"] == 1
    assert r["url"].startswith(f"http://127.0.0.1:{pac.server_address[1]}/p/")
    assert r["qr"].startswith("data:image/svg+xml")
    status, corpo = chamar(enf, "GET", "/api/fila")
    lista = json.loads(corpo)["pacientes"]
    assert lista[0]["cor"] == "laranja" and "token" not in lista[0]


def test_a_cor_e_calculada_no_servidor_nao_vem_do_navegador(servidores):
    enf, _, _ = servidores
    ficha = {"dados_atendente": {"idade": 30}, "respostas": {}}
    chamar(enf, "POST", "/api/fila", {"ficha": ficha, "classificacao": {"cor": "vermelho"}, "cor": "vermelho"})
    lista = json.loads(chamar(enf, "GET", "/api/fila")[1])["pacientes"]
    assert lista[0]["cor"] == "verde"


def test_ficha_invalida_nao_entra_na_fila(servidores):
    enf, _, f = servidores
    status, corpo = chamar(enf, "POST", "/api/fila", {"ficha": {"respostas": {}}})
    assert status == 422 and f.listar() == []


def test_chamar_concluir_e_qr_de_novo_pela_api(servidores):
    enf, pac, _ = servidores
    r = json.loads(chamar(enf, "POST", "/api/fila", {"ficha": FICHA_GRAVE})[1])
    status, corpo = chamar(enf, "POST", "/api/fila/qr", {"numero": r["numero"]})
    assert status == 200 and json.loads(corpo)["url"] == r["url"]
    assert chamar(enf, "POST", "/api/fila/chamar", {"numero": r["numero"]})[0] == 200
    assert chamar(enf, "POST", "/api/fila/chamar", {"numero": r["numero"]})[0] == 404
    caminho = r["url"].split(str(pac.server_address[1]), 1)[1]
    assert b"Voc\xc3\xaa foi chamado" in chamar(pac, "GET", caminho)[1]
    assert chamar(enf, "POST", "/api/fila/concluir", {"numero": r["numero"]})[0] == 200
    assert chamar(pac, "GET", caminho)[0] == 404
    assert chamar(enf, "POST", "/api/fila/qr", {"numero": r["numero"]})[0] == 404


def test_pagina_do_paciente(servidores):
    enf, pac, _ = servidores
    r = json.loads(chamar(enf, "POST", "/api/fila", {"ficha": FICHA_GRAVE})[1])
    caminho = r["url"].split(str(pac.server_address[1]), 1)[1]
    status, html = chamar(pac, "GET", caminho)
    texto = html.decode("utf-8")
    assert status == 200 and ">001<" in texto
    assert "Laranja — muito urgente" in texto and "Dor em aperto que se espalha" in texto
    assert "Você é o próximo" in texto and "até 10 min" in texto
    assert "pontua" not in texto.lower() and "<script" not in texto.lower()
    assert 'http-equiv="refresh"' in texto
    assert chamar(pac, "GET", "/paciente.css")[0] == 200


@pytest.mark.parametrize("caminho", ["/", "/api/fila", "/api/triagem", "/api/questionario", "/api/exemplos",
                                     "/estatico/app.js", "/p/", "/p/naoexiste", "/p/../api/fila"])
def test_servidor_do_paciente_nao_expoe_nada_alem_do_status(servidores, caminho):
    _, pac, _ = servidores
    status, corpo = chamar(pac, "GET", caminho)
    assert status == 404 and b"C\xc3\xb3digo n\xc3\xa3o encontrado" in corpo


@pytest.mark.parametrize("metodo", ["POST", "PUT", "DELETE"])
def test_servidor_do_paciente_so_le(servidores, metodo):
    _, pac, _ = servidores
    assert chamar(pac, metodo, "/api/fila", {"ficha": FICHA_GRAVE})[0] == 405


def test_sem_pagina_do_paciente_a_fila_funciona_sem_qr():
    f = Fila(":memory:")
    enf = _rodar(criar_servidor(0, f, None))
    try:
        status, corpo = chamar(enf, "POST", "/api/fila", {"ficha": FICHA_GRAVE})
        r = json.loads(corpo)
        assert status == 200 and r["url"] is None and r["qr"] is None
    finally:
        enf.shutdown()
        enf.server_close()
        f.fechar()
