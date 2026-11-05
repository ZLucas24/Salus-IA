"""Extratores: mock (regras) e Ollama (com cliente falso). Sem rede."""

import json

import pytest

from triagem.extracao import criar_extrator
from triagem.extrator_mock import MockExtrator
from triagem.extrator_ollama import ErroExtracao, OllamaExtrator
from triagem.schema import Duracao
from triagem.sinais import NomeSinal, Origem, Queixa, Status


def estados(ext):
    return {s.nome.value: s.status.value for s in ext.sinais}


# --- mock ------------------------------------------------------------------------------

def test_mock_extrai_o_que_o_relato_cita_com_trecho_e_origem():
    ext = MockExtrator().extrair("Dor no peito há 2 horas, sem febre")
    assert estados(ext) == {"dor": "presente", "febre_referida": "negado"}
    assert ext.duracao == Duracao(valor=2, unidade="horas")
    assert ext.queixas == [Queixa.DOR_TORACICA]
    assert all(s.origem == Origem.EXTRAIDO_DO_RELATO and s.trecho for s in ext.sinais)
    assert ext.queixa_principal == "dor no peito há 2 horas"


@pytest.mark.parametrize("relato, esperado", [
    ("vomitando sem parar desde a madrugada", {"vomito": "presente"}),            # "sem parar" não nega
    ("não consigo parar de vomitar", {"vomito": "presente"}),
    ("Dor no peito, sem dor nas costas", {"dor": "presente"}),                     # presente vence negado
    ("sem dor de barriga", {"dor": "negado", "dor_abdominal": "negado"}),
    ("não tenho febre nem tosse", {"febre_referida": "negado"}),
    ("nada de falta de ar", {"dispneia": "negado"}),
    ("sofri um acidente vascular", {}),                                            # AVC não é trauma
    ("estou doendo muito e com falta de ar", {"dor": "presente", "dispneia": "presente"}),
])
def test_mock_negacao_vale_para_a_palavra_logo_depois(relato, esperado):
    assert estados(MockExtrator().extrair(relato)) == esperado


@pytest.mark.parametrize("relato, itens", [
    ("alérgico a dipirona e tenho dor", ["dipirona"]),
    ("sou alérgico a dipirona, penicilina", ["dipirona", "penicilina"]),
    ("tenho alergia a ibuprofeno", ["ibuprofeno"]),
    ("sou alérgico a ela", []),                                  # pronome não é medicamento
])
def test_mock_alergia_so_quando_afirmada(relato, itens):
    ext = MockExtrator().extrair(relato)
    assert ext.alergias.status == Status.PRESENTE and ext.alergias.itens == itens


@pytest.mark.parametrize("relato", ["não tenho alergia a remédio", "sem alergia", "nunca tive alergia a nada"])
def test_mock_ignora_negacao_de_alergia(relato):
    assert MockExtrator().extrair(relato).alergias is None


@pytest.mark.parametrize("relato, esperado", [
    ("dor há 3 dias", (3, "dias")), ("febre há dois dias", (2, "dias")), ("tosse faz 1 mês", (1, "meses")),
    ("mal-estar há uns 20 minutos", (20, "minutos")), ("febre desde ontem", (1, "dias")),
    ("há 2 h com dor", (2, "horas")),
])
def test_mock_duracao(relato, esperado):
    d = MockExtrator().extrair(relato).duracao
    assert (d.valor, d.unidade.value) == esperado


def test_mock_duracoes_diferentes_geram_aviso_e_usa_a_primeira():
    ext = MockExtrator().extrair("tosse há 1 mês e febre há 2 dias")
    assert (ext.duracao.valor, ext.duracao.unidade.value) == (1, "meses") and ext.avisos


def test_mock_queixas_e_doencas():
    ext = MockExtrator().extrair("tenho diabetes e pressão alta, dor de barriga")
    por_nome = {s.nome: s for s in ext.sinais}
    assert por_nome[NomeSinal.DOENCA_CRONICA].itens == ["diabetes", "hipertensao"]
    assert Queixa.DOR_ABDOMINAL in ext.queixas
    assert MockExtrator().extrair("vim renovar a receita").queixas == [Queixa.INDEFINIDA]


def test_mock_nunca_devolve_sinal_medido_nem_alergia_negada():
    ext = MockExtrator().extrair("febre de 39 graus, saturação baixa, sem alergia")
    assert not {s.nome for s in ext.sinais} & {NomeSinal.FEBRE_ATUAL, NomeSinal.HIPOXEMIA}


def test_registro_cria_extratores_e_rejeita_desconhecido():
    assert isinstance(criar_extrator("mock"), MockExtrator)
    with pytest.raises(ValueError, match="mock, ollama"):
        criar_extrator("inexistente")


# --- ollama (cliente falso) ----------------------------------------------------------------

class ClienteFalso:
    def __init__(self, *conteudos, erro=None):
        self.conteudos, self.erro, self.chamadas = list(conteudos), erro, []

    def chat(self, **kwargs):
        self.chamadas.append(kwargs)
        if self.erro:
            raise self.erro
        return {"message": {"content": self.conteudos.pop(0) if len(self.conteudos) > 1 else self.conteudos[0]}}


def resposta(**kw):
    return json.dumps(kw)


def extrair(relato, *conteudos, **kw):
    return OllamaExtrator(modelo="teste", cliente=ClienteFalso(*conteudos, **kw)).extrair(relato)


def test_ollama_converte_resposta_valida():
    ext = extrair("dor no peito há 2 horas, sem febre", resposta(
        queixa_principal="Dor no peito", queixas=["dor_toracica"],
        duracao={"valor": 2, "unidade": "horas"},
        sinais=[{"nome": "dor", "status": "presente", "trecho": "dor no peito"},
                {"nome": "febre_referida", "status": "negado", "trecho": "sem febre"}]))
    assert estados(ext) == {"dor": "presente", "febre_referida": "negado"}
    assert ext.queixa_principal == "dor no peito" and ext.queixas == [Queixa.DOR_TORACICA]
    assert ext.duracao == Duracao(valor=2, unidade="horas") and not ext.avisos
    assert all(s.origem == Origem.EXTRAIDO_DO_RELATO for s in ext.sinais)


def test_ollama_envia_relato_modelo_e_limites():
    cliente = ClienteFalso(resposta())
    OllamaExtrator(modelo="teste", cliente=cliente).extrair("dor")
    chamada = cliente.chamadas[0]
    assert chamada["model"] == "teste" and chamada["messages"][-1] == {"role": "user", "content": "dor"}
    assert chamada["options"]["temperature"] == 0 and chamada["options"]["num_predict"] > 0


def test_ollama_nome_inclui_o_modelo():
    assert OllamaExtrator(modelo="llama3.1:8b", cliente=ClienteFalso(resposta())).nome == "ollama:llama3.1:8b"


def test_ollama_descarta_so_o_item_invalido_e_avisa():
    ext = extrair("dor no peito", resposta(sinais=[
        {"nome": "dor", "status": "presente", "trecho": "dor no peito"},
        {"nome": "gravidade_alta", "status": "presente", "trecho": "dor"},   # fora do vocabulário
        {"nome": "hipoxemia", "status": "presente", "trecho": "dor"},         # só vem de aferição
        {"nome": "dispneia", "status": "nao_mencionado", "trecho": "dor"},    # estado não permitido
    ]))
    assert estados(ext) == {"dor": "presente"} and len(ext.avisos) == 3


def test_ollama_negado_inventado_e_descartado_quando_relato_nao_nega():
    ext = extrair("dor no peito há 2 horas", resposta(sinais=[
        {"nome": "dor", "status": "presente", "trecho": "dor no peito"},
        {"nome": "febre_referida", "status": "negado", "trecho": "dor"}]))
    assert estados(ext) == {"dor": "presente"}
    ext = extrair("tosse, não tenho febre", resposta(sinais=[
        {"nome": "febre_referida", "status": "negado", "trecho": "não tenho febre"}]))
    assert estados(ext) == {"febre_referida": "negado"}


def test_ollama_presente_vence_negado_e_incerto_fica_entre_os_dois():
    ext = extrair("sem dor, mas dor forte", resposta(sinais=[
        {"nome": "dor", "status": "negado", "trecho": "sem dor"},
        {"nome": "dor", "status": "presente", "trecho": "dor forte"}]))
    assert estados(ext) == {"dor": "presente"}
    ext = extrair("sem dor", resposta(sinais=[
        {"nome": "dor", "status": "negado", "trecho": "sem dor"},
        {"nome": "dor", "status": "incerto", "trecho": "sem dor"}]))
    assert estados(ext) == {"dor": "incerto"}


def test_ollama_alergia_so_presente_nunca_negada():
    afirmada = extrair("alérgico a dipirona", resposta(alergias={"itens": ["dipirona"]}))
    assert afirmada.alergias.status == Status.PRESENTE and afirmada.alergias.itens == ["dipirona"]
    assert extrair("sem alergia", resposta(alergias={"itens": []})).alergias is None
    assert extrair("sem alergia", resposta(alergias=None)).alergias is None


def test_ollama_valor_fora_da_faixa_perde_o_valor_mas_mantem_o_sinal():
    ext = extrair("dor 15 e febre de 390", resposta(sinais=[
        {"nome": "dor", "status": "presente", "valor": 15, "trecho": "dor 15"},
        {"nome": "febre_referida", "status": "presente", "valor": 390, "trecho": "febre de 390"}]))
    assert estados(ext) == {"dor": "presente", "febre_referida": "presente"}
    assert all(s.valor is None for s in ext.sinais) and len(ext.avisos) == 2
    ok = extrair("dor 8", resposta(sinais=[{"nome": "dor", "status": "presente", "valor": 8, "trecho": "dor 8"}]))
    assert ok.sinais[0].valor == 8


def test_ollama_sinal_sem_prova_no_relato_e_descartado():
    """Modelos pequenos inventam sinais: sem trecho que exista no relato, o sinal não entra."""
    ext = extrair("dor no peito", resposta(sinais=[
        {"nome": "dor", "status": "presente", "trecho": "dor no peito"},
        {"nome": "dispneia", "status": "presente", "trecho": "falta de ar terrível"},   # trecho inventado
        {"nome": "suor_frio_enjoo_tontura", "status": "presente"},                       # sem trecho
        {"nome": "febre_referida", "status": "presente", "trecho": "  "}]))
    assert estados(ext) == {"dor": "presente"} and len(ext.avisos) == 3
    assert ext.sinais[0].trecho == "dor no peito"
    com_acento = extrair("Dor no peito", resposta(sinais=[{"nome": "dor", "status": "presente", "trecho": "dor NO peito"}]))
    assert estados(com_acento) == {"dor": "presente"}  # comparação sem diferenciar caixa


def test_ollama_queixa_invalida_e_descartada():
    ext = extrair("x", resposta(queixas=["dor_toracica", "inventada"]))
    assert ext.queixas == [Queixa.DOR_TORACICA] and ext.avisos


def test_ollama_tenta_de_novo_uma_vez_e_depois_falha_com_erro_claro():
    cliente = ClienteFalso("não é json", resposta(sinais=[{"nome": "dor", "status": "presente", "trecho": "dor"}]))
    ext = OllamaExtrator(modelo="teste", cliente=cliente).extrair("dor")
    assert estados(ext) == {"dor": "presente"} and len(cliente.chamadas) == 2
    ruim = ClienteFalso("não é json")
    with pytest.raises(ErroExtracao, match="fora do formato"):
        OllamaExtrator(modelo="teste", cliente=ruim).extrair("dor")
    assert len(ruim.chamadas) == 2


def test_ollama_falha_de_conexao_vira_erro_de_extracao_sem_repetir():
    cliente = ClienteFalso(erro=ConnectionError("sem servidor"))
    with pytest.raises(ErroExtracao, match="sem servidor"):
        OllamaExtrator(modelo="teste", cliente=cliente).extrair("dor")
    assert len(cliente.chamadas) == 1  # timeout/conexão não se resolve repetindo


def test_ollama_host_remoto_gera_aviso(caplog):
    from triagem.extrator_ollama import _aviso_host

    with caplog.at_level("WARNING", logger="triagem.ollama"):
        _aviso_host("http://servidor.exemplo.com:11434")
        _aviso_host("http://localhost:11434")
        _aviso_host(None)
    assert len(caplog.records) == 1 and "servidor.exemplo.com" in caplog.records[0].message
