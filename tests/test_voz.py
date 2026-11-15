"""Voz: interpretação da fala (código, sem IA) e a rota /api/voz com um transcritor falso."""

import http.client
import json
import threading

import pytest

from triagem.fila import Fila
from triagem.interface.servidor import criar_servidor
from triagem.questionario import perguntas_por_id
from triagem.voz import ErroVoz, Transcritor, interpretar_fala

P = perguntas_por_id()


def parte(pid, nome="resposta"):
    return next(x for x in P[pid]["partes"] if x["nome"] == nome)


def ouvir(pid, texto, nome="resposta"):
    e = interpretar_fala(parte(pid, nome), texto)
    return e.valor if e.entendido else None


# --- sim/não ----------------------------------------------------------------------------------

@pytest.mark.parametrize("texto, esperado", [
    ("Sim.", True), ("sim, tem", True), ("Tem falta de ar", True), ("positivo", True),
    ("Não.", False), ("não tem", False), ("nunca desmaiou", False), ("Negativo", False),
    ("sem falta de ar", False), ("NÃO", False),
])
def test_sim_nao(texto, esperado):
    assert ouvir("Q09", texto) is esperado


@pytest.mark.parametrize("texto", ["não sei", "Ele não sabe.", "acho que não", "acho que sim", "talvez",
                                   "mais ou menos", "sei lá", "não tem certeza", "não lembra"])
def test_duvida_vira_nao_sabe_e_nunca_nao(texto):
    assert ouvir("Q08", texto) == "nao_sabe"


@pytest.mark.parametrize("texto", ["não quer responder", "prefiro não responder", "recusou"])
def test_recusa(texto):
    assert ouvir("Q08", texto) == "recusou"


@pytest.mark.parametrize("texto", ["sim e não", "não, sim", "hmm", "o paciente está aqui", "", "...", "?!", "ele"])
def test_sim_nao_ambiguo_ou_vazio_nao_e_entendido(texto):
    e = interpretar_fala(parte("Q09"), texto)
    assert not e.entendido and e.valor is None and e.motivo


def test_nenhuma_frase_de_duvida_vira_negado():
    """Segurança: qualquer frase com dúvida, mesmo com "não", nunca vira False."""
    duvidas = ["não sei", "acho que não", "talvez não", "não tenho certeza", "não lembro se tem",
               "pode ser que não", "mais ou menos, não", "sei lá, acho que não"]
    for pid in ("Q08", "Q09", "T01", "A04", "R02"):
        for t in duvidas:
            assert ouvir(pid, t) is not False, (pid, t)


# --- números -------------------------------------------------------------------------------

@pytest.mark.parametrize("texto, esperado", [
    ("7", 7), ("nota 8", 8), ("oito", 8), ("zero", 0), ("dez", 10), ("é um 5", None),
    ("11", None), ("7,5", None), ("entre 6 e 7", None), ("não sei", "nao_sabe"),
])
def test_escala(texto, esperado):
    assert ouvir("Q05", texto) == esperado


def test_numero_com_virgula_e_por_extenso():
    assert ouvir("R01", "38,5", "maior_temperatura") == 38.5
    assert ouvir("R01", "trinta e oito e meio", "maior_temperatura") == 38.5
    assert ouvir("A02", "três vezes", "episodios") == 3
    assert ouvir("A02", "vinte e dois", "episodios") == 22


# --- opções ---------------------------------------------------------------------------------

@pytest.mark.parametrize("texto, esperado", [
    ("aperto", "aperto"), ("É uma queimação", "queimacao"), ("tipo uma fisgada", "pontada"),
    ("cólica", "colica"), ("aperto e queimação", None), ("não é aperto", None), ("azul", None),
])
def test_opcao(texto, esperado):
    assert ouvir("Q04", texto) == esperado


def test_opcao_com_negacao_no_sinonimo():
    assert ouvir("Q03", "não mudou") == "igual"  # o "não" faz parte do sinônimo
    assert ouvir("Q03", "não está piorando") is None
    assert ouvir("Q03", "está piorando") == "piorando"
    assert ouvir("Q02", "foi de repente", "inicio") == "de_repente"


@pytest.mark.parametrize("texto, esperado", [
    ("diabetes e pressão alta", ["diabetes", "hipertensao"]),
    ("tem asma", ["pneumopatia"]),
    ("nenhuma", []), ("não tem nenhuma doença", []),
    ("diabetes, não tem pressão alta", None),
    ("acho que diabetes", "nao_sabe"),
])
def test_multiplas(texto, esperado):
    assert ouvir("Q13", texto) == esperado


# --- número com unidade ---------------------------------------------------------------------

@pytest.mark.parametrize("texto, esperado", [
    ("2 horas", {"valor": 2, "unidade": "horas"}),
    ("três dias", {"valor": 3, "unidade": "dias"}),
    ("uma hora e meia", {"valor": 1.5, "unidade": "horas"}),
    ("meia hora", {"valor": 0.5, "unidade": "horas"}),
    ("uma semana", {"valor": 1, "unidade": "semanas"}),
    ("ontem", {"valor": 1, "unidade": "dias"}),
    ("2 horas e 3 dias", None), ("faz tempo", None),
])
def test_numero_unidade(texto, esperado):
    assert ouvir("Q02", texto, "duracao") == esperado


def test_unidade_nao_aceita_na_pergunta():
    assert ouvir("Q12", "3 semanas", "ha") is None  # Q12 só aceita minutos, horas e dias


# --- texto livre ----------------------------------------------------------------------------

def test_texto_livre_e_o_que_foi_dito_sem_marcador():
    relato = "Acho que comi algo estragado, estou com dor na barriga desde ontem."
    assert ouvir("Q01", relato) == relato  # "acho" no relato não vira "não sabe"


def test_valor_entendido_passa_na_validacao_do_questionario():
    from triagem.questionario import interpretar
    interpretar(P["Q05"], ouvir("Q05", "oito"))
    interpretar(P["Q13"], ouvir("Q13", "diabetes"))
    interpretar(P["Q02"], {"duracao": ouvir("Q02", "duas horas", "duracao"), "inicio": ouvir("Q02", "aos poucos", "inicio")})


# --- rota /api/voz --------------------------------------------------------------------------

class TranscritorFalso(Transcritor):
    nome = "falso"

    def __init__(self, texto="não", erro=None, preciso=None):
        self.texto, self.erro, self.recebidos, self.pedidos = texto, erro, [], []
        self.texto_preciso, self.tem_reserva = preciso, preciso is not None

    def transcrever(self, audio, curta=False, dica=None, preciso=False):
        self.recebidos.append(audio)
        self.pedidos.append({"curta": curta, "dica": dica, "preciso": preciso})
        if self.erro:
            raise self.erro
        return self.texto_preciso if preciso else self.texto


@pytest.fixture
def srv_voz():
    falso = TranscritorFalso()
    s = criar_servidor(0, Fila(), None, falso)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    yield s, falso
    s.shutdown()
    s.server_close()


def enviar(srv, caminho, corpo=b"RIFF....", tipo="audio/webm;codecs=opus", origem=None):
    porta = srv.server_address[1]
    con = http.client.HTTPConnection("127.0.0.1", porta, timeout=10)
    cab = {"Content-Type": tipo, "Content-Length": str(len(corpo))}
    if origem:
        cab["Origin"] = origem
    con.request("POST", caminho, body=corpo, headers=cab)
    r = con.getresponse()
    return r.status, json.loads(r.read() or b"{}")


def test_rota_transcreve_e_interpreta(srv_voz):
    s, falso = srv_voz
    status, r = enviar(s, "/api/voz?pergunta=Q09&parte=resposta")
    assert status == 200 and r["transcricao"] == "não" and r["valor"] is False and r["entendido"]
    assert falso.recebidos == [b"RIFF...."]
    assert falso.pedidos[0]["curta"] is True and "sim" in falso.pedidos[0]["dica"]  # resposta curta: modelo rápido
    falso.texto = "acho que sim"
    assert enviar(s, "/api/voz?pergunta=Q09")[1]["valor"] == "nao_sabe"


def test_rota_nao_preenche_o_que_nao_entendeu(srv_voz):
    s, falso = srv_voz
    falso.texto = "sim e não"
    status, r = enviar(s, "/api/voz?pergunta=Q09")
    assert status == 200 and r["entendido"] is False and r["valor"] is None and r["motivo"]


def test_relato_vai_pelo_modelo_preciso(srv_voz):
    s, falso = srv_voz
    falso.texto = "dor no peito há duas horas"
    assert enviar(s, "/api/voz?pergunta=Q01")[1]["valor"] == "dor no peito há duas horas"
    assert falso.pedidos[-1] == {"curta": False, "dica": None, "preciso": False}


def test_quando_o_rapido_nao_entende_tenta_o_preciso_uma_vez():
    falso = TranscritorFalso(texto="hmm", preciso="sete")
    s = criar_servidor(0, Fila(), None, falso)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    try:
        r = enviar(s, "/api/voz?pergunta=Q05")[1]
        assert r["entendido"] and r["valor"] == 7 and r["transcricao"] == "sete"
        assert [p["preciso"] for p in falso.pedidos] == [False, True]
        falso.pedidos.clear()
        falso.texto = "oito"  # entendeu de primeira: não gasta a segunda tentativa
        assert enviar(s, "/api/voz?pergunta=Q05")[1]["valor"] == 8 and len(falso.pedidos) == 1
        falso.texto, falso.texto_preciso = "hmm", "ahn"  # nenhum entendeu: devolve o que o rápido ouviu
        r = enviar(s, "/api/voz?pergunta=Q05")[1]
        assert r["entendido"] is False and r["transcricao"] == "hmm"
    finally:
        s.shutdown()
        s.server_close()


def test_dica_por_tipo_de_pergunta():
    from triagem.voz import dica_da_parte, forma_curta
    assert "10" in dica_da_parte(parte("Q05")) and forma_curta(parte("Q05"))
    assert "aperto" in dica_da_parte(parte("Q04"))
    assert dica_da_parte(parte("Q01")) is None and not forma_curta(parte("Q01"))


@pytest.mark.parametrize("texto, esperado", [
    ("Des.", 10), ("deis", 10), ("Treis", 3), ("sinco", 5), ("nota des", 10), ("des e sete", None),
])
def test_numero_escrito_do_jeito_que_o_modelo_ouve(texto, esperado):
    assert ouvir("Q05", texto) == esperado


@pytest.mark.parametrize("texto", ["Sin.", "É.", "com certeza", "é verdade"])
def test_sim_curto(texto):
    assert ouvir("Q09", texto) is True


@pytest.mark.parametrize("texto", ["nau", "num", "na", "n"])
def test_nao_aproximado_nunca_vira_negado(texto):
    assert ouvir("Q09", texto) is not False


@pytest.mark.parametrize("caminho", ["/api/voz?pergunta=Q99", "/api/voz?pergunta=Q02&parte=nada", "/api/voz"])
def test_rota_recusa_pergunta_ou_parte_desconhecida(srv_voz, caminho):
    assert enviar(srv_voz[0], caminho)[0] == 400


def test_rota_exige_audio_e_origem_local(srv_voz):
    s, _ = srv_voz
    assert enviar(s, "/api/voz?pergunta=Q09", tipo="application/json")[0] == 415
    assert enviar(s, "/api/voz?pergunta=Q09", origem="https://evil.example.com")[0] == 403


def test_rota_devolve_erro_de_transcricao(srv_voz):
    s, falso = srv_voz
    falso.erro = ErroVoz("áudio inválido")
    status, r = enviar(s, "/api/voz?pergunta=Q09")
    assert status == 422 and "áudio inválido" in r["erros"][0]


def test_sem_transcritor_a_voz_fica_desligada():
    s = criar_servidor(0, Fila(), None, None)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    try:
        assert enviar(s, "/api/voz?pergunta=Q09")[0] == 503
        con = http.client.HTTPConnection("127.0.0.1", s.server_address[1], timeout=10)
        con.request("GET", "/api/questionario")
        assert json.loads(con.getresponse().read())["voz"] is False
    finally:
        s.shutdown()
        s.server_close()
