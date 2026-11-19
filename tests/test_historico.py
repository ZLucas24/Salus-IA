"""Histórico do paciente: fonte simulada, cruzamento por regra e rotas da interface."""

import copy
import http.client
import json
import threading
from datetime import date

import pytest

from triagem import historico as modulo
from triagem.historico import FonteHistorico, HistoricoSimulado, consultar, cruzar, prontuario_valido
from triagem.interface.servidor import calcular, criar_servidor
from triagem.regras import RegrasInvalidas, carregar_regras, validar_regras

HOJE = date(2026, 11, 16)
FICHA_PEITO = {"dados_atendente": {"idade": 58},
               "respostas": {"Q01": "Estou com dor no peito em aperto desde cedo", "Q10": {"resposta": False}}}


def saida_de(ficha):
    status, corpo = calcular(ficha, "mock")
    assert status == 200
    return corpo["saida"]


def codigos(padroes):
    return [p["codigo"] for p in padroes]


@pytest.fixture
def fonte():
    return HistoricoSimulado(hoje=lambda: HOJE)


# --- fonte ----------------------------------------------------------------------------------

@pytest.mark.parametrize("valor, ok", [("100001", True), ("1234", True), ("123", False), ("1" * 13, False),
                                       ("12a45", False), ("", False), (100001, False), (None, False),
                                       ("1000 01", False), ("100001\n", False)])
def test_formato_do_prontuario(valor, ok):
    assert prontuario_valido(valor) is ok


def test_fonte_simulada_devolve_datas_relativas_a_hoje(fonte):
    h = fonte.buscar("100001")
    assert h["simulado"] is True and h["fonte"] == "simulado" and h["prontuario"] == "100001"
    assert [a["ha_dias"] for a in h["atendimentos"]] == sorted(a["ha_dias"] for a in h["atendimentos"])
    assert h["atendimentos"][0]["data"] == "2026-11-14" and h["atendimentos"][0]["ha_dias"] == 2
    assert "dipirona" in h["alergias"] and "uso_anticoagulante" in h["sinais"]


def test_prontuario_desconhecido_ou_invalido_devolve_none(fonte):
    assert fonte.buscar("999999") is None and fonte.buscar("abc") is None and fonte.buscar(None) is None
    assert consultar(fonte, "999999") is None and consultar(None, "100001") is None
    assert "100001" in fonte.exemplos()


def test_buscar_devolve_copia_que_nao_estraga_o_arquivo_em_memoria(fonte):
    h = fonte.buscar("100001")
    h["alergias"].append("x")
    h["atendimentos"].clear()
    assert fonte.buscar("100001")["alergias"] == ["dipirona"] and len(fonte.buscar("100001")["atendimentos"]) == 3


def test_arquivo_simulado_so_tem_dado_inventado_e_cores_validas():
    dados = json.loads(modulo.ARQUIVO_SIMULADO.read_text(encoding="utf-8"))
    assert "INVENTADOS" in dados["aviso"]
    for p in dados["pacientes"].values():
        assert "nome" not in p and "cpf" not in p  # nem inventado: o protótipo não precisa
        for a in p["atendimentos"]:
            assert a["cor"] in {"vermelho", "laranja", "amarelo", "verde", "azul"}
            assert a["queixa"] in {"dor_toracica", "dor_abdominal", "respiratorio_febre", "outra", "indefinida"}


# --- cruzamento -----------------------------------------------------------------------------

def test_padroes_de_retorno_e_de_queixa_repetida(fonte):
    padroes = consultar(fonte, "100001", saida_de(FICHA_PEITO))["padroes"]
    assert codigos(padroes)[:3] == ["retorno_precoce", "retorno_frequente", "queixa_repetida"]
    texto = {p["codigo"]: p["mensagem"] for p in padroes}
    assert "3ª vinda em 30 dias" in texto["retorno_frequente"]
    assert "2 atendimentos anteriores" in texto["queixa_repetida"] and "Angina (2x)" in texto["queixa_repetida"]
    assert "não diagnóstico de hoje" in texto["queixa_repetida"]  # é registro, nunca diagnóstico


def test_queixa_diferente_nao_vira_padrao_de_repeticao(fonte):
    ficha = {"dados_atendente": {"idade": 58}, "respostas": {"Q01": "dor na barriga desde ontem"}}
    assert "queixa_repetida" not in codigos(consultar(fonte, "100001", saida_de(ficha))["padroes"])


def test_queixa_generica_nunca_vira_padrao(fonte):
    h = fonte.buscar("100001")
    assert "queixa_repetida" not in codigos(cruzar(h, {"queixas": ["outra", "indefinida"]}))


def test_alergia_do_historico_que_falta_na_ficha(fonte):
    padroes = consultar(fonte, "100001", saida_de(FICHA_PEITO))["padroes"]
    alerta = next(p for p in padroes if p["codigo"] == "alergia_no_historico")
    assert alerta["nivel"] == "grave" and "dipirona" in alerta["mensagem"]
    h = fonte.buscar("100001")
    assert "alergia_no_historico" not in codigos(cruzar(h, {"alergias": {"status": "presente", "itens": ["Dipirona"]}}))
    assert "alergia_no_historico" in codigos(cruzar(h, {"alergias": {"status": "presente", "itens": ["amendoim"]}}))
    assert "alergia_no_historico" in codigos(cruzar(h, {"alergias": {"status": "nao_sabe", "itens": []}}))


def test_sinal_do_historico_nao_confirmado_hoje(fonte):
    h = fonte.buscar("100001")
    sinais = [{"nome": "uso_anticoagulante", "status": "negado"}, {"nome": "doenca_cronica", "status": "presente"}]
    msgs = [p["mensagem"] for p in cruzar(h, {"sinais": sinais}) if p["codigo"] == "historico_diverge_da_ficha"]
    assert len(msgs) == 1 and "anticoagulante" in msgs[0]
    sinais[0]["status"] = "presente"
    assert "historico_diverge_da_ficha" not in codigos(cruzar(h, {"sinais": sinais}))


def test_paciente_sem_atendimentos_nao_gera_padrao(fonte):
    assert consultar(fonte, "100004", saida_de(FICHA_PEITO))["padroes"] == []


def test_um_atendimento_antigo_so_gera_queixa_repetida(fonte):
    ficha = {"dados_atendente": {"idade": 41}, "respostas": {"Q01": "dor na barriga forte", "Q10": {"resposta": True}}}
    saida = saida_de(ficha)
    saida["alergias"] = {"status": "presente", "itens": ["penicilina"], "tipos": ["medicamento"]}
    padroes = consultar(fonte, "100003", saida)["padroes"]
    assert codigos(padroes) == ["queixa_repetida"] and "1 atendimento anterior" in padroes[0]["mensagem"]


def test_limites_vem_das_regras(fonte, monkeypatch):
    regras = copy.deepcopy(carregar_regras())
    regras["historico"].update(retorno_precoce_dias=1, janela_retorno_dias=5, atendimentos_para_retorno_frequente=3)
    monkeypatch.setattr(modulo, "carregar_regras", lambda: regras)
    assert codigos(cruzar(fonte.buscar("100001"), {})) == ["alergia_no_historico", "historico_diverge_da_ficha",
                                                           "historico_diverge_da_ficha"]


@pytest.mark.parametrize("chave, valor", [("retorno_precoce_dias", 0), ("janela_retorno_dias", "30"),
                                          ("atendimentos_para_retorno_frequente", True),
                                          ("janela_retorno_dias", None)])
def test_limites_invalidos_sao_recusados(chave, valor):
    regras = copy.deepcopy(carregar_regras())
    regras["historico"][chave] = valor
    with pytest.raises(RegrasInvalidas):
        validar_regras(regras)


def test_cruzamento_nunca_muda_a_triagem(fonte):
    """Segurança: o histórico só acrescenta avisos; cor, pontuação e sinais ficam idênticos."""
    for prontuario in fonte.exemplos():
        saida = saida_de(FICHA_PEITO)
        antes = copy.deepcopy(saida)
        h = consultar(fonte, prontuario, saida)
        assert saida == antes
        for p in h["padroes"]:
            assert set(p) == {"codigo", "nivel", "mensagem"} and p["nivel"] in {"grave", "atencao", "info"}


def test_o_cruzamento_e_codigo_sem_ia():
    fonte_do_modulo = modulo.Path(modulo.__file__).read_text(encoding="utf-8")
    for proibido in ("import requests", "ollama", "extrator", "urllib", "http.client"):
        assert proibido not in fonte_do_modulo.lower().replace("sem ia", ""), proibido


def test_fonte_e_trocavel():
    class OutraFonte(FonteHistorico):
        nome = "hospital"

        def buscar(self, prontuario):
            return {"prontuario": prontuario, "fonte": self.nome, "simulado": False, "idade": 70,
                    "sexo_biologico": None, "condicoes": [], "alergias": [], "medicamentos": [], "sinais": [],
                    "atendimentos": [{"data": "2026-11-16", "ha_dias": 0, "queixa": "dor_toracica",
                                      "descricao": "dor no peito", "cor": "laranja", "diagnostico": None,
                                      "desfecho": None}]}

    h = consultar(OutraFonte(), "5555", saida_de(FICHA_PEITO))
    assert h["fonte"] == "hospital" and codigos(h["padroes"]) == ["retorno_precoce", "queixa_repetida"]
    assert "hoje" in h["padroes"][0]["mensagem"] and "não informado" in h["padroes"][0]["mensagem"]
    assert OutraFonte().exemplos() == []


# --- rotas ----------------------------------------------------------------------------------

@pytest.fixture(scope="module")
def srv():
    s = criar_servidor(0)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    yield s
    s.shutdown()
    s.server_close()


def chamar(srv, metodo, caminho, corpo=None):
    con = http.client.HTTPConnection("127.0.0.1", srv.server_address[1], timeout=10)
    dados = None if corpo is None else json.dumps(corpo).encode()
    con.request(metodo, caminho, body=dados, headers={"Content-Type": "application/json"} if dados else {})
    r = con.getresponse()
    return r.status, json.loads(r.read() or b"{}")


def test_rota_do_historico(srv):
    status, h = chamar(srv, "POST", "/api/historico", {"prontuario": "100001"})
    assert status == 200 and h["simulado"] is True and len(h["atendimentos"]) == 3 and "padroes" not in h
    assert chamar(srv, "POST", "/api/historico", {"prontuario": "999999"})[0] == 404
    for ruim in ("12", "abc", 100001, None, ["100001"], {"a": 1}):
        assert chamar(srv, "POST", "/api/historico", {"prontuario": ruim})[0] == 400, ruim
    assert chamar(srv, "POST", "/api/historico", {})[0] == 400
    assert chamar(srv, "GET", "/api/historico")[0] == 404  # o prontuário nunca vai no endereço


def test_triagem_com_prontuario_acrescenta_padroes_sem_mudar_a_classificacao(srv):
    _, sem = chamar(srv, "POST", "/api/triagem", {"ficha": FICHA_PEITO})
    status, com = chamar(srv, "POST", "/api/triagem", {"ficha": FICHA_PEITO, "prontuario": "100001"})
    assert status == 200 and "historico" not in sem
    assert com["saida"] == sem["saida"]
    assert "queixa_repetida" in codigos(com["historico"]["padroes"])


@pytest.mark.parametrize("prontuario", ["999999", "abc", None, 12, ""])
def test_prontuario_ruim_nao_derruba_a_triagem(srv, prontuario):
    status, corpo = chamar(srv, "POST", "/api/triagem", {"ficha": FICHA_PEITO, "prontuario": prontuario})
    assert status == 200 and corpo["historico"] is None and corpo["saida"]["classificacao"]["cor"]


def test_ficha_invalida_com_prontuario_continua_422(srv):
    status, corpo = chamar(srv, "POST", "/api/triagem", {"ficha": {"respostas": {}}, "prontuario": "100001"})
    assert status == 422 and "historico" not in corpo


def test_interface_informa_se_o_historico_esta_ligado(srv):
    _, q = chamar(srv, "GET", "/api/questionario")
    assert q["historico"] == {"ligado": True, "fonte": "simulado", "exemplos": ["100001", "100002", "100003", "100004"]}
    desligado = criar_servidor(0, sem_historico=True)
    threading.Thread(target=desligado.serve_forever, daemon=True).start()
    try:
        assert chamar(desligado, "GET", "/api/questionario")[1]["historico"] == {"ligado": False, "fonte": None,
                                                                               "exemplos": []}
        assert chamar(desligado, "POST", "/api/historico", {"prontuario": "100001"})[0] == 404
        status, corpo = chamar(desligado, "POST", "/api/triagem", {"ficha": FICHA_PEITO, "prontuario": "100001"})
        assert status == 200 and corpo["historico"] is None
    finally:
        desligado.shutdown()
        desligado.server_close()


def test_a_fila_nao_guarda_o_prontuario(srv):
    status, _ = chamar(srv, "POST", "/api/fila", {"ficha": FICHA_PEITO, "prontuario": "100001"})
    assert status == 200
    linhas = srv.fila._con.execute("SELECT * FROM pacientes").fetchall()
    assert linhas and all("100001" not in json.dumps([str(v) for v in tuple(linha)]) for linha in linhas)
