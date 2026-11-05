"""Motor de regras: cor, pontuação e a garantia de que nada reduz a prioridade."""

import random

import pytest

from helpers import citado, ficha, processar
from triagem.extracao import Extracao
from triagem.pontuacao import pontuar
from triagem.regras import carregar_regras
from triagem.sinais import Cor, NomeSinal, Status


def classificar(f, extracao=None):
    return processar(f, extracao).classificacao


def ids(c):
    return {r.id for r in c.regras_aplicadas}


def test_sem_achados_fica_na_cor_base_com_zero_pontos():
    c = classificar(ficha())
    assert (c.cor, c.pontuacao) == (Cor.VERDE, 0)
    assert c.provisoria is True and c.regras_validadas is False


def test_pontuar_recebe_o_objeto_estruturado_e_e_deterministico():
    saida = processar(ficha({"Q09": True, "Q05": 6}))
    assert pontuar(saida) == pontuar(saida) == saida.classificacao


def test_regra_de_cor_eleva_e_registra_para_auditoria():
    c = classificar(ficha({"Q08": True}))
    assert c.cor == Cor.LARANJA and "RC-01" in ids(c)
    assert any(r.id == "PESO-alteracao_consciencia" for r in c.regras_aplicadas)


def test_combinacao_exige_todos_os_sinais():
    assert "RC-08" not in ids(classificar(ficha({"Q04": "aperto", "T01": False})))
    assert "RC-08" in ids(classificar(ficha({"Q04": "aperto", "T01": True})))


def test_regra_com_limite_de_valor():
    assert "RC-16" not in ids(classificar(ficha({"Q05": 7})))
    assert "RC-16" in ids(classificar(ficha({"Q05": 8})))
    assert "RC-03" in ids(classificar(ficha(glasgow=7)))
    assert "RC-03" not in ids(classificar(ficha(glasgow=12)))


def test_cor_maxima_vence():
    c = classificar(ficha({"Q08": True}, saturacao=85))
    assert c.cor == Cor.VERMELHO and "RC-04" in ids(c)


def test_dor_proporcional_com_piso():
    baixa = classificar(ficha({"Q05": 1})).pontuacao
    media = classificar(ficha({"Q05": 5})).pontuacao
    alta = classificar(ficha({"Q05": 10})).pontuacao
    assert baixa <= media < alta
    peso = carregar_regras()["pontuacao"]["pesos"]["dor"]
    assert alta == int(peso) and baixa == int(peso * 0.5)  # piso de 50%


def test_nao_sabe_recusou_incerto_e_nao_mencionado_nao_pontuam_nem_reduzem():
    base = classificar(ficha({"Q09": True}))
    for estado in ("nao_sabe", "recusou"):
        c = classificar(ficha({"Q08": estado}))
        assert c.pontuacao == 0 and c.cor == Cor.VERDE
    ext = Extracao(sinais=[citado(NomeSinal.CALAFRIOS, Status.INCERTO)])
    assert classificar(ficha({"Q01": "x", "Q09": True}), ext).pontuacao == base.pontuacao


def test_divergencia_nao_reduz_a_pontuacao():
    """O relato cita falta de ar e a resposta direta nega: o sinal continua contando."""
    ext = Extracao(sinais=[citado(NomeSinal.DISPNEIA)])
    sem_resposta = classificar(ficha({"Q01": "falta de ar"}), ext)
    com_resposta_negando = classificar(ficha({"Q01": "falta de ar", "Q09": False}), ext)
    assert (com_resposta_negando.cor.nivel, com_resposta_negando.pontuacao) >= \
           (sem_resposta.cor.nivel, sem_resposta.pontuacao)
    assert "RC-15" in ids(com_resposta_negando)


def test_divergencia_pode_ser_desligada_nas_regras(monkeypatch):
    regras = carregar_regras()
    monkeypatch.setitem(regras["pontuacao"], "divergencia_conta_como_presente", False)
    ext = Extracao(sinais=[citado(NomeSinal.DISPNEIA)])
    assert "RC-15" not in ids(classificar(ficha({"Q01": "falta de ar", "Q09": False}), ext))


def test_promocao_ao_chegar_no_teto(monkeypatch):
    regras = carregar_regras()
    monkeypatch.setitem(regras["pontuacao"], "teto", 10)
    c = classificar(ficha({"Q09": True}))  # dispneia vale 10 pontos: sobe de cor
    assert any(r.id == "PROMOCAO" for r in c.regras_aplicadas)
    assert c.cor.nivel > Cor.AMARELO.nivel - 1 and c.pontuacao < 10


def test_pontuacao_nunca_passa_do_teto_nem_a_cor_do_vermelho():
    tudo = {"Q02": {"inicio": "de_repente"}, "Q03": "piorando", "Q04": "aperto", "Q05": 10,
            "Q06": {"resposta": True}, "Q08": True, "Q09": True, "Q11": {"resposta": True, "anticoagulante": True,
                                                                         "insulina": True},
            "Q13": ["diabetes"], "T01": True, "T02": True, "T03": True, "A02": {"vomitando": True,
            "sangue_vomito_ou_fezes": True}, "A04": True, "R02": False, "R03": {"chiado": True, "tosse_com_sangue": True}}
    c = classificar(ficha(tudo, temperatura=40, saturacao=80, frequencia_cardiaca=140, pressao_sistolica=70,
                          pressao_diastolica=40, frequencia_respiratoria=30, glicemia=40, glasgow=6))
    assert c.cor == Cor.VERMELHO and 0 <= c.pontuacao <= 100


# --- "nada reduz a pontuação": sequências aleatórias de novas informações ----------------------

RESPOSTAS = {
    "Q02": {"inicio": "de_repente"}, "Q03": "piorando", "Q04": "aperto", "Q05": 9, "Q06": {"resposta": True},
    "Q08": True, "Q09": True, "Q11": {"resposta": True, "anticoagulante": True, "insulina": False},
    "Q12": {"resposta": True, "classes": ["antitermico"]}, "Q13": ["diabetes"], "Q14": ["cirurgia"],
    "T01": True, "T02": True, "T03": True, "A01": {"local": "toda_a_barriga", "mudou_de_lugar": True},
    "A02": {"vomitando": True, "sangue_vomito_ou_fezes": True}, "A04": True, "R01": {"febre": True, "calafrios": True},
    "R03": {"chiado": True, "tosse_com_sangue": True}, "R04": True,
}
NEGATIVAS = {"Q08": False, "Q09": False, "Q05": 0, "T01": False, "R01": {"febre": False, "calafrios": False}}
AFERICOES = {"temperatura": 39, "saturacao": 85, "frequencia_cardiaca": 130, "frequencia_respiratoria": 30,
             "glicemia": 40, "glasgow": 10}


@pytest.mark.parametrize("semente", range(40))
def test_pontuacao_so_aumenta_quando_chegam_novas_informacoes(semente):
    rng = random.Random(semente)
    entradas = [("r", k, v) for k, v in RESPOSTAS.items()] + [("a", k, v) for k, v in AFERICOES.items()]
    rng.shuffle(entradas)
    respostas, aferidos, anterior = {}, {}, (-1, -1)
    for tipo, chave, valor in entradas:
        (respostas if tipo == "r" else aferidos)[chave] = valor
        c = classificar(ficha(dict(respostas), **aferidos))
        atual = (c.cor.nivel, c.pontuacao)
        assert atual >= anterior, (chave, anterior, atual)
        anterior = atual


@pytest.mark.parametrize("negativa", list(NEGATIVAS))
def test_responder_nao_depois_nunca_reduz(negativa):
    """Uma resposta negativa só acrescenta informação: nunca baixa a prioridade."""
    base = dict(RESPOSTAS)
    base.pop(negativa)
    antes = classificar(ficha(dict(base)))
    depois = classificar(ficha({**base, negativa: NEGATIVAS[negativa]}))
    assert (depois.cor.nivel, depois.pontuacao) >= (antes.cor.nivel, antes.pontuacao)


def test_relato_citando_depois_da_resposta_tambem_nao_reduz():
    base = ficha({"Q01": "falta de ar", "Q09": False})
    ext = Extracao(sinais=[citado(NomeSinal.DISPNEIA)])
    sem = classificar(base)
    com = classificar(base, ext)
    assert (com.cor.nivel, com.pontuacao) >= (sem.cor.nivel, sem.pontuacao)
