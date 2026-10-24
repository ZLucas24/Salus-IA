"""Interpretação determinística das respostas fechadas (um bloco por tipo)."""

import math

import pytest

from triagem.questionario import ErroResposta, interpretar, perguntas_por_id
from triagem.schema import Duracao
from triagem.sinais import NomeSinal, Origem, Status

P = perguntas_por_id()


def estados(pid, bruto):
    r = interpretar(P[pid], bruto)
    return {n.value: (s.status.value, s.valor, s.itens) for n, s in r.sinais.items()}


@pytest.mark.parametrize("pid, sinal", [
    ("Q08", "alteracao_consciencia"), ("Q09", "dispneia"), ("T01", "suor_frio_enjoo_tontura"),
    ("T02", "dor_piora_esforco_respirar"), ("T03", "risco_tromboembolico"),
    ("A04", "abdome_rigido_distendido"), ("R04", "contato_ou_viagem"),
])
def test_sim_nao_simples(pid, sinal):
    assert estados(pid, True)[sinal][0] == "presente"
    assert estados(pid, False)[sinal][0] == "negado"


@pytest.mark.parametrize("pid, sinal", [("A05", "alteracao_urinaria"), ("R02", "fala_entrecortada"),
                                        ("R05", "dificuldade_beber")])
def test_sim_nao_invertido(pid, sinal):
    """Nestas perguntas 'sim' significa normal."""
    assert estados(pid, True)[sinal][0] == "negado"
    assert estados(pid, False)[sinal][0] == "presente"


def test_sinais_diretos_tem_origem_resposta_direta():
    assert all(s.origem == Origem.RESPOSTA_DIRETA for s in interpretar(P["Q09"], True).sinais.values())


def test_opcao_com_quando():
    assert estados("Q03", "piorando")["piora_progressiva"][0] == "presente"
    assert estados("Q03", "melhorando")["piora_progressiva"][0] == "negado"
    assert estados("Q04", "aperto")["dor_em_aperto"][0] == "presente"
    assert estados("Q04", "colica")["dor_em_aperto"][0] == "negado"


def test_escala_da_dor_zero_e_negada_e_nota_vira_valor():
    assert estados("Q05", 0)["dor"][:2] == ("negado", None)
    assert estados("Q05", 8)["dor"][:2] == ("presente", 8.0)


@pytest.mark.parametrize("valor", [11, -1, 7.5, True, "7", float("nan"), float("inf"), [5]])
def test_escala_invalida(valor):
    with pytest.raises(ErroResposta):
        interpretar(P["Q05"], valor)


def test_erro_mostra_o_valor_recebido():
    with pytest.raises(ErroResposta, match="'talvez'"):
        interpretar(P["Q09"], "talvez")


def test_composta_q02_inicio_e_duracao():
    r = interpretar(P["Q02"], {"inicio": "de_repente", "duracao": {"valor": 2, "unidade": "horas"}})
    assert r.sinais[NomeSinal.INICIO_SUBITO].status == Status.PRESENTE
    assert r.duracao == Duracao(valor=2, unidade="horas")
    assert estados("Q02", {"inicio": "aos_poucos"})["inicio_subito"][0] == "negado"


@pytest.mark.parametrize("duracao", [{"valor": 2}, {"valor": -1, "unidade": "horas"},
                                     {"valor": 2, "unidade": "luas"}, {"valor": math.nan, "unidade": "dias"},
                                     {"valor": 5000, "unidade": "anos"}, "2 horas"])
def test_duracao_invalida(duracao):
    with pytest.raises(ErroResposta):
        interpretar(P["Q02"], {"duracao": duracao})


def test_dependente_ausente_deixa_pergunta_incompleta():
    r = interpretar(P["Q12"], {"resposta": True})
    assert "classes" in r.incompleta
    assert NomeSinal.ANTITERMICO_RECENTE not in r.sinais


def test_dependente_informado_sem_condicao_e_contradicao():
    with pytest.raises(ErroResposta, match="só se aplica"):
        interpretar(P["Q11"], {"resposta": False, "insulina": True})
    with pytest.raises(ErroResposta):
        interpretar(P["Q06"], {"resposta": False, "para_onde": "braço"})


def test_filho_de_um_nao_e_nao():
    assert estados("Q12", {"resposta": False})["antitermico_recente"][0] == "negado"
    assert estados("Q11", {"resposta": False})["uso_insulina"][0] == "negado"


def test_q12_antitermico():
    e = estados("Q12", {"resposta": True, "classes": ["antitermico"], "texto": "dipirona"})
    assert e["antitermico_recente"][0] == "presente"
    assert estados("Q12", {"resposta": True, "classes": ["analgesico"]})["antitermico_recente"][0] == "negado"


def test_marcadores_nao_sabe_recusou_nunca_viram_nao():
    r = interpretar(P["Q09"], "nao_sabe")
    assert r.sinais[NomeSinal.DISPNEIA].status == Status.NAO_SABE
    r = interpretar(P["Q11"], {"resposta": "recusou"})
    assert r.sinais[NomeSinal.USO_INSULINA].status == Status.RECUSOU
    assert r.desconhecidos == ["resposta"]


def test_multiplas_lista_vazia_e_negado_e_itens_viram_valor():
    assert estados("Q13", [])["doenca_cronica"][0] == "negado"
    s = estados("Q13", ["diabetes", "renopatia"])["doenca_cronica"]
    assert s[0] == "presente" and s[2] == ["diabetes", "renopatia"]


@pytest.mark.parametrize("bruto", [["gripe"], ["diabetes", "diabetes"], "diabetes", [1]])
def test_multiplas_invalida(bruto):
    with pytest.raises(ErroResposta):
        interpretar(P["Q13"], bruto)


def test_q15_ou_entre_partes():
    assert estados("Q15", {"gravida_possivel": False, "amamentando": False,
                           "menstruacao_atrasada": True})["gravidez_possivel"][0] == "presente"
    todos_nao = estados("Q15", {"gravida_possivel": False, "amamentando": False, "menstruacao_atrasada": False})
    assert todos_nao["gravidez_possivel"][0] == "negado"
    parcial = interpretar(P["Q15"], {"gravida_possivel": False})
    assert NomeSinal.GRAVIDEZ_POSSIVEL not in parcial.sinais  # falta uma parte: sem conclusão
    assert set(parcial.incompleta) == {"amamentando", "menstruacao_atrasada"}


def test_a02_episodios_viram_valor_do_vomito():
    e = estados("A02", {"vomitando": True, "episodios": 4, "sangue_vomito_ou_fezes": False})
    assert e["vomito"][:2] == ("presente", 4.0) and e["sangue_vomito_fezes"][0] == "negado"


def test_alergia_q10():
    r = interpretar(P["Q10"], {"resposta": True, "tipos": ["medicamento"], "texto": "Dipirona; penicilina e dipirona"})
    assert r.alergias.status == Status.PRESENTE
    assert r.alergias.itens == ["Dipirona", "penicilina"]  # sem repetição
    assert interpretar(P["Q10"], {"resposta": False}).alergias.status == Status.NEGADO
    assert interpretar(P["Q10"], "recusou").alergias.status == Status.RECUSOU
    assert "texto" in interpretar(P["Q10"], {"resposta": True}).incompleta  # faltam os nomes


def test_texto_livre_valida_tamanho_depois_do_strip_e_vazio():
    assert interpretar(P["Q01"], "  " + "x" * 200 + "  ").relato == "x" * 200
    with pytest.raises(ErroResposta):
        interpretar(P["Q01"], "x" * 201)
    with pytest.raises(ErroResposta):
        interpretar(P["Q01"], "   ")


def test_campos_desconhecidos_e_tipo_errado_da_composta():
    with pytest.raises(ErroResposta, match="desconhecido"):
        interpretar(P["Q12"], {"resposta": False, "tomou": 1})
    with pytest.raises(ErroResposta):
        interpretar(P["Q12"], True)
