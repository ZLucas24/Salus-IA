"""Regressões do debug geral: entradas malformadas, sessão ociosa, leitura do relato reaproveitada
entre a análise e a fila, e voz quando o modelo rápido não carrega. Nenhum teste usa rede."""

import http.client
import json
import sys
import threading
import types

import pytest

from helpers import ExtratorFalso
from triagem import voz as mod_voz
from triagem.afericoes import validar_dados_atendente
from triagem.extracao import Extracao
from triagem.fila import Fila, numero_valido, token_valido
from triagem.interface import servidor
from triagem.interface.paciente import criar_servidor_paciente
from triagem.interface.servidor import CacheDeLeitura, criar_servidor
from triagem.schema import Classificacao, Sinal
from triagem.sinais import Cor, NomeSinal, Origem, Status
from triagem.usuarios import SESSAO_OCIOSA_S, ErroUsuario, Usuarios
from triagem.voz import ErroVoz, TranscritorWhisper

FICHA = {"dados_atendente": {"idade": 40}, "respostas": {"Q01": "dor no peito em aperto", "Q08": False}}
GIGANTE = 10 ** 30


def _rodar(s):
    threading.Thread(target=s.serve_forever, daemon=True).start()
    return s


@pytest.fixture
def srv():
    s = _rodar(criar_servidor(0, Fila()))
    yield s
    s.shutdown()
    s.server_close()


def pedir(srv, metodo, caminho, corpo=None, bruto=None, cabecalhos=None, tipo="application/json"):
    con = http.client.HTTPConnection("127.0.0.1", srv.server_address[1], timeout=20)
    dados = bruto if bruto is not None else (None if corpo is None else json.dumps(corpo).encode())
    cab = {**({"Content-Type": tipo} if dados is not None else {}), **(cabecalhos or {})}
    con.request(metodo, caminho, body=dados, headers=cab)
    r = con.getresponse()
    return r.status, dict(r.getheaders()), r.read()


# --- números e códigos ------------------------------------------------------------------------

@pytest.mark.parametrize("n, ok", [(1, True), (2 ** 31 - 1, True), (0, False), (-1, False), (2 ** 31, False),
                                   (GIGANTE, False), (True, False), (1.0, False), ("1", False), (None, False)])
def test_numero_de_atendimento_valido(n, ok):
    assert numero_valido(n) is ok


def test_numero_gigante_nao_derruba_a_fila():
    fila = Fila()
    fila.entrar(Classificacao(cor=Cor.VERDE))
    for n in (GIGANTE, -GIGANTE, 0):
        assert not fila.chamar(n) and not fila.concluir(n) and not fila.devolver(n)
        assert not fila.marcar_aviso_visto(n) and fila.ficha(n) is None and fila.historico(n) == []
        assert fila.reclassificar(n, Classificacao(cor=Cor.VERMELHO), {}, "mock")["motivo"] == "nao_encontrado"


@pytest.mark.parametrize("rota", ["/api/fila/chamar", "/api/fila/concluir", "/api/fila/devolver",
                                  "/api/fila/aviso-visto", "/api/fila/ficha", "/api/fila/qr"])
def test_numero_gigante_pela_api_e_404_e_nao_erro_interno(srv, rota):
    assert pedir(srv, "POST", rota, {"numero": GIGANTE})[0] == 404
    assert pedir(srv, "POST", "/api/fila/reclassificar", {"numero": GIGANTE, "ficha": FICHA})[0] == 404


@pytest.mark.parametrize("token", ["A" * 24 + "\n", "A" * 19, "A" * 65, "A" * 23 + " ", 24, None])
def test_codigo_do_paciente_com_sobra_e_recusado(token):
    assert token_valido(token) is False and Fila().status_paciente(token) is None


def test_codigo_do_paciente_valido():
    assert token_valido("A" * 20) and token_valido("a-B_9" * 5)


# --- corpo e métodos estranhos ---------------------------------------------------------------------

@pytest.mark.parametrize("forma", ["listas", "objetos"])
def test_json_aninhado_demais_e_400_com_resposta(srv, forma):
    bruto = b"[" * 100_000 + b"]" * 100_000 if forma == "listas" else b'{"a":' * 50_000 + b"1" + b"}" * 50_000
    status, _, corpo = pedir(srv, "POST", "/api/triagem", bruto=bruto)
    assert status == 400 and "erros" in json.loads(corpo)


@pytest.mark.parametrize("metodo", ["PUT", "DELETE", "PATCH", "OPTIONS"])
def test_metodo_nao_usado_e_405_com_os_cabecalhos_de_seguranca(srv, metodo):
    status, cab, corpo = pedir(srv, metodo, "/api/fila", {"numero": 1})
    assert status == 405 and json.loads(corpo)["erros"] and cab["X-Content-Type-Options"] == "nosniff"
    assert "default-src 'none'" in cab["Content-Security-Policy"]


def test_head_responde_sem_corpo(srv):
    status, _, corpo = pedir(srv, "HEAD", "/")
    assert status == 405 and corpo == b""


def test_pagina_do_paciente_responde_405_mesmo_com_corpo_nao_esperado():
    pac = _rodar(criar_servidor_paciente(Fila(), "127.0.0.1", 0))
    try:
        for metodo, caminho in (("POST", "/qualquer"), ("PUT", "/p/" + "A" * 24), ("PATCH", "/"), ("OPTIONS", "/")):
            status, cab, _ = pedir(pac, metodo, caminho, bruto=b"motivo=dor" * 50,
                                   tipo="application/x-www-form-urlencoded")
            assert status == 405 and cab["X-Content-Type-Options"] == "nosniff", (metodo, caminho)
    finally:
        pac.shutdown()
        pac.server_close()


@pytest.mark.parametrize("nome", ["app.js\n", "app.js ", "../app.js", "APP.JS", "app.py", ""])
def test_arquivo_estatico_com_nome_estranho(srv, nome):
    assert servidor.NOME_ARQUIVO.fullmatch(nome) is None or not (servidor.PASTA_ESTATICA / nome).is_file() \
        or nome.endswith(".py")


# --- cadastro: número é número ---------------------------------------------------------------------

@pytest.mark.parametrize("dados", [{"idade": True}, {"idade": "40"}, {"idade": [40]}, {"idade": {"v": 40}},
                                   {"idade": 40, "temperatura": "37"}, {"idade": 40, "temperatura": True},
                                   {"idade": 40, "glasgow": "15"}, {"idade": 40, "saturacao": False}])
def test_cadastro_recusa_o_que_nao_e_numero(dados):
    validado, erros = validar_dados_atendente(dados)
    assert validado is None and erros and "deve ser um número" in erros[0]


def test_cadastro_aceita_numeros_de_verdade():
    dados, erros = validar_dados_atendente({"idade": 40.0, "temperatura": 37, "glasgow": 15.0, "saturacao": None})
    assert erros == [] and dados.idade == 40 and dados.temperatura == 37.0 and dados.glasgow == 15


@pytest.mark.parametrize("dados, trecho", [
    ({"idade": 40.5}, "inteiro"), ({"idade": 131}, "no máximo 130"), ({"idade": -1}, "no mínimo 0"),
    ({"idade": 40, "sexo_biologico": "FEMININO"}, "deve ser um de"), ({"idade": 40, "nome": "x"}, "desconhecido"),
    ({}, "obrigatório"),
])
def test_erros_do_cadastro_saem_em_portugues(dados, trecho):
    _, erros = validar_dados_atendente(dados)
    assert trecho in erros[0] and "Input should" not in " ".join(erros) and "Field required" not in " ".join(erros)


def test_idade_booleana_pela_api_e_ficha_invalida(srv):
    status, _, corpo = pedir(srv, "POST", "/api/triagem", {"ficha": {"dados_atendente": {"idade": True}, "respostas": {}}})
    assert status == 422 and "idade" in json.loads(corpo)["erros"][0]


# --- contas e sessão ociosa ------------------------------------------------------------------------

class Relogio:
    def __init__(self):
        self.t = 1_800_000_000.0

    def __call__(self):
        return self.t


@pytest.fixture
def contas():
    relogio = Relogio()
    u = Usuarios(":memory:", relogio=relogio)
    u.criar("ana", "Ana Souza", "senha-segura")
    yield u, relogio
    u.fechar()


def test_trocar_senha_e_desativar_aceitam_o_login_como_foi_digitado(contas):
    u, _ = contas
    u.trocar_senha(" ANA ", "outra-senha-boa")
    assert u.entrar("ana", "outra-senha-boa") is not None and u.entrar("ana", "senha-segura") is None
    assert u.desativar("Ana") is True and u.entrar("ana", "outra-senha-boa") is None
    with pytest.raises(ErroUsuario):
        u.trocar_senha("ninguem", "outra-senha-boa")


@pytest.mark.parametrize("login", ["ana\n", "ana maria", "an", "a" * 33, "ána", None, 5])
def test_login_fora_do_formato_nao_cria_conta(contas, login):
    u, _ = contas
    if login == "ana\n":  # a quebra de linha some na limpeza e o login já existe
        with pytest.raises(ErroUsuario):
            u.criar(login, "Outra", "senha-segura")
        return
    with pytest.raises(ErroUsuario):
        u.criar(login, "Nome", "senha-segura")


def test_consulta_automatica_nao_renova_a_sessao(contas):
    u, relogio = contas
    s = u.entrar("ana", "senha-segura")
    for _ in range(10):  # a página consulta a fila sozinha, mas ninguém mexe
        relogio.t += SESSAO_OCIOSA_S / 8
        if u.sessao(s, renovar=False) is None:
            break
    assert u.sessao(s) is None  # expirou por inatividade, apesar das consultas
    s = u.entrar("ana", "senha-segura")
    for _ in range(10):  # com uso de verdade, continua valendo
        relogio.t += SESSAO_OCIOSA_S / 8
        assert u.sessao(s) is not None


def test_a_fila_que_se_atualiza_sozinha_nao_segura_o_login(contas):
    u, relogio = contas
    s = _rodar(criar_servidor(0, Fila(), usuarios=u))
    try:
        cookie = {"Cookie": f"salus_sessao={u.entrar('ana', 'senha-segura')}"}
        automatico = {**cookie, "X-Salus-Automatico": "1"}
        for _ in range(7):
            relogio.t += SESSAO_OCIOSA_S / 8
            assert pedir(s, "GET", "/api/fila", cabecalhos=automatico)[0] == 200
        relogio.t += SESSAO_OCIOSA_S / 4
        assert pedir(s, "GET", "/api/fila", cabecalhos=automatico)[0] == 401  # caiu por inatividade
        cookie = {"Cookie": f"salus_sessao={u.entrar('ana', 'senha-segura')}"}
        for _ in range(12):  # quando o enfermeiro usa a tela, a sessão se renova
            relogio.t += SESSAO_OCIOSA_S / 8
            assert pedir(s, "GET", "/api/fila", cabecalhos=cookie)[0] == 200
    finally:
        s.shutdown()
        s.server_close()


def test_a_pagina_marca_a_consulta_automatica():
    js = (servidor.PASTA_ESTATICA / "app.js").read_text(encoding="utf-8")
    assert "carregarFila(true)" in js and f"'{servidor.CABECALHO_AUTOMATICO}': '1'" in js


# --- leitura do relato reaproveitada entre a análise e a fila ----------------------------------------

def _extracao():
    return Extracao(queixa_principal="dor no peito", sinais=[Sinal(
        nome=NomeSinal.DOR_EM_APERTO, status=Status.PRESENTE, trecho="aperto", origem=Origem.EXTRAIDO_DO_RELATO)])


def test_cache_devolve_copia_expira_e_tem_limite():
    relogio = Relogio()
    cache = CacheDeLeitura(validade_s=60, maximo=2, relogio=relogio)
    assert cache.obter("m", "relato") is None
    cache.guardar("m", "relato", _extracao())
    lida = cache.obter("m", "relato")
    lida.sinais.clear()  # mexer na cópia não estraga o que está guardado
    assert len(cache.obter("m", "relato").sinais) == 1
    assert cache.obter("outro-modelo", "relato") is None and cache.obter("m", "outro relato") is None
    relogio.t += 61
    assert cache.obter("m", "relato") is None
    for i in range(3):
        relogio.t += 1
        cache.guardar("m", f"r{i}", _extracao())
    assert cache.obter("m", "r0") is None and cache.obter("m", "r1") and cache.obter("m", "r2")
    assert all("relato" not in str(chave) and "r1" not in chave for chave in cache._itens)  # a chave é um resumo


def test_analise_e_fila_usam_a_mesma_leitura_do_modelo(srv, monkeypatch):
    falso = ExtratorFalso(_extracao())
    falso.nome = "ollama:falso"
    monkeypatch.setattr(servidor, "criar_extrator", lambda nome: falso)
    servidor.CACHE_DE_LEITURA.limpar()
    try:
        _, _, corpo = pedir(srv, "POST", "/api/triagem", {"ficha": FICHA, "extrator": "ollama"})
        cor_na_tela = json.loads(corpo)["saida"]["classificacao"]["cor"]
        assert pedir(srv, "POST", "/api/fila", {"ficha": FICHA, "extrator": "ollama"})[0] == 200
        assert len(falso.chamadas) == 1  # o modelo leu o relato uma vez só
        assert json.loads(pedir(srv, "GET", "/api/fila")[2])["pacientes"][0]["cor"] == cor_na_tela
        outra = {"dados_atendente": {"idade": 40}, "respostas": {"Q01": "outro relato, com febre"}}
        pedir(srv, "POST", "/api/triagem", {"ficha": outra, "extrator": "ollama"})
        assert len(falso.chamadas) == 2  # relato diferente: lê de novo
    finally:
        servidor.CACHE_DE_LEITURA.limpar()


def test_leitura_que_falhou_nao_fica_guardada(srv, monkeypatch):
    falso = ExtratorFalso(erro=RuntimeError("modelo fora do ar"))
    falso.nome = "ollama:falso"
    monkeypatch.setattr(servidor, "criar_extrator", lambda nome: falso)
    servidor.CACHE_DE_LEITURA.limpar()
    for _ in range(2):
        _, _, corpo = pedir(srv, "POST", "/api/triagem", {"ficha": FICHA, "extrator": "ollama"})
        assert "extracao_falhou" in [a["codigo"] for a in json.loads(corpo)["saida"]["alertas"]]
    assert len(falso.chamadas) == 2  # tentou de novo em vez de repetir a falha


def test_leitura_por_palavras_chave_nao_usa_o_cache(srv):
    servidor.CACHE_DE_LEITURA.limpar()
    pedir(srv, "POST", "/api/triagem", {"ficha": FICHA})
    assert servidor.CACHE_DE_LEITURA._itens == {}


# --- voz: o modelo rápido pode não estar disponível -----------------------------------------------

class ModeloFalso:
    def __init__(self, nome):
        self.nome = nome

    def transcribe(self, amostras, **kw):
        return [types.SimpleNamespace(text=f" ouvi com {self.nome} ")], None


def _whisper_falso(monkeypatch, indisponiveis=()):
    carregados = []

    def WhisperModel(nome, **kw):
        if nome in indisponiveis:
            raise OSError("sem rede")
        carregados.append(nome)
        return ModeloFalso(nome)

    monkeypatch.setitem(sys.modules, "faster_whisper", types.SimpleNamespace(WhisperModel=WhisperModel))
    monkeypatch.setattr(mod_voz, "decodificar", lambda audio: [0.0])
    return carregados


def test_resposta_curta_usa_o_rapido_e_o_relato_usa_o_maior(monkeypatch):
    _whisper_falso(monkeypatch)
    t = TranscritorWhisper("small", "base")
    assert t.transcrever(b"x", curta=True) == "ouvi com base" and t.transcrever(b"x") == "ouvi com small"
    assert t.transcrever(b"x", curta=True, preciso=True) == "ouvi com small" and t.tem_reserva


def test_sem_o_modelo_rapido_a_voz_continua_com_o_principal(monkeypatch):
    carregados = _whisper_falso(monkeypatch, indisponiveis={"base"})
    t = TranscritorWhisper("small", "base")
    assert t.transcrever(b"x", curta=True) == "ouvi com small"  # caiu para o principal, sem erro
    assert t.tem_reserva is False and t.nome == "whisper:small" and carregados == ["small"]
    assert t.transcrever(b"x", curta=True) == "ouvi com small" and carregados == ["small"]  # não tenta de novo


def test_precarga_nao_falha_quando_so_o_rapido_esta_indisponivel(monkeypatch):
    _whisper_falso(monkeypatch, indisponiveis={"base"})
    t = TranscritorWhisper("small", "base")
    t.carregar()
    assert t.tem_reserva is False


def test_sem_nenhum_modelo_o_erro_e_claro(monkeypatch):
    _whisper_falso(monkeypatch, indisponiveis={"base", "small"})
    with pytest.raises(ErroVoz, match="não foi possível carregar o modelo de voz 'small'"):
        TranscritorWhisper("small", "base").transcrever(b"x", curta=True)
