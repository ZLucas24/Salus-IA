"""Regressões dos achados da revisão externa (relatório de outro modelo, conferido um a um)."""

import threading

import pytest

from helpers import ExtratorFalso
from triagem.entrevista import processar_ficha
from triagem.extracao import Extracao, ExtratorIndisponivel, criar_extrator_ou_indisponivel
from triagem.extrator_mock import MockExtrator
from triagem.extrator_ollama import OllamaExtrator, _Resposta
from triagem.historico import cruzar
from triagem.questionario import perguntas_por_id
from triagem.schema import Alergias, Sinal
from triagem.sinais import NomeSinal, Origem, Status
from triagem.treino import anonimizar, montar_caso
from triagem.usuarios import TENTATIVAS, Usuarios
from triagem.voz import interpretar_fala

MOCK = MockExtrator()
P = perguntas_por_id()


def ficha(respostas, idade=40, extrator=MOCK):
    return processar_ficha({"dados_atendente": {"idade": idade}, "respostas": respostas}, extrator)


def extrator_com(*sinais, alergias=None):
    return ExtratorFalso(Extracao(sinais=list(sinais), alergias=alergias))


def do_relato(nome, valor=None, itens=()):
    return Sinal(nome=nome, status=Status.PRESENTE, valor=valor, itens=list(itens), trecho="x",
                 origem=Origem.EXTRAIDO_DO_RELATO)


# --- 1. divergência relato x resposta não reduz a classificação ------------------------------

def test_resposta_que_nega_a_dor_do_relato_nao_baixa_cor_nem_pontuacao():
    ext = extrator_com(do_relato(NomeSinal.DOR, valor=9))
    so_relato = ficha({"Q01": "dor nota 9"}, extrator=ext).classificacao
    com_q05 = ficha({"Q01": "dor nota 9", "Q05": 0}, extrator=ext)
    assert (com_q05.classificacao.cor.nivel, com_q05.classificacao.pontuacao) >= \
        (so_relato.cor.nivel, so_relato.pontuacao)
    dor = next(s for s in com_q05.sinais if s.nome == NomeSinal.DOR)
    assert dor.status == Status.NEGADO and dor.status_no_relato == Status.PRESENTE and dor.valor == 9


def test_divergencia_mantem_os_itens_do_relato():
    ext = extrator_com(do_relato(NomeSinal.DOENCA_CRONICA, itens=["diabetes"]))
    s = ficha({"Q01": "sou diabético", "Q13": []}, extrator=ext)
    cronica = next(x for x in s.sinais if x.nome == NomeSinal.DOENCA_CRONICA)
    assert cronica.status_no_relato == Status.PRESENTE and cronica.itens == ["diabetes"]


# --- 2 e 5. marcadores ("não sabe" etc.) nunca viram texto ----------------------------------

def test_nao_sabe_no_relato_nao_vira_texto_do_relato():
    s = ficha({"Q01": "nao_sabe"})
    assert s.relato_original == "" and s.queixa_principal is None


def test_nao_sabe_no_nome_da_alergia_nao_vira_item():
    s = ficha({"Q10": {"resposta": True, "texto": "nao_sabe"}})
    assert s.alergias.status == Status.PRESENTE and s.alergias.itens == []
    assert all("Status." not in i for i in s.alergias.itens)


def test_nao_se_aplica_em_pergunta_de_seguranca_nao_e_dado_desconhecido():
    s = ficha({"Q15": "nao_se_aplica"}, idade=30)
    assert "dado_desconhecido" not in [a.codigo for a in s.alertas]
    assert "dado_desconhecido" in [a.codigo for a in ficha({"Q08": "nao_sabe"}).alertas]


# --- 3. extrator que não inicia degrada ---------------------------------------------------

def test_extrator_que_nao_inicia_vira_falha_de_leitura(monkeypatch):
    monkeypatch.setenv("OLLAMA_HOST", "http://[endereco-invalido")
    ext = criar_extrator_ou_indisponivel("ollama")
    assert isinstance(ext, ExtratorIndisponivel)
    s = ficha({"Q01": "dor no peito", "Q09": True}, extrator=ext)
    assert "extracao_falhou" in [a.codigo for a in s.alertas] and s.classificacao.cor
    with pytest.raises(ValueError):
        criar_extrator_ou_indisponivel("inexistente")


def test_cli_nao_sai_com_erro_interno_quando_o_extrator_nao_inicia(monkeypatch, tmp_path, capsys):
    from triagem import cli
    monkeypatch.setenv("OLLAMA_HOST", "http://[endereco-invalido")
    arquivo = tmp_path / "f.json"
    arquivo.write_text('{"dados_atendente": {"idade": 40}, "respostas": {"Q01": "dor"}}', encoding="utf-8")
    assert cli.main([str(arquivo), "--extrator", "ollama", "-q"]) == 0
    assert "extracao_falhou" in capsys.readouterr().out


# --- 4. contagem de senhas erradas com acessos simultâneos ---------------------------------

def test_tentativas_simultaneas_nao_perdem_a_contagem():
    u = Usuarios(":memory:")
    u.criar("ana", "Ana", "senha-segura")
    fios = [threading.Thread(target=u.entrar, args=("ana", "errada")) for _ in range(TENTATIVAS * 3)]
    for f in fios:
        f.start()
    for f in fios:
        f.join()
    assert u.entrar("ana", "senha-segura") is None  # bloqueado: nenhuma falha se perdeu
    u.fechar()


# --- 6 e 7. alergia, pendências e duração ----------------------------------------------------

def test_alergia_do_relato_vale_quando_a_q10_e_nao_sabe_ou_recusou():
    ext = extrator_com(alergias=Alergias(status=Status.PRESENTE, itens=["dipirona"]))
    for marcador in ("nao_sabe", "recusou"):
        assert ficha({"Q01": "alérgico a dipirona", "Q10": marcador}, extrator=ext).alergias.itens == ["dipirona"]


def test_alergia_divergente_volta_a_q10_para_as_pendencias_e_sem_parenteses_vazios():
    ext = extrator_com(alergias=Alergias(status=Status.PRESENTE, itens=[]))
    s = ficha({"Q01": "sou alérgico", "Q10": {"resposta": False}}, extrator=ext)
    alerta = next(a for a in s.alertas if a.codigo == "alergia_divergente")
    assert "()" not in alerta.mensagem and "Q10" in s.perguntas_pendentes


def test_duracao_divergente_volta_a_q02_e_zero_com_zero_concorda():
    q02 = {"inicio": "de_repente", "duracao": {"valor": 2, "unidade": "horas"}}
    s = ficha({"Q01": "dor há 3 dias", "Q02": q02})
    assert "duracao_divergente" in [a.codigo for a in s.alertas] and "Q02" in s.perguntas_pendentes
    q02["duracao"] = {"valor": 0, "unidade": "minutos"}
    s = ficha({"Q01": "dor há 0 minutos", "Q02": q02})
    assert "duracao_divergente" not in [a.codigo for a in s.alertas]


# --- 8. extrator por palavras-chave -------------------------------------------------------------

def test_duracao_absurda_e_descartada_sem_perder_a_leitura():
    e = MOCK.extrair("dor no peito há 2000 dias")
    assert e.duracao is None and any(s.nome == NomeSinal.DOR for s in e.sinais) and e.avisos


def test_doenca_negada_nao_entra_nos_itens():
    e = MOCK.extrair("tenho diabetes, não tenho pressão alta")
    assert next(s for s in e.sinais if s.nome == NomeSinal.DOENCA_CRONICA).itens == ["diabetes"]
    assert next(s for s in MOCK.extrair("tenho insuficiência cardíaca").sinais
                if s.nome == NomeSinal.DOENCA_CRONICA).itens


def test_queixa_com_negacao_longe_continua_reconhecida():
    assert [q.value for q in MOCK.extrair("tosse que não passa há 3 dias").queixas] == ["respiratorio_febre"]
    assert "respiratorio_febre" not in [q.value for q in MOCK.extrair("dor de cabeça, sem febre").queixas]


def test_nome_da_alergia_para_antes_da_proxima_ideia():
    assert MOCK.extrair("tenho alergia a penicilina quando tomo fico com falta de ar").alergias.itens == ["penicilina"]


# --- 9. modelo local devolvendo campos fora do formato ----------------------------------------

def test_resposta_do_modelo_com_campos_ruins_nao_derruba_a_leitura():
    r = _Resposta.model_validate({"queixas": None, "sinais": None, "duracao": {"valor": 5000, "unidade": "dias"},
                                  "alergias": {"itens": [123, None, "dipirona"]}})
    e = OllamaExtrator._converter("alérgico a dipirona", r)
    assert e.duracao is None and e.alergias.itens == ["dipirona"] and e.avisos
    assert "descartes" not in str(_Resposta.model_json_schema())  # o modelo não vê o campo interno


# --- 11. anonimização ---------------------------------------------------------------------------

@pytest.mark.parametrize("texto, esperado", [
    ("moro na rua das flores, 123", "moro na [ENDERECO]"),
    ("moro na Rua São João. Estou com dor", "moro na [ENDERECO]. Estou com dor"),
    ("caí na rua e bati a cabeça", "caí na rua e bati a cabeça"),
])
def test_endereco(texto, esperado):
    assert anonimizar(texto) == esperado


def test_nomes_suspeitos_tambem_nas_respostas_em_texto():
    caso = montar_caso("abc", {"dados_atendente": {"idade": 40},
                               "respostas": {"Q07": "piora quando o Joaquim chega", "Q01": "dor"}},
                       {"relato_original": "dor", "sinais": [], "alertas": []}, "mock")
    assert "Joaquim" in caso["revisar_nomes"]


# --- baixa gravidade -----------------------------------------------------------------------------

@pytest.mark.parametrize("texto, esperado", [("Sem dúvida, sim", True), ("Não entendi", None), ("não ouvi", None)])
def test_voz_sim_nao(texto, esperado):
    e = interpretar_fala(P["Q09"]["partes"][0], texto)
    assert (e.valor if e.entendido else None) == esperado


@pytest.mark.parametrize("texto, esperado", [("2h", {"valor": 2, "unidade": "horas"}),
                                             ("30min", {"valor": 30, "unidade": "minutos"}), ("2000 dias", None)])
def test_voz_duracao(texto, esperado):
    parte = next(x for x in P["Q02"]["partes"] if x["nome"] == "duracao")
    e = interpretar_fala(parte, texto)
    assert (e.valor if e.entendido else None) == esperado


def test_glicemia_pedida_para_qualquer_jeito_de_escrever_diabetes():
    ext = extrator_com(do_relato(NomeSinal.DOENCA_CRONICA, itens=["Diabetes mellitus"]))
    assert "E06" in ficha({"Q01": "tenho diabetes"}, extrator=ext).afericoes_faltando


def test_historico_fora_de_ordem_usa_o_atendimento_mais_recente():
    h = {"alergias": [], "sinais": [], "atendimentos": [
        {"ha_dias": 200, "queixa": "outra", "descricao": "antigo", "desfecho": None, "diagnostico": None},
        {"ha_dias": 1, "queixa": "outra", "descricao": "recente", "desfecho": "alta", "diagnostico": None}]}
    assert "recente" in next(p for p in cruzar(h, {}) if p["codigo"] == "retorno_precoce")["mensagem"]
