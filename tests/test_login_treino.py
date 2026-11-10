"""Login do enfermeiro (contas, sessões, rotas protegidas) e base de treino anonimizada do extrator."""

import http.client
import json
import threading

import pytest

from triagem import treino as mod_treino
from triagem.fila import Fila
from triagem.interface.servidor import criar_servidor
from triagem.treino import BaseTreino, anonimizar, faixa_etaria, montar_caso, nomes_suspeitos, particao
from triagem.usuarios import (BLOQUEIO_S, SESSAO_MAX_S, SESSAO_OCIOSA_S, TENTATIVAS, ErroUsuario, Usuarios)
from triagem.usuarios import main as usuarios_main


class Relogio:
    def __init__(self):
        self.t = 1_800_000_000.0

    def __call__(self):
        return self.t


@pytest.fixture
def relogio():
    return Relogio()


@pytest.fixture
def usuarios(relogio):
    u = Usuarios(":memory:", relogio=relogio)
    u.criar("ana", "Ana Souza", "senha-segura")
    yield u
    u.fechar()


# --- contas e sessões ---------------------------------------------------------------------

def test_senha_nao_fica_em_texto(usuarios):
    linha = usuarios._con.execute("SELECT * FROM usuarios").fetchone()
    assert b"senha-segura" not in bytes(linha["hash"]) and len(bytes(linha["sal"])) == 16


@pytest.mark.parametrize("login, nome, senha", [("a", "Ana", "senha-segura"), ("Ana Maria", "Ana", "senha-segura"),
                                                ("bia", "", "senha-segura"), ("bia", "Bia", "curta")])
def test_criar_valida(usuarios, login, nome, senha):
    with pytest.raises(ErroUsuario):
        usuarios.criar(login, nome, senha)


def test_login_repetido_e_recusado(usuarios):
    with pytest.raises(ErroUsuario):
        usuarios.criar("ANA", "Outra", "senha-segura")


def test_entrar_e_sessao(usuarios):
    assert usuarios.entrar("ana", "errada") is None
    assert usuarios.entrar("ninguem", "senha-segura") is None
    s = usuarios.entrar(" ANA ", "senha-segura")
    assert usuarios.sessao(s) == {"login": "ana", "nome": "Ana Souza"}
    assert usuarios.sessao("inventado") is None and usuarios.sessao(None) is None
    usuarios.sair(s)
    assert usuarios.sessao(s) is None


def test_bloqueio_depois_de_varias_senhas_erradas(usuarios, relogio):
    for _ in range(TENTATIVAS):
        assert usuarios.entrar("ana", "errada") is None
    assert usuarios.entrar("ana", "senha-segura") is None  # bloqueado, mesmo com a senha certa
    relogio.t += BLOQUEIO_S + 1
    assert usuarios.entrar("ana", "senha-segura") is not None


def test_sessao_expira_por_tempo_e_por_inatividade(usuarios, relogio):
    s = usuarios.entrar("ana", "senha-segura")
    relogio.t += SESSAO_OCIOSA_S + 1
    assert usuarios.sessao(s) is None
    s = usuarios.entrar("ana", "senha-segura")
    for _ in range(SESSAO_MAX_S // (SESSAO_OCIOSA_S // 2) + 1):
        relogio.t += SESSAO_OCIOSA_S // 2
        ativa = usuarios.sessao(s)
    assert ativa is None  # mesmo em uso, acaba no fim do plantão


def test_desativar_e_trocar_senha_encerram_sessoes(usuarios):
    s = usuarios.entrar("ana", "senha-segura")
    usuarios.trocar_senha("ana", "outra-senha-boa")
    assert usuarios.sessao(s) is None and usuarios.entrar("ana", "senha-segura") is None
    s = usuarios.entrar("ana", "outra-senha-boa")
    assert usuarios.desativar("ana") and usuarios.sessao(s) is None
    assert usuarios.entrar("ana", "outra-senha-boa") is None and not usuarios.existe_algum_ativo()


def test_comando_de_contas(tmp_path, monkeypatch, capsys):
    arquivo = str(tmp_path / "u.db")
    senhas = iter(["senha-segura", "senha-segura"])
    monkeypatch.setattr("getpass.getpass", lambda prompt="": next(senhas))
    assert usuarios_main(["--arquivo", arquivo, "criar", "bia", "--nome", "Bia Lima"]) == 0
    assert usuarios_main(["--arquivo", arquivo, "listar"]) == 0
    assert "Bia Lima" in capsys.readouterr().out
    senhas = iter(["a-senha-um", "a-senha-dois"])
    monkeypatch.setattr("getpass.getpass", lambda prompt="": next(senhas))
    assert usuarios_main(["--arquivo", arquivo, "senha", "bia"]) == 1  # senhas não conferem
    assert usuarios_main(["--arquivo", arquivo, "desativar", "ninguem"]) == 1


# --- servidor com login --------------------------------------------------------------------

@pytest.fixture
def srv_login(usuarios):
    f = Fila(":memory:")
    s = criar_servidor(0, f, None, None, usuarios)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    yield s, f
    s.shutdown()
    s.server_close()
    f.fechar()


def req(srv, metodo, caminho, corpo=None, tipo="application/json", cookie=None, origem=None):
    porta = srv.server_address[1]
    con = http.client.HTTPConnection("127.0.0.1", porta, timeout=10)
    cab = {}
    dados = None
    if corpo is not None:
        dados = corpo if isinstance(corpo, bytes) else json.dumps(corpo).encode()
        cab = {"Content-Type": tipo, "Content-Length": str(len(dados))}
    if cookie:
        cab["Cookie"] = cookie
    if origem:
        cab["Origin"] = origem
    con.request(metodo, caminho, body=dados, headers=cab)
    r = con.getresponse()
    return r.status, {k.lower(): v for k, v in r.getheaders()}, r.read()


def logar(srv, senha="senha-segura"):
    status, cab, _ = req(srv, "POST", "/login", f"login=ana&senha={senha}".encode(),
                         "application/x-www-form-urlencoded")
    return status, cab


def test_sem_login_tudo_e_bloqueado(srv_login):
    s, _ = srv_login
    status, cab, _ = req(s, "GET", "/")
    assert status == 303 and cab["location"] == "/login"
    for metodo, caminho in [("GET", "/api/fila"), ("GET", "/api/questionario"), ("GET", "/estatico/app.js"),
                            ("POST", "/api/triagem"), ("POST", "/api/fila"), ("POST", "/api/fila/chamar")]:
        assert req(s, metodo, caminho, {"ficha": {}} if metodo == "POST" else None)[0] == 401, caminho
    assert req(s, "POST", "/api/voz?pergunta=Q09", b"x", "audio/webm")[0] == 401
    assert req(s, "GET", "/login")[0] == 200 and req(s, "GET", "/estatico/estilo.css")[0] == 200


def test_login_errado_e_certo(srv_login):
    s, _ = srv_login
    status, cab = logar(s, "errada")
    assert status == 303 and cab["location"] == "/login?erro=1" and "set-cookie" not in cab
    assert b"incorretos" in req(s, "GET", "/login?erro=1")[2]
    status, cab = logar(s)
    biscoito = cab["set-cookie"]
    assert status == 303 and cab["location"] == "/"
    assert "HttpOnly" in biscoito and "SameSite=Strict" in biscoito
    cookie = biscoito.split(";")[0]
    assert req(s, "GET", "/", cookie=cookie)[0] == 200
    assert json.loads(req(s, "GET", "/api/eu", cookie=cookie)[2]) == {"login": "ana", "nome": "Ana Souza"}
    assert req(s, "GET", "/login", cookie=cookie)[1]["location"] == "/"


def test_login_vindo_de_outro_site_e_recusado(srv_login):
    s, _ = srv_login
    status, _, _ = req(s, "POST", "/login", b"login=ana&senha=senha-segura", "application/x-www-form-urlencoded",
                       origem="https://evil.example.com")
    assert status == 403


def test_acoes_na_fila_registram_quem_fez(srv_login):
    s, f = srv_login
    cookie = logar(s)[1]["set-cookie"].split(";")[0]
    ficha = {"dados_atendente": {"idade": 40}, "respostas": {}}
    r = json.loads(req(s, "POST", "/api/fila", {"ficha": ficha}, cookie=cookie)[2])
    assert json.loads(req(s, "GET", "/api/fila", cookie=cookie)[2])["pacientes"][0]["triado_por"] == "ana"
    req(s, "POST", "/api/fila/chamar", {"numero": r["numero"]}, cookie=cookie)
    req(s, "POST", "/api/fila/concluir", {"numero": r["numero"]}, cookie=cookie)
    linha = f._con.execute("SELECT triado_por, chamado_por, atendido_por FROM pacientes").fetchone()
    assert tuple(linha) == ("ana", "ana", "ana")


def test_sair_encerra_a_sessao(srv_login):
    s, _ = srv_login
    cookie = logar(s)[1]["set-cookie"].split(";")[0]
    status, cab, _ = req(s, "POST", "/logout", b"x", "application/x-www-form-urlencoded", cookie=cookie)
    assert status == 303 and "Max-Age=0" in cab["set-cookie"]
    assert req(s, "GET", "/api/fila", cookie=cookie)[0] == 401


# --- anonimização --------------------------------------------------------------------------

@pytest.mark.parametrize("texto, some, fica", [
    ("Meu nome é João da Silva e estou com dor no peito", "João", "dor no peito"),
    ("me chamo maria e tenho falta de ar", "maria", "falta de ar"),
    ("Sou a Ana Paula, com febre", "Ana", "febre"),
    ("CPF 123.456.789-00", "123.456", "CPF"),
    ("ligue (34) 99876-5432", "99876", "ligue"),
    ("cartão 898 0012 3456 7890", "0012", "cartão"),
    ("nasceu em 12/03/1990", "1990", "nasceu"),
    ("email ana@exemplo.com", "ana@", "email"),
    ("moro na Rua das Flores, 123 e tenho tosse", "Flores", "tenho tosse"),
    ("foi ao Dr. Carlos Mendes ontem", "Carlos", "ontem"),
])
def test_anonimizar(texto, some, fica):
    a = anonimizar(texto)
    assert some not in a and fica in a


def test_anonimizar_nao_estraga_o_relato_clinico():
    t = "Sou a mãe dele. Dor abdominal há 2 dias, febre de 38,5, vomitou 3 vezes."
    assert anonimizar(t) == t


def test_nomes_que_escapam_ficam_marcados_para_revisao():
    assert nomes_suspeitos("dor no peito desde que vi o Roberto. Ele estava mal.") == ["Roberto"]
    assert nomes_suspeitos("Dor no peito. Falta de ar.") == []


def test_faixa_e_particao():
    assert [faixa_etaria(i) for i in (3, 15, 25, 45, 70, 95, None)] == \
        ["0-11", "12-17", "18-39", "40-59", "60-79", "80+", None]
    ids = [f"{i:016x}" for i in range(2000)]
    assert all(particao(i) == particao(i) for i in ids[:50])  # determinística
    assert 0.15 < sum(particao(i) == "teste" for i in ids) / len(ids) < 0.25


def test_caso_nao_guarda_identificacao(relogio):
    from triagem.entrevista import processar_ficha
    from triagem.extracao import criar_extrator
    ficha = {"dados_atendente": {"idade": 47, "sexo_biologico": "feminino", "temperatura": 38.4},
             "respostas": {"Q01": "Meu nome é Rosa Lima, dor no peito há 2 horas", "Q09": True,
                           "Q07": "piora quando falo com o Dr. Paulo Reis",
                           "Q11": {"resposta": True, "anticoagulante": False, "insulina": False, "texto": "CPF 111.222.333-44"}}}
    saida = processar_ficha(ficha, criar_extrator("mock")).model_dump(mode="json")
    caso = montar_caso("abc123", ficha, saida, "mock", relogio)
    texto = json.dumps(caso, ensure_ascii=False)
    for proibido in ("Rosa", "Lima", "Paulo", "111.222", "47"):
        assert proibido not in texto, proibido
    assert caso["faixa_etaria"] == "40-59" and caso["afericoes"] == {"temperatura": 38.4}
    assert "dor no peito" in caso["relato"] and caso["mes"] == "2027-01"
    assert any(s["nome"] == "dispneia" and s["origem"] == "resposta_direta" for s in caso["sinais_finais"])


# --- base de treino ligada ao servidor ---------------------------------------------------------

@pytest.fixture
def srv_treino(tmp_path):
    f = Fila(":memory:")
    base = BaseTreino(str(tmp_path / "treino.db"))
    s = criar_servidor(0, f, None, None, None, base)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    yield s, base
    s.shutdown()
    s.server_close()
    f.fechar()
    base.fechar()


def test_cada_triagem_na_fila_vira_um_caso_e_a_reclassificacao_atualiza(srv_treino):
    s, base = srv_treino
    ficha = {"dados_atendente": {"idade": 30}, "respostas": {"Q01": "falta de ar desde ontem"}}
    r = json.loads(req(s, "POST", "/api/fila", {"ficha": ficha})[2])
    assert "caso_id" not in r
    casos = base.casos()
    assert len(casos) == 1 and casos[0]["relato"] == "falta de ar desde ontem" and casos[0]["revisoes"] == 0
    ficha["respostas"]["Q09"] = True
    assert req(s, "POST", "/api/fila/reclassificar", {"numero": r["numero"], "ficha": ficha})[0] == 200
    casos = base.casos()
    assert len(casos) == 1 and casos[0]["revisoes"] == 1 and casos[0]["respostas"]["Q09"] is True


def test_triagem_sem_fila_nao_grava(srv_treino):
    s, base = srv_treino
    req(s, "POST", "/api/triagem", {"ficha": {"dados_atendente": {"idade": 30}, "respostas": {}}})
    assert base.casos() == []


def test_falha_na_base_nao_atrapalha_a_triagem(srv_treino, monkeypatch):
    s, base = srv_treino

    def quebra(*a, **k):
        raise RuntimeError("disco cheio")

    monkeypatch.setattr(base, "registrar", quebra)
    status, _, _ = req(s, "POST", "/api/fila", {"ficha": {"dados_atendente": {"idade": 30}, "respostas": {}}})
    assert status == 200


def test_exportar_separa_as_particoes(tmp_path, relogio, capsys):
    base = BaseTreino(str(tmp_path / "t.db"), relogio)
    saida = {"relato_original": "dor", "sinais": [], "alertas": [], "classificacao": {"cor": "verde"}}
    for i in range(40):
        relato = "dor, falei com o Roberto" if i == 0 else "dor"
        base.registrar(f"{i:016x}", {"dados_atendente": {"idade": 30}, "respostas": {}},
                       {**saida, "relato_original": relato}, "mock")
    base.fechar()
    arq = str(tmp_path / "t.db")
    assert mod_treino.main(["--arquivo", arq, "resumo"]) == 0
    resumo = json.loads(capsys.readouterr().out)
    assert resumo["casos"] == 40 and resumo["treino"] + resumo["teste"] == 40 and resumo["revisar_nomes"] == 1
    out = tmp_path / "treino.jsonl"
    assert mod_treino.main(["--arquivo", arq, "exportar", "--particao", "treino", "--saida", str(out)]) == 0
    linhas = [json.loads(x) for x in out.read_text(encoding="utf-8").splitlines()]
    assert linhas and all(c["particao"] == "treino" for c in linhas)
    mod_treino.main(["--arquivo", arq, "exportar", "--particao", "treino", "--saida", str(out), "--sem-revisar"])
    assert all(not json.loads(x)["revisar_nomes"] for x in out.read_text(encoding="utf-8").splitlines())


def test_caso_guarda_a_leitura_crua_do_relato_mesmo_quando_concorda_com_a_resposta(srv_treino):
    s, base = srv_treino
    # relato e resposta direta dizem a mesma coisa: na saída final só aparece a resposta direta
    ficha = {"dados_atendente": {"idade": 30}, "respostas": {"Q01": "estou com falta de ar", "Q09": True}}
    req(s, "POST", "/api/fila", {"ficha": ficha})
    caso = base.casos()[0]
    assert [x["nome"] for x in caso["extracao"]["sinais"]] == ["dispneia"]
    assert "falta de ar" in caso["extracao"]["sinais"][0]["trecho"]
    final = next(x for x in caso["sinais_finais"] if x["nome"] == "dispneia")
    assert final["origem"] == "resposta_direta"
