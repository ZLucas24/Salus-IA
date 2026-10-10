"""Testes sem rede: usam um ExtratorFalso no lugar de qualquer modelo."""

import json
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from triagem.entrevista import FichaInvalida, processar_ficha
from triagem.extracao import Extracao, Extrator, criar_extrator
from triagem.extrator_mock import MockExtrator
from triagem.pontuacao import pontuar
from triagem.schema import AlergiasMedicamentosas, Duracao, SaidaTriagem, Sinal
from triagem.sinais import NomeSinal, Origem, Status

RAIZ = Path(__file__).parent.parent
EXEMPLOS = RAIZ / "exemplos"


class ExtratorFalso(Extrator):
    nome = "falso"

    def __init__(self, extracao: Extracao | None = None):
        self.extracao = extracao or Extracao()
        self.chamadas: list[str] = []

    def extrair(self, relato: str) -> Extracao:
        self.chamadas.append(relato)
        return self.extracao


def citado(nome, status=Status.PRESENTE):
    return Sinal(nome=nome, status=status, origem=Origem.EXTRAIDO_DO_RELATO)


def ficha(respostas=None, idade=30):
    return {"dados_atendente": {"idade": idade}, "respostas": respostas or {}}


def sinal(saida, nome):
    return next(s for s in saida.sinais if s.nome == nome)


def processar(f, extracao=None):
    return processar_ficha(f, ExtratorFalso(extracao))


# --- schema ----------------------------------------------------------------

def test_schema_rejeita_relato_com_mais_de_200_caracteres():
    with pytest.raises(ValidationError):
        SaidaTriagem(relato_original="x" * 201, dados_atendente={"idade": 1}, extrator="falso")


def test_schema_rejeita_sinal_fora_do_vocabulario():
    with pytest.raises(ValidationError):
        Sinal(nome="alergia", status=Status.PRESENTE, origem=Origem.RESPOSTA_DIRETA)


def test_schema_rejeita_sinais_duplicados():
    s = citado(NomeSinal.DOR)
    with pytest.raises(ValidationError):
        SaidaTriagem(relato_original="", sinais=[s, s],
                     dados_atendente={"idade": 1}, extrator="falso")


def test_saida_cobre_todos_os_sinais_e_nenhum_e_alergia():
    saida = processar(ficha())
    assert [s.nome for s in saida.sinais] == list(NomeSinal)
    assert "alergia" not in {n.value for n in NomeSinal}


# --- mapeamento das respostas fechadas ------------------------------------

def test_respostas_fechadas_viram_sinais_com_origem_direta():
    saida = processar(ficha({
        "P03": True, "P04": {"resposta": True, "escala": 7}, "P05": "peito",
        "P06": False, "P07": {"ha_sangramento": True, "sangrando_agora": True},
        "P08": {"desmaiou_ou_confuso": True, "convulsao": False},
        "P09": {"resposta": True, "valor": 38.5}, "P10": True, "P11": False,
        "P12": {"gravida": True, "doenca_cronica": ["diabetes", "pulmao"]},
    }))
    esperado = {
        NomeSinal.INICIO_SUBITO: (Status.PRESENTE, None),
        NomeSinal.DOR: (Status.PRESENTE, 7),
        NomeSinal.LOCAL_DOR: (Status.PRESENTE, "peito"),
        NomeSinal.DISPNEIA: (Status.NEGADO, None),
        NomeSinal.SANGRAMENTO: (Status.PRESENTE, "ativo_agora"),
        NomeSinal.ALTERACAO_CONSCIENCIA: (Status.PRESENTE, None),
        NomeSinal.CONVULSAO: (Status.NEGADO, None),
        NomeSinal.FEBRE: (Status.PRESENTE, 38.5),
        NomeSinal.VOMITO_PERSISTENTE: (Status.PRESENTE, None),
        NomeSinal.TRAUMA: (Status.NEGADO, None),
        NomeSinal.GRAVIDEZ: (Status.PRESENTE, None),
        NomeSinal.DOENCA_CRONICA: (Status.PRESENTE, "diabetes, pulmao"),
    }
    for nome, (status, valor) in esperado.items():
        s = sinal(saida, nome)
        assert (s.status, s.valor) == (status, valor), nome
        assert s.origem == Origem.RESPOSTA_DIRETA, nome


def test_duracao_vem_da_p02():
    saida = processar(ficha({"P02": {"valor": 2, "unidade": "horas"}}))
    assert saida.duracao == Duracao(valor=2, unidade="horas")


@pytest.mark.parametrize("resposta, status, meds", [
    ({"resposta": False}, Status.NEGADO, []),
    ({"resposta": True, "texto": "dipirona; penicilina"}, Status.PRESENTE,
     ["dipirona", "penicilina"]),
])
def test_p13_preenche_alergias_fora_dos_sinais(resposta, status, meds):
    saida = processar(ficha({"P13": resposta}))
    assert saida.alergias_medicamentosas.status == status
    assert saida.alergias_medicamentosas.medicamentos == meds
    assert "P13" not in saida.perguntas_pendentes


# --- perguntas pendentes ---------------------------------------------------

def test_sem_respostas_tudo_nao_mencionado_e_pendente():
    saida = processar(ficha())
    assert all(s.status == Status.NAO_MENCIONADO for s in saida.sinais)
    assert saida.perguntas_pendentes == [f"P{i:02d}" for i in range(1, 14)]
    assert saida.alergias_medicamentosas.status == Status.NAO_MENCIONADO


def test_pergunta_respondida_sai_das_pendentes():
    saida = processar(ficha({"P06": False, "P13": {"resposta": False}}))
    assert "P06" not in saida.perguntas_pendentes
    assert "P13" not in saida.perguntas_pendentes
    assert "P09" in saida.perguntas_pendentes


def test_pergunta_nao_respondida_segue_pendente_mesmo_com_sinal_no_relato():
    ext = Extracao(sinais=[citado(NomeSinal.DISPNEIA)])
    saida = processar(ficha({"P01": "falta de ar"}), ext)
    assert sinal(saida, NomeSinal.DISPNEIA).origem == Origem.EXTRAIDO_DO_RELATO
    assert "P06" in saida.perguntas_pendentes


# --- extrator e divergência ---------------------------------------------------

def test_sinais_do_relato_entram_com_origem_extraido():
    ext = Extracao(queixa_principal="dor no peito",
                   sinais=[citado(NomeSinal.DOR), citado(NomeSinal.FEBRE, Status.NEGADO)])
    saida = processar(ficha({"P01": "dor no peito sem febre"}), ext)
    assert saida.queixa_principal == "dor no peito"
    assert (sinal(saida, NomeSinal.DOR).status, sinal(saida, NomeSinal.DOR).origem) == (
        Status.PRESENTE, Origem.EXTRAIDO_DO_RELATO)
    assert sinal(saida, NomeSinal.FEBRE).status == Status.NEGADO
    assert sinal(saida, NomeSinal.TRAUMA).status == Status.NAO_MENCIONADO
    assert saida.extrator == "falso"


def test_resposta_direta_prevalece_na_divergencia():
    ext = Extracao(sinais=[citado(NomeSinal.DISPNEIA, Status.PRESENTE)])
    saida = processar(ficha({"P01": "falta de ar", "P06": False}), ext)
    s = sinal(saida, NomeSinal.DISPNEIA)
    assert (s.status, s.origem) == (Status.NEGADO, Origem.RESPOSTA_DIRETA)


def test_duracao_e_alergia_diretas_prevalecem_sobre_o_relato():
    ext = Extracao(duracao=Duracao(valor=9, unidade="dias"),
                   alergias_medicamentosas=AlergiasMedicamentosas(
                       status=Status.PRESENTE, medicamentos=["dipirona"]))
    saida = processar(ficha({"P01": "x", "P02": {"valor": 2, "unidade": "horas"},
                             "P13": {"resposta": False}}), ext)
    assert saida.duracao.unidade.value == "horas"
    assert saida.alergias_medicamentosas.status == Status.NEGADO


def test_duracao_e_alergia_do_relato_entram_quando_nao_ha_resposta_direta():
    ext = Extracao(duracao=Duracao(valor=3, unidade="dias"),
                   alergias_medicamentosas=AlergiasMedicamentosas(
                       status=Status.PRESENTE, medicamentos=["dipirona"]))
    saida = processar(ficha({"P01": "x"}), ext)
    assert saida.duracao.valor == 3
    assert saida.alergias_medicamentosas.medicamentos == ["dipirona"]
    assert "P13" in saida.perguntas_pendentes  # ainda precisa da confirmação


def test_extrator_so_e_chamado_com_p01():
    falso = ExtratorFalso()
    processar_ficha(ficha(), falso)
    assert falso.chamadas == []
    processar_ficha(ficha({"P01": "dor"}), falso)
    assert falso.chamadas == ["dor"]


def test_mock_extrator_extrai_apenas_o_citado():
    ext = MockExtrator().extrair("Dor no peito há 2 horas, sem febre. Alérgico a dipirona e penicilina")
    por_nome = {s.nome: s.status for s in ext.sinais}
    assert por_nome == {NomeSinal.DOR: Status.PRESENTE, NomeSinal.FEBRE: Status.NEGADO}
    assert ext.duracao == Duracao(valor=2, unidade="horas")
    assert ext.alergias_medicamentosas.medicamentos == ["dipirona", "penicilina"]
    assert all(s.origem == Origem.EXTRAIDO_DO_RELATO for s in ext.sinais)


def test_criar_extrator():
    assert isinstance(criar_extrator("mock"), MockExtrator)
    with pytest.raises(ValueError):
        criar_extrator("inexistente")


# --- pontuação ------------------------------------------------------------------

def test_pontuar_stub_devolve_numero_fixo_e_resultado_e_provisorio():
    a = processar(ficha({"P06": True}))
    b = processar(ficha({"P06": False, "P10": True}))
    assert pontuar(a) == pontuar(b) == a.pontuacao
    assert isinstance(a.pontuacao, int)
    assert a.pontuacao_provisoria is True


# --- validação -----------------------------------------------------------------

@pytest.mark.parametrize("f, trecho", [
    ({"respostas": {}}, "dados_atendente"),
    (ficha(idade=None) | {"dados_atendente": {}}, "idade"),
    (ficha({"P01": "x" * 201}), "P01"),
    (ficha({"P02": {"valor": 2, "unidade": "luas"}}), "P02"),
    (ficha({"P04": {"resposta": True}}), "P04"),
    (ficha({"P05": "cotovelo"}), "P05"),
    (ficha({"P06": "talvez"}), "P06"),
    (ficha({"P09": {"resposta": True, "valor": 90}}), "P09"),
    (ficha({"P12": {"gravida": False, "doenca_cronica": ["gripe"]}}), "P12"),
    (ficha({"P13": {"resposta": True}}), "P13"),
    (ficha({"P99": True}), "P99"),
])
def test_ficha_invalida_aponta_a_pergunta(f, trecho):
    with pytest.raises(FichaInvalida) as exc:
        processar(f)
    assert trecho in str(exc.value)


def test_p01_com_exatamente_200_caracteres_e_aceita():
    saida = processar(ficha({"P01": "x" * 200}))
    assert len(saida.relato_original) == 200


# --- CLI -------------------------------------------------------------------------

def rodar(*args):
    return subprocess.run([sys.executable, "-m", "triagem", *map(str, args)],
                          capture_output=True, cwd=RAIZ)


def test_cli_stdout_so_json_utf8_e_logs_no_stderr():
    r = rodar(EXEMPLOS / "ficha_exemplo.json")
    assert r.returncode == 0
    texto = r.stdout.decode("utf-8")
    saida = json.loads(texto)  # nada além do JSON no stdout
    assert "\\u00" not in texto  # acentos sem escape ASCII
    assert saida["extrator"] == "mock"
    assert saida["pontuacao_provisoria"] is True
    assert b"[INFO]" in r.stderr


def test_cli_extrator_mock_explicito_e_desconhecido():
    ok = rodar(EXEMPLOS / "ficha_exemplo.json", "--extrator", "mock")
    assert ok.returncode == 0
    assert rodar(EXEMPLOS / "ficha_exemplo.json", "--extrator", "outro").returncode != 0


@pytest.mark.parametrize("arquivo", sorted(p.name for p in EXEMPLOS.glob("*.json")
                                          if not p.stem.endswith("_falha")))
def test_cli_fichas_validas(arquivo):
    r = rodar(EXEMPLOS / arquivo)
    assert r.returncode == 0, r.stderr.decode("utf-8")
    SaidaTriagem.model_validate(json.loads(r.stdout.decode("utf-8")))


@pytest.mark.parametrize("arquivo, pergunta", [
    ("ficha_08_p01_201_falha.json", "P01"),
    ("ficha_09_sem_idade_falha.json", "idade"),
    ("ficha_10_tipo_resposta_errado_falha.json", "P06"),
])
def test_cli_fichas_invalidas(arquivo, pergunta):
    r = rodar(EXEMPLOS / arquivo)
    assert r.returncode != 0
    assert r.stdout == b""
    assert pergunta in r.stderr.decode("utf-8")


def test_cli_arquivo_inexistente_e_json_quebrado(tmp_path):
    assert rodar(tmp_path / "nao_existe.json").returncode != 0
    quebrado = tmp_path / "q.json"
    quebrado.write_text("{", encoding="utf-8")
    r = rodar(quebrado)
    assert r.returncode != 0 and r.stdout == b""


def test_cli_casos_especificos():
    def saida(nome):
        return json.loads(rodar(EXEMPLOS / nome).stdout.decode("utf-8"))

    def sinais(s):
        return {x["nome"]: x for x in s["sinais"]}

    febre = sinais(saida("ficha_03_febre_com_valor.json"))["febre"]
    assert (febre["status"], febre["valor"]) == ("presente", 38.7)

    pend = saida("ficha_02_perguntas_sem_resposta.json")["perguntas_pendentes"]
    assert "P09" in pend and "P13" in pend and "P06" not in pend

    p13 = saida("ficha_04_alergia_p13.json")["alergias_medicamentosas"]
    assert p13 == {"status": "presente", "medicamentos": ["dipirona", "penicilina"]}

    so_relato = saida("ficha_05_alergia_so_na_extracao.json")
    assert so_relato["alergias_medicamentosas"]["medicamentos"] == ["dipirona"]
    assert "P13" in so_relato["perguntas_pendentes"]

    div = sinais(saida("ficha_06_divergencia_extracao_x_direta.json"))["dispneia"]
    assert (div["status"], div["origem"]) == ("negado", "resposta_direta")
