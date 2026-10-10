import json
import subprocess
import sys
from pathlib import Path

import pytest

from triagem.entrevista import FichaInvalida, processar_ficha
from triagem.sinais import NomeSinal, Origem, Status

RAIZ = Path(__file__).parent.parent
EXEMPLO = RAIZ / "exemplos" / "ficha_exemplo.json"


def _sinal(saida, nome):
    return next(s for s in saida.sinais if s.nome == nome)


def test_exemplo_completo_sem_pendencias():
    ficha = json.loads(EXEMPLO.read_text(encoding="utf-8"))
    saida = processar_ficha(ficha, mock=True)
    assert saida.perguntas_pendentes == []
    assert saida.pontuacao_provisoria is True
    assert saida.alergias_medicamentosas.status == Status.NEGADO
    assert _sinal(saida, NomeSinal.DOR).valor == 8


def test_nao_respondida_vira_nao_mencionado_e_pendente():
    saida = processar_ficha({"dados_atendente": {"idade": 30}, "respostas": {"P01": "dor"}})
    assert _sinal(saida, NomeSinal.FEBRE).status == Status.NAO_MENCIONADO
    assert "P09" in saida.perguntas_pendentes
    assert "P13" in saida.perguntas_pendentes
    assert saida.alergias_medicamentosas.status == Status.NAO_MENCIONADO
    # o mock preenche dor e dispneia a partir do relato
    dor = _sinal(saida, NomeSinal.DOR)
    assert dor.status == Status.PRESENTE and dor.origem == Origem.EXTRAIDO_DO_RELATO


def test_resposta_direta_prevalece_sobre_o_relato():
    ficha = {"dados_atendente": {"idade": 30},
             "respostas": {"P01": "falta de ar", "P06": False}}
    saida = processar_ficha(ficha)
    dispneia = _sinal(saida, NomeSinal.DISPNEIA)
    assert dispneia.status == Status.NEGADO
    assert dispneia.origem == Origem.RESPOSTA_DIRETA


def test_alergia_presente():
    ficha = {"dados_atendente": {"idade": 30},
             "respostas": {"P13": {"resposta": True, "texto": "dipirona, penicilina"}}}
    saida = processar_ficha(ficha)
    assert saida.alergias_medicamentosas.status == Status.PRESENTE
    assert saida.alergias_medicamentosas.medicamentos == ["dipirona", "penicilina"]


@pytest.mark.parametrize("ficha, trecho", [
    ({"respostas": {}}, "dados_atendente"),
    ({"dados_atendente": {}, "respostas": {}}, "idade"),
    ({"dados_atendente": {"idade": 30}, "respostas": {"P01": "x" * 201}}, "P01"),
    ({"dados_atendente": {"idade": 30}, "respostas": {"P04": {"resposta": True}}}, "P04"),
    ({"dados_atendente": {"idade": 30}, "respostas": {"P05": "cotovelo"}}, "P05"),
    ({"dados_atendente": {"idade": 30}, "respostas": {"P06": "talvez"}}, "P06"),
    ({"dados_atendente": {"idade": 30}, "respostas": {"P99": True}}, "P99"),
])
def test_ficha_invalida_aponta_a_pergunta(ficha, trecho):
    with pytest.raises(FichaInvalida) as exc:
        processar_ficha(ficha)
    assert trecho in str(exc.value)


def test_cli_stdout_so_json_e_exit_code_de_erro(tmp_path):
    ok = subprocess.run([sys.executable, "-m", "triagem", str(EXEMPLO), "--mock"],
                        capture_output=True, cwd=RAIZ)
    assert ok.returncode == 0
    json.loads(ok.stdout.decode("utf-8"))  # stdout é JSON puro
    assert "dor no peito" in ok.stdout.decode("utf-8")  # sem escape ASCII de acentos

    ruim = tmp_path / "ruim.json"
    ruim.write_text('{"dados_atendente": {"idade": 30}, "respostas": {"P06": "talvez"}}',
                    encoding="utf-8")
    erro = subprocess.run([sys.executable, "-m", "triagem", str(ruim), "--mock"],
                          capture_output=True, cwd=RAIZ)
    assert erro.returncode != 0
    assert erro.stdout == b""
    assert b"P06" in erro.stderr
