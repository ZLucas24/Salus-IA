"""Orquestração da entrevista: validação, mesclagem, pendências e alertas."""

import pytest
from pydantic import ValidationError

from helpers import ExtratorFalso, alerta, ficha, processar, sinal, citado
from triagem.entrevista import FichaInvalida, processar_ficha
from triagem.extracao import Extracao
from triagem.schema import Alergias, DadosAtendente, Duracao, SaidaTriagem, Sinal
from triagem.sinais import NomeSinal, Origem, Queixa, Status


# --- validação ------------------------------------------------------------------

@pytest.mark.parametrize("f, trecho", [
    ({"respostas": {}}, "dados_atendente"),
    ({"dados_atendente": {}, "respostas": {}}, "idade"),
    ({"dados_atendente": {"idade": 30}, "respostas": {}, "extra": 1}, "extra"),
    ({"dados_atendente": {"idade": 30, "pulso": 80}, "respostas": {}}, "pulso"),
    (ficha({"Q01": "x" * 201}), "Q01"),
    (ficha({"Q05": 11}), "Q05"),
    (ficha({"Q09": "talvez"}), "Q09"),
    (ficha({"Q99": True}), "Q99"),
    (ficha({"Q10": {"resposta": False, "texto": "dipirona"}}), "Q10"),
    (ficha(temperatura=200), "temperatura"),
    (ficha(saturacao=float("nan")), "saturacao"),
    (ficha(pressao_sistolica=80, pressao_diastolica=120), "menor que a diast"),
    (ficha(pressao_sistolica=120), "juntas"),
    (ficha(idade=-1), "idade"),
])
def test_ficha_invalida_aponta_o_problema(f, trecho):
    with pytest.raises(FichaInvalida) as exc:
        processar(f)
    assert trecho in str(exc.value)


def test_ficha_que_nao_e_objeto():
    with pytest.raises(FichaInvalida):
        processar([])


def test_todos_os_erros_sao_reportados_de_uma_vez():
    with pytest.raises(FichaInvalida) as exc:
        processar(ficha({"Q05": 11, "Q09": "talvez"}, idade=None) | {"dados_atendente": {}})
    assert len(exc.value.erros) == 3


def test_falha_de_validacao_nao_chama_o_extrator():
    falso = ExtratorFalso()
    with pytest.raises(FichaInvalida):
        processar_ficha(ficha({"Q01": "dor", "Q09": "talvez"}), falso)
    assert falso.chamadas == []


def test_relato_com_exatamente_200_caracteres():
    assert len(processar(ficha({"Q01": "x" * 200})).relato_original) == 200


# --- schema ----------------------------------------------------------------------------

def test_schema_rejeita_relato_com_mais_de_200_caracteres():
    with pytest.raises(ValidationError):
        SaidaTriagem(relato_original="x" * 201, dados_atendente={"idade": 1}, extrator="f")


def test_schema_rejeita_sinal_duplicado_nan_e_alergia_como_sinal():
    s = Sinal(nome=NomeSinal.DOR, status=Status.PRESENTE, origem=Origem.RESPOSTA_DIRETA)
    with pytest.raises(ValidationError):
        SaidaTriagem(sinais=[s, s], dados_atendente={"idade": 1}, extrator="f")
    with pytest.raises(ValidationError):
        Sinal(nome=NomeSinal.DOR, status=Status.PRESENTE, valor=float("nan"), origem=Origem.NENHUMA)
    with pytest.raises(ValidationError):
        Sinal(nome="alergia", status=Status.PRESENTE, origem=Origem.NENHUMA)
    with pytest.raises(ValidationError):
        DadosAtendente(idade=30, temperatura=float("inf"))


def test_saida_traz_todos_os_sinais_uma_vez_e_a_versao_do_schema():
    saida = processar(ficha())
    assert [s.nome for s in saida.sinais] == list(NomeSinal)
    assert saida.versao_schema == "0.2.0" and saida.extrator == "falso"


# --- mapeamento e estados ----------------------------------------------------------------

def test_sem_respostas_tudo_e_nao_mencionado_sem_origem():
    saida = processar(ficha())
    assert all(s.status in (Status.NAO_MENCIONADO, Status.NAO_SE_APLICA) and s.origem == Origem.NENHUMA
               for s in saida.sinais)
    assert saida.alergias.status == Status.NAO_MENCIONADO


def test_afericoes_viram_sinais_medidos_com_valor():
    saida = processar(ficha(temperatura=39.2, saturacao=88, frequencia_cardiaca=120, pressao_sistolica=85,
                            pressao_diastolica=50, frequencia_respiratoria=26, glicemia=50, glasgow=13))
    for nome in ("febre_atual", "hipoxemia", "taquicardia", "hipotensao", "taquipneia",
                 "glicemia_alterada", "glasgow_reduzido"):
        s = sinal(saida, NomeSinal(nome))
        assert s.status == Status.PRESENTE and s.origem == Origem.MEDIDO_PELO_ATENDENTE and s.valor is not None
    normal = processar(ficha(temperatura=36.5, saturacao=98))
    assert sinal(normal, NomeSinal.FEBRE_ATUAL).status == Status.NEGADO
    assert sinal(normal, NomeSinal.TAQUICARDIA).status == Status.NAO_MENCIONADO  # não aferido != normal


def test_limite_de_febre_depende_da_idade():
    assert sinal(processar(ficha(idade=40, temperatura=37.6)), NomeSinal.FEBRE_ATUAL).status == Status.NEGADO
    assert sinal(processar(ficha(idade=5, temperatura=37.6)), NomeSinal.FEBRE_ATUAL).status == Status.PRESENTE


def test_crianca_nao_tem_limites_de_adulto_e_gera_alerta():
    saida = processar(ficha(idade=6, saturacao=80, frequencia_cardiaca=140))
    assert sinal(saida, NomeSinal.HIPOXEMIA).status == Status.NAO_MENCIONADO
    assert alerta(saida, "limites_pediatricos")


def test_afericoes_faltando_essenciais_e_condicionais():
    assert processar(ficha()).afericoes_faltando == ["E01", "E02", "E03", "E04"]
    completo = ficha(temperatura=36, saturacao=98, pressao_sistolica=120, pressao_diastolica=80,
                     frequencia_cardiaca=70)
    assert processar(completo).afericoes_faltando == []
    com_dispneia = completo | {"respostas": {"Q09": True}}
    assert processar(com_dispneia).afericoes_faltando == ["E05"]
    consciencia = completo | {"respostas": {"Q08": True}}
    assert processar(consciencia).afericoes_faltando == ["E06", "E07"]


def test_q10_preenche_alergias_fora_dos_sinais():
    saida = processar(ficha({"Q10": {"resposta": True, "tipos": ["medicamento"], "texto": "dipirona, penicilina"}}))
    assert saida.alergias.status == Status.PRESENTE and saida.alergias.itens == ["dipirona", "penicilina"]
    assert "Q10" not in saida.perguntas_pendentes
    assert "alergia" not in {n.value for n in NomeSinal}


def test_duracao_vem_de_q02():
    saida = processar(ficha({"Q02": {"inicio": "aos_poucos", "duracao": {"valor": 2, "unidade": "horas"}}}))
    assert saida.duracao == Duracao(valor=2, unidade="horas")


# --- perguntas pendentes -----------------------------------------------------------------------

def test_pendentes_em_ordem_de_prioridade_e_sem_complementares():
    saida = processar(ficha(sexo="ausente"))
    nucleo = saida.perguntas_pendentes
    assert nucleo[0] == saida.proxima_pergunta == "Q08"
    assert nucleo.index("Q15") < nucleo.index("Q01")  # segurança vem antes do núcleo
    assert not any(p.startswith(("C", "T", "A", "R")) for p in nucleo)  # sem módulo ativo nem complementares


def test_pergunta_respondida_sai_das_pendentes():
    saida = processar(ficha({"Q08": False, "Q10": {"resposta": False}}))
    assert "Q08" not in saida.perguntas_pendentes and "Q10" not in saida.perguntas_pendentes
    assert "Q09" in saida.perguntas_pendentes


def test_pergunta_pela_metade_continua_pendente_e_gera_alerta():
    saida = processar(ficha({"Q12": {"resposta": True}}))
    assert "Q12" in saida.perguntas_pendentes
    assert alerta(saida, "dado_incompleto")


def test_nao_sabe_e_recusou_nao_ficam_pendentes_mas_avisam():
    saida = processar(ficha({"Q08": "nao_sabe", "Q10": "recusou"}))
    assert "Q08" not in saida.perguntas_pendentes and "Q10" not in saida.perguntas_pendentes
    assert sinal(saida, NomeSinal.ALTERACAO_CONSCIENCIA).status == Status.NAO_SABE
    assert saida.alergias.status == Status.RECUSOU
    assert alerta(saida, "dado_desconhecido")[0].referencias == ["Q08", "Q10"]


def test_q15_depende_de_sexo_e_idade():
    assert "Q15" not in processar(ficha(sexo="masculino")).perguntas_pendentes
    assert "Q15" not in processar(ficha(sexo="feminino", idade=70)).perguntas_pendentes
    assert "Q15" in processar(ficha(sexo="feminino", idade=30)).perguntas_pendentes
    assert "Q15" in processar(ficha(sexo="ausente", idade=30)).perguntas_pendentes
    homem = processar(ficha(sexo="masculino"))
    assert sinal(homem, NomeSinal.GRAVIDEZ_POSSIVEL).status == Status.NAO_SE_APLICA


def test_modulo_so_entra_quando_ativo():
    sem = processar(ficha({"Q01": "dor de cabeça"}))
    assert sem.modulos_ativos == [] and not any(p[0] in "TAR" for p in sem.perguntas_pendentes)
    ext = Extracao(queixas=[Queixa.DOR_TORACICA])
    com = processar(ficha({"Q01": "dor no peito"}), ext)
    assert com.modulos_ativos == ["dor_toracica"] and {"T01", "T02", "T03"} <= set(com.perguntas_pendentes)
    por_resposta = processar(ficha({"A04": True}))
    assert por_resposta.modulos_ativos == ["dor_abdominal"]
    por_sinal = processar(ficha(temperatura=39))
    assert por_sinal.modulos_ativos == ["respiratorio_febre"]


def test_sem_modulo_gera_alerta_apenas_com_relato_extraido():
    assert alerta(processar(ficha({"Q01": "vim renovar receita"}), Extracao()), "sem_modulo")
    assert not alerta(processar(ficha()), "sem_modulo")


# --- extração e mesclagem -----------------------------------------------------------------------

def test_extrator_so_e_chamado_com_relato():
    falso = ExtratorFalso()
    processar_ficha(ficha(), falso)
    assert falso.chamadas == []
    processar_ficha(ficha({"Q01": "dor"}), falso)
    assert falso.chamadas == ["dor"]


def test_sinal_do_relato_entra_com_origem_e_trecho():
    ext = Extracao(queixa_principal="dor no peito", queixas=[Queixa.DOR_TORACICA],
                   sinais=[citado(NomeSinal.DOR, trecho="dor no peito")])
    saida = processar(ficha({"Q01": "dor no peito"}), ext)
    dor = sinal(saida, NomeSinal.DOR)
    assert (dor.status, dor.origem, dor.trecho) == (Status.PRESENTE, Origem.EXTRAIDO_DO_RELATO, "dor no peito")
    assert saida.queixa_principal == "dor no peito" and saida.queixas == [Queixa.DOR_TORACICA]


def test_pergunta_nao_respondida_segue_pendente_mesmo_com_sinal_no_relato():
    saida = processar(ficha({"Q01": "falta de ar"}), Extracao(sinais=[citado(NomeSinal.DISPNEIA)]))
    assert sinal(saida, NomeSinal.DISPNEIA).origem == Origem.EXTRAIDO_DO_RELATO
    assert "Q09" in saida.perguntas_pendentes


def test_resposta_direta_prevalece_e_a_divergencia_e_visivel():
    ext = Extracao(sinais=[citado(NomeSinal.DISPNEIA)])
    saida = processar(ficha({"Q01": "falta de ar", "Q09": False}), ext)
    s = sinal(saida, NomeSinal.DISPNEIA)
    assert (s.status, s.origem, s.status_no_relato) == (Status.NEGADO, Origem.RESPOSTA_DIRETA, Status.PRESENTE)
    assert alerta(saida, "divergencia")[0].referencias == ["dispneia"]
    assert "Q09" in saida.perguntas_pendentes  # pede confirmação


def test_relato_incerto_ou_igual_nao_e_divergencia():
    ext = Extracao(sinais=[citado(NomeSinal.DISPNEIA, Status.INCERTO)])
    assert not alerta(processar(ficha({"Q01": "x", "Q09": False}), ext), "divergencia")
    ext = Extracao(sinais=[citado(NomeSinal.DISPNEIA)])
    assert not alerta(processar(ficha({"Q01": "x", "Q09": True}), ext), "divergencia")


def test_resposta_nao_sabe_cede_ao_relato():
    ext = Extracao(sinais=[citado(NomeSinal.DISPNEIA)])
    s = sinal(processar(ficha({"Q01": "x", "Q09": "nao_sabe"}), ext), NomeSinal.DISPNEIA)
    assert s.status == Status.PRESENTE and s.origem == Origem.EXTRAIDO_DO_RELATO


def test_duracao_direta_prevalece_e_divergencia_vira_alerta():
    ext = Extracao(duracao=Duracao(valor=9, unidade="dias"))
    saida = processar(ficha({"Q01": "x", "Q02": {"inicio": "aos_poucos", "duracao": {"valor": 2, "unidade": "horas"}}}), ext)
    assert saida.duracao.unidade.value == "horas" and alerta(saida, "duracao_divergente")
    parecida = processar(ficha({"Q01": "x", "Q02": {"inicio": "aos_poucos", "duracao": {"valor": 24, "unidade": "horas"}}}),
                         Extracao(duracao=Duracao(valor=1, unidade="dias")))
    assert not alerta(parecida, "duracao_divergente")
    so_relato = processar(ficha({"Q01": "x"}), Extracao(duracao=Duracao(valor=3, unidade="dias")))
    assert so_relato.duracao.valor == 3


def test_alergia_do_relato_so_entra_sem_resposta_direta():
    ext = Extracao(alergias=Alergias(status=Status.PRESENTE, itens=["dipirona"]))
    saida = processar(ficha({"Q01": "x"}), ext)
    assert saida.alergias.itens == ["dipirona"] and "Q10" in saida.perguntas_pendentes
    negada = processar(ficha({"Q01": "x", "Q10": {"resposta": False}}), ext)
    assert negada.alergias.status == Status.NEGADO and alerta(negada, "alergia_divergente")


def test_falha_do_extrator_degrada_sem_perder_as_respostas():
    saida = processar(ficha({"Q01": "dor", "Q09": True}), erro=RuntimeError("Ollama fora do ar"))
    assert sinal(saida, NomeSinal.DISPNEIA).status == Status.PRESENTE  # resposta direta preservada
    assert alerta(saida, "extracao_falhou") and "Q01" in saida.perguntas_pendentes
    assert saida.queixa_principal is None


def test_avisos_de_descarte_do_extrator_ficam_visiveis():
    saida = processar(ficha({"Q01": "x"}), Extracao(avisos=["sinal 'x' descartado"]))
    assert alerta(saida, "extracao_avisos")


def test_contrato_do_extrator_e_aplicado_pelo_modelo():
    for ruim in ({"sinais": [Sinal(nome=NomeSinal.HIPOXEMIA, status=Status.PRESENTE, origem=Origem.EXTRAIDO_DO_RELATO)]},
                 {"sinais": [citado(NomeSinal.DOR, Status.NAO_SE_APLICA)]},
                 {"sinais": [Sinal(nome=NomeSinal.DOR, status=Status.PRESENTE, origem=Origem.RESPOSTA_DIRETA)]},
                 {"alergias": Alergias(status=Status.NEGADO)}):
        with pytest.raises(ValidationError):
            Extracao(**ruim)


# --- alertas clínicos -----------------------------------------------------------------------------

def test_febre_mascarada_por_antitermico():
    f = ficha({"R01": {"febre": True, "calafrios": False},
               "Q12": {"resposta": True, "classes": ["antitermico"]}}, temperatura=36.7)
    assert alerta(processar(f), "febre_mascarada")
    sem_remedio = ficha({"R01": {"febre": True, "calafrios": False}, "Q12": {"resposta": False}}, temperatura=36.7)
    assert not alerta(processar(sem_remedio), "febre_mascarada")


def test_paciente_nega_febre_mas_termometro_marca():
    saida = processar(ficha({"R01": {"febre": False, "calafrios": False}}, temperatura=39.2))
    assert alerta(saida, "febre_nao_referida")
    assert sinal(saida, NomeSinal.FEBRE_ATUAL).status == Status.PRESENTE


def test_regra_de_alerta_grave_avisa_a_enfermagem():
    saida = processar(ficha({"Q08": True}))
    assert [a.referencias for a in alerta(saida, "sinal_de_alerta")] == [["RC-01"]]
    assert not alerta(processar(ficha({"Q08": False})), "sinal_de_alerta")
