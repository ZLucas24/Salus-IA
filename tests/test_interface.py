"""Servidor da interface: rotas, validação e defesas. Sobe em loopback numa porta livre."""

import http.client
import json
import threading

import pytest

from triagem.interface import servidor
from triagem.interface.servidor import PASTA_ESTATICA, criar_servidor

FICHA = {"dados_atendente": {"idade": 40}, "respostas": {"Q08": True}}


@pytest.fixture(scope="module")
def srv():
    s = criar_servidor(0)
    thread = threading.Thread(target=s.serve_forever, daemon=True)
    thread.start()
    yield s
    s.shutdown()
    s.server_close()


def chamar(srv, metodo, caminho, corpo=None, cabecalhos=None, host=None):
    porta = srv.server_address[1]
    con = http.client.HTTPConnection("127.0.0.1", porta, timeout=10)
    cab = {"Host": host or f"127.0.0.1:{porta}", **(cabecalhos or {})}
    con.putrequest(metodo, caminho, skip_host=True, skip_accept_encoding=True)
    dados = None if corpo is None else (corpo if isinstance(corpo, bytes) else json.dumps(corpo).encode())
    if dados is not None:
        cab.setdefault("Content-Type", "application/json")
        cab["Content-Length"] = str(len(dados))
    for k, v in cab.items():
        con.putheader(k, v)
    con.endheaders(dados)
    resp = con.getresponse()
    return resp.status, dict(resp.getheaders()), resp.read()


def post(srv, corpo, **kw):
    status, cab, dados = chamar(srv, "POST", "/api/triagem", corpo, **kw)
    return status, json.loads(dados)


def test_escuta_so_em_loopback(srv):
    assert srv.server_address[0] == "127.0.0.1"


def test_pagina_e_arquivos_estaticos(srv):
    status, cab, corpo = chamar(srv, "GET", "/")
    assert status == 200 and cab["Content-Type"].startswith("text/html") and b"SalUS.ia" in corpo
    for nome, tipo in [("app.js", "text/javascript"), ("estilo.css", "text/css")]:
        status, cab, _ = chamar(srv, "GET", f"/estatico/{nome}")
        assert status == 200 and cab["Content-Type"].startswith(tipo)


@pytest.mark.parametrize("caminho", ["/estatico/../servidor.py", "/estatico/%2e%2e/servidor.py", "/estatico/servidor.py",
                                     "/estatico/..%5cservidor.py", "/estatico/", "/nada", "/api/outra"])
def test_nada_fora_da_lista_e_servido(srv, caminho):
    assert chamar(srv, "GET", caminho)[0] == 404


def test_cabecalhos_de_seguranca(srv):
    _, cab, _ = chamar(srv, "GET", "/")
    assert "default-src 'none'" in cab["Content-Security-Policy"] and "frame-ancestors 'none'" in cab["Content-Security-Policy"]
    assert cab["X-Content-Type-Options"] == "nosniff" and cab["Cache-Control"] == "no-store"


def test_a_pagina_nao_carrega_nada_de_fora():
    html = (PASTA_ESTATICA / "index.html").read_text(encoding="utf-8")
    assert "http://" not in html.replace("http://www.w3.org", "") and "https://" not in html
    js = (PASTA_ESTATICA / "app.js").read_text(encoding="utf-8")
    for perigoso in (".innerHTML", ".outerHTML", "insertAdjacentHTML", "document.write", "eval(", "new Function"):
        assert perigoso not in js, perigoso  # só DOM seguro: texto do paciente nunca vira HTML


def test_api_questionario_e_exemplos(srv):
    status, _, corpo = chamar(srv, "GET", "/api/questionario")
    q = json.loads(corpo)
    assert status == 200 and len(q["perguntas"]) == 32 and q["regras"]["validado"] is False
    assert q["extratores"] == ["mock", "ollama"] and q["extrator_padrao"] == "mock"
    status, _, corpo = chamar(srv, "GET", "/api/exemplos")
    exemplos = json.loads(corpo)
    assert status == 200 and len(exemplos) >= 10
    assert {e["nome"] for e in exemplos if e["falha_proposital"]} >= {"ficha_09_sem_idade_falha"}


def test_triagem_devolve_a_saida_do_fluxo_real(srv):
    status, corpo = post(srv, {"ficha": FICHA})
    assert status == 200
    saida = corpo["saida"]
    assert saida["classificacao"]["cor"] == "laranja" and saida["extrator"] == "mock"
    assert saida["classificacao"]["provisoria"] is True


def test_ficha_invalida_devolve_422_com_a_pergunta(srv):
    status, corpo = post(srv, {"ficha": {"dados_atendente": {"idade": 40}, "respostas": {"Q05": 11}}})
    assert status == 422 and "Q05" in corpo["erros"][0]
    status, corpo = post(srv, {"ficha": {"respostas": {}}})
    assert status == 422 and "dados_atendente" in corpo["erros"][0]


def test_extrator_desconhecido_e_400(srv):
    assert post(srv, {"ficha": FICHA, "extrator": "inexistente"})[0] == 400


def test_ollama_fora_do_ar_nao_derruba_a_ficha(srv, monkeypatch):
    monkeypatch.setenv("OLLAMA_HOST", "http://127.0.0.1:9")
    ficha = {"dados_atendente": {"idade": 40}, "respostas": {"Q01": "dor no peito", "Q09": True}}
    status, corpo = post(srv, {"ficha": ficha, "extrator": "ollama"})
    assert status == 200
    assert "extracao_falhou" in [a["codigo"] for a in corpo["saida"]["alertas"]]


@pytest.mark.parametrize("corpo", [b"nao e json", b"[]", b'{"semficha": {}}', b"\xff\xfe"])
def test_corpo_malformado_e_400(srv, corpo):
    status, _, dados = chamar(srv, "POST", "/api/triagem", corpo)
    assert status == 400 and "erros" in json.loads(dados)


def test_ficha_que_nao_e_objeto_e_ficha_invalida(srv):
    status, corpo = post(srv, {"ficha": None})
    assert status == 422 and "objeto" in corpo["erros"][0]


def test_exige_json_e_tamanho_valido(srv):
    assert chamar(srv, "POST", "/api/triagem", b"{}", {"Content-Type": "text/plain"})[0] == 415
    assert chamar(srv, "POST", "/api/triagem", b"")[0] == 413
    grande = b'{"ficha": "' + b"a" * (servidor.LIMITE_CORPO + 10) + b'"}'
    try:
        assert chamar(srv, "POST", "/api/triagem", grande)[0] == 413
    except ConnectionError:
        pass  # o servidor recusa pelo tamanho e fecha sem ler o corpo; o Windows pode abortar o envio


def test_post_em_outra_rota_e_404(srv):
    assert chamar(srv, "POST", "/api/questionario", {})[0] == 404


@pytest.mark.parametrize("host", ["evil.example.com", "127.0.0.1:1", "localhost"])
def test_host_estranho_e_recusado_contra_dns_rebinding(srv, host):
    assert chamar(srv, "GET", "/api/questionario", host=host)[0] == 403
    assert chamar(srv, "POST", "/api/triagem", {"ficha": FICHA}, host=host)[0] == 403


def test_origem_de_outro_site_e_recusada_no_post(srv):
    porta = srv.server_address[1]
    assert chamar(srv, "POST", "/api/triagem", {"ficha": FICHA}, {"Origin": "https://evil.example.com"})[0] == 403
    assert chamar(srv, "POST", "/api/triagem", {"ficha": FICHA}, {"Origin": f"http://127.0.0.1:{porta}"})[0] == 200
    assert chamar(srv, "POST", "/api/triagem", {"ficha": FICHA}, {"Origin": f"http://localhost:{porta}"},
                  host=f"localhost:{porta}")[0] == 200


def test_erro_interno_nao_vaza_detalhes(srv, monkeypatch):
    def quebra(*a, **k):
        raise RuntimeError("segredo interno")

    monkeypatch.setattr(servidor, "calcular", quebra)
    status, corpo = post(srv, {"ficha": FICHA})
    assert status == 500 and "segredo" not in json.dumps(corpo)


def test_comando_recusa_porta_ocupada(srv):
    assert servidor.main(["--porta", str(srv.server_address[1])]) == 2
