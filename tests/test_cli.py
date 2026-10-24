"""Linha de comando: contrato de stdout/stderr, códigos de saída e fichas de exemplo."""

import json

import pytest

from helpers import EXEMPLOS, RAIZ, rodar
from triagem import cli, relato
from triagem.schema import SaidaTriagem

FICHA = EXEMPLOS / "ficha_exemplo.json"
INVALIDAS = {"ficha_08_relato_201_falha.json": "Q01", "ficha_09_sem_idade_falha.json": "idade",
             "ficha_10_tipo_resposta_errado_falha.json": "Q09", "ficha_14_dado_contraditorio_falha.json": "Q11"}


def saida_json(r):
    return json.loads(r.stdout.decode("utf-8"))


def test_stdout_so_json_utf8_legivel_e_logs_no_stderr():
    r = rodar("triagem", FICHA)
    assert r.returncode == 0
    texto = r.stdout.decode("utf-8")
    saida = json.loads(texto)  # nada além do JSON no stdout
    assert "\\u00" not in texto and "há 2 horas" in texto  # acentos legíveis, sem escape ASCII
    assert texto.startswith("{\n  ") and texto.endswith("}\n")  # indentado
    assert saida["extrator"] == "mock" and saida["classificacao"]["provisoria"] is True
    assert b"[INFO]" in r.stderr and b"{" not in r.stderr


def test_saida_valida_contra_o_schema():
    SaidaTriagem.model_validate(saida_json(rodar("triagem", FICHA)))


def test_silencioso_corta_os_logs_de_info():
    assert b"[INFO]" not in rodar("triagem", FICHA, "-q").stderr


@pytest.mark.parametrize("arquivo", sorted(p.name for p in EXEMPLOS.glob("*.json") if "_falha" not in p.name))
def test_fichas_validas(arquivo):
    r = rodar("triagem", EXEMPLOS / arquivo, "-q")
    assert r.returncode == 0, r.stderr.decode("utf-8")
    SaidaTriagem.model_validate(saida_json(r))


@pytest.mark.parametrize("arquivo, pergunta", INVALIDAS.items())
def test_fichas_invalidas_dizem_qual_pergunta_falhou(arquivo, pergunta):
    r = rodar("triagem", EXEMPLOS / arquivo)
    assert r.returncode == 1 and r.stdout == b""
    assert pergunta in r.stderr.decode("utf-8")


def test_entrada_pelo_stdin_e_saida_em_arquivo(tmp_path):
    r = rodar("triagem", "-", "-q", entrada=FICHA.read_bytes())
    assert r.returncode == 0 and saida_json(r)["dados_atendente"]["idade"] == 58
    destino = tmp_path / "saida.json"
    r = rodar("triagem", FICHA, "-q", "--saida", destino)
    assert r.returncode == 0 and r.stdout == b""
    assert "há 2 horas" in destino.read_text(encoding="utf-8")


def test_ficha_com_bom_do_windows_e_aceita(tmp_path):
    arquivo = tmp_path / "bom.json"
    arquivo.write_bytes(b"\xef\xbb\xbf" + FICHA.read_bytes())
    assert rodar("triagem", arquivo, "-q").returncode == 0


def test_arquivo_inexistente_pasta_e_json_quebrado(tmp_path):
    for alvo, trecho in [(tmp_path / "nao_existe.json", b"n\xc3\xa3o encontrado"), (tmp_path, b"pasta")]:
        r = rodar("triagem", alvo)
        assert r.returncode == 2 and r.stdout == b"" and trecho in r.stderr
    quebrado = tmp_path / "q.json"
    quebrado.write_text("{", encoding="utf-8")
    r = rodar("triagem", quebrado)
    assert r.returncode == 2 and r.stdout == b"" and b"JSON" in r.stderr


def test_ficha_enorme_e_recusada(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "TAMANHO_MAXIMO", 100)
    grande = tmp_path / "grande.json"
    grande.write_text(json.dumps({"dados_atendente": {"idade": 30}, "respostas": {}, "x": "a" * 200}), encoding="utf-8")
    assert cli.main([str(grande), "-q"]) == 2


def test_extrator_desconhecido_e_rejeitado_pelo_argparse():
    assert rodar("triagem", FICHA, "--extrator", "outro").returncode == 2


def test_erro_interno_tem_codigo_proprio(monkeypatch, capsys):
    def quebra(*a, **k):
        raise RuntimeError("bug")

    monkeypatch.setattr(cli, "processar_ficha", quebra)
    assert cli.main([str(FICHA), "-q"]) == 3
    assert capsys.readouterr().out == ""


def test_ollama_indisponivel_degrada_e_a_ficha_sai_com_alerta(monkeypatch, capsys):
    """Com o modelo fora do ar o comando principal continua: respostas diretas + alerta."""
    monkeypatch.setenv("OLLAMA_HOST", "http://127.0.0.1:9")  # porta sem servidor
    assert cli.main([str(FICHA), "--extrator", "ollama", "-q"]) == 0
    saida = json.loads(capsys.readouterr().out)
    assert [a["codigo"] for a in saida["alertas"] if a["codigo"] == "extracao_falhou"]
    assert any(s["nome"] == "dispneia" and s["status"] == "presente" for s in saida["sinais"])


# --- comando de relato ---------------------------------------------------------------------

def test_relato_imprime_json_com_queixa_e_sinais():
    r = rodar("triagem.relato", "dor no peito há 2 horas")
    assert r.returncode == 0
    saida = saida_json(r)
    assert saida["queixa_principal"] == "dor no peito há 2 horas"
    assert saida["duracao"] == {"valor": 2.0, "unidade": "horas"}
    assert [(s["nome"], s["status"]) for s in saida["sinais"]] == [("dor", "presente")]
    assert "classificacao" not in saida and "pontuacao" not in saida  # só extração
    assert "há" in r.stdout.decode("utf-8")


def test_relato_pelo_stdin_evita_expor_o_texto_na_linha_de_comando():
    r = rodar("triagem.relato", "-", entrada="dor no peito há 2 horas".encode("utf-8"))
    assert r.returncode == 0 and saida_json(r)["relato_original"] == "dor no peito há 2 horas"


@pytest.mark.parametrize("texto", ["", "   ", "x" * 201])
def test_relato_vazio_ou_longo_falha_sem_stdout(texto):
    r = rodar("triagem.relato", texto)
    assert r.returncode == 1 and r.stdout == b"" and r.stderr


def test_relato_com_espacos_nas_pontas_e_200_caracteres_passa():
    r = rodar("triagem.relato", "  " + "x" * 200 + "  ")
    assert r.returncode == 0


def test_relato_ollama_fora_do_ar_tem_codigo_proprio(monkeypatch, capsys):
    monkeypatch.setenv("OLLAMA_HOST", "http://127.0.0.1:9")
    assert relato.main(["dor", "--extrator", "ollama", "-q"]) == 4
    assert capsys.readouterr().out == ""
