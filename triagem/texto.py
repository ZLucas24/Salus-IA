"""Utilitários de texto compartilhados por validação e extratores."""

import re
import unicodedata

MAX_RELATO = 200
MAX_ITENS = 10
MAX_ITEM_CHARS = 40

_NEGACAO = re.compile(r"\b(sem|nao|nada|nunca|nem|nenhum|nenhuma|ausencia)\b")
_PRONOMES = {"ela", "ele", "elas", "eles", "isso", "esse", "essa", "remedio", "remedios",
             "medicamento", "medicamentos", "nada", "tudo", "outros", "outras"}


def sem_acentos(texto: str) -> str:
    """Remove acentos mantendo o mesmo comprimento (índices comparáveis)."""
    saida = []
    for ch in texto:
        base = "".join(c for c in unicodedata.normalize("NFD", ch)
                       if not unicodedata.combining(c))
        saida.append(base[:1] or ch)
    return "".join(saida)


def tem_negacao(texto: str) -> bool:
    return bool(_NEGACAO.search(sem_acentos(texto).lower()))


def negacao_antes(texto_normalizado: str, posicao: int, janela: int = 3) -> bool:
    """Há palavra de negação nas últimas `janela` palavras antes de `posicao`?

    A negação vale para o que vem logo depois dela ("sem febre", "não tenho
    dor", "nada de dor"), não para o texto inteiro: "vomitando sem parar" e
    "não consigo parar de vomitar" não negam o vômito.
    """
    palavras = re.findall(r"\w+", texto_normalizado[:posicao])[-janela:]
    return any(_NEGACAO.fullmatch(p) for p in palavras)


def validar_relato(texto) -> str:
    """Única regra de validação do relato (usada pela ficha e pelo comando de relato).

    Devolve o texto sem espaços nas pontas ou levanta ValueError.
    """
    if not isinstance(texto, str):
        raise ValueError(f"o relato deve ser um texto; recebi {texto!r}")
    limpo = texto.strip()
    if not limpo:
        raise ValueError("o relato não pode ser vazio")
    if len(limpo) > MAX_RELATO:
        raise ValueError(f"o relato tem {len(limpo)} caracteres; o máximo é {MAX_RELATO}")
    return limpo


def normalizar_itens(texto: str | list[str]) -> list[str]:
    """Quebra um texto livre em itens curtos, sem repetição.

    Separa por vírgula, ponto e vírgula e " e ". Descarta pronomes soltos
    ("ela", "remédio"), limita quantidade e tamanho (texto livre pode carregar
    dado pessoal).
    """
    partes = texto if isinstance(texto, list) else re.split(r",|;|\be\b", str(texto))
    vistos, itens = set(), []
    for parte in partes:
        item = parte.strip().strip(".").strip()
        chave = sem_acentos(item).lower()
        if not item or chave in _PRONOMES or chave in vistos:
            continue
        vistos.add(chave)
        itens.append(item[:MAX_ITEM_CHARS])
        if len(itens) == MAX_ITENS:
            break
    return itens
