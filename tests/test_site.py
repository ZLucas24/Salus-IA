"""Site institucional (docs/): não carrega nada de fora e a política bate com o que o código faz."""

import re

import pytest

from helpers import RAIZ
from triagem.fila import JANELA_CHAMADA_S
from triagem.usuarios import BLOQUEIO_S, SESSAO_MAX_S, SESSAO_OCIOSA_S, TENTATIVAS

DOCS = RAIZ / "docs"
PAGINAS = ["index.html", "politica.html"]


def texto(nome):
    return (DOCS / nome).read_text(encoding="utf-8")


@pytest.mark.parametrize("nome", PAGINAS)
def test_pagina_nao_carrega_nada_de_outro_servidor(nome):
    html = texto(nome)
    # links para outros sites são permitidos (<a href>); carregar recursos de fora não
    for m in re.finditer(r'<(script|link|img|iframe|source|video|audio)\b[^>]*>', html):
        assert "http://" not in m.group(0) and "https://" not in m.group(0), m.group(0)
    assert "<script" not in html  # o site não usa JavaScript


@pytest.mark.parametrize("nome", PAGINAS)
def test_arquivos_referenciados_existem(nome):
    for ref in re.findall(r'(?:src|href)="([^"#:]+)"', texto(nome)):
        assert (DOCS / ref).is_file(), ref


def test_css_nao_carrega_nada_de_fora():
    css = texto("site.css")
    assert "@import" not in css and "url(" not in css


@pytest.mark.parametrize("nome", PAGINAS)
def test_nome_da_marca(nome):
    html = texto(nome)
    assert "salUS.ia" in html or 'n-ia">.ia' in html
    assert "salUS.ai" not in html and ".ai<" not in html


def test_politica_bate_com_o_codigo():
    """Se um prazo ou limite mudar no código, este teste lembra de atualizar a política."""
    p = re.sub(r"\s+", " ", texto("politica.html"))
    assert JANELA_CHAMADA_S == 600 and "Apagada 10 minutos depois de o paciente ser chamado" in p
    assert "Deixa de funcionar 10 minutos depois de o paciente ser chamado" in p
    assert SESSAO_OCIOSA_S == 3600 and SESSAO_MAX_S == 12 * 3600 and "1 hora sem uso ou 12 horas no total" in p
    assert TENTATIVAS == 5 and BLOQUEIO_S == 300 and "bloqueio de 5 minutos após 5 tentativas erradas" in p
    for compromisso in ("Nunca vendemos dados", "nunca é gravado", "não usa cookies", "ainda não foram validados",
                        "rascunho para revisão jurídica"):
        assert compromisso in p, compromisso


def test_cabecalhos_do_cloudflare_fecham_o_que_o_site_nao_usa():
    h = texto("_headers")
    assert "default-src 'none'" in h and "frame-ancestors 'none'" in h and "nosniff" in h
    assert "script-src" not in h  # o site não usa JavaScript


def test_politica_explica_a_hospedagem_e_o_uso_para_gestao():
    p = re.sub(r"\s+", " ", texto("politica.html"))
    assert "Cloudflare Pages" in p and "endereço IP" in p
    assert "números agregados" in p and "nunca a ficha, o relato ou o histórico de um paciente identificado" in p
    assert "não para punir profissionais individualmente" in p


def test_equipe_e_universidade_na_pagina_inicial():
    i = texto("index.html")
    for nome in ("Larissa Previde", "Anna Cassia Alves Bueno", "José Lucas Silva de Oliveira",
                 "Universidade Federal de Viçosa, Campus Rio Paranaíba"):
        assert nome in i, nome
