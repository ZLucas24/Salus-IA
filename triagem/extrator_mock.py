"""Extrator simulado: regras de palavras-chave, sem rede e sem modelo.

Só serve para exercitar o fluxo e dar uma linha de base; não é uma extração
real. Regras de segurança do contrato:
  - a negação vale por oração ("sem X", "não tenho X", "nem X"), nunca pelo texto inteiro;
  - se o mesmo sinal aparece presente e negado, vence o presente;
  - alergia só é extraída quando afirmada; "sem alergia" é ignorado.
"""

import re

from triagem.extracao import Extracao, Extrator
from triagem.schema import Alergias, Duracao, Sinal
from triagem.sinais import NomeSinal, Origem, Queixa, Status
from triagem.texto import negacao_antes, normalizar_itens, sem_acentos, tem_negacao

# sinal -> expressão (sobre texto minúsculo e sem acentos)
PALAVRAS: dict[NomeSinal, str] = {
    NomeSinal.DOR: r"\bdor(es)?\b|\bdoendo\b|\bdoi\b|\bdoe\b|dolorid",
    NomeSinal.DISPNEIA: r"falta de ar|dificuldade (para|de|em) respirar|sufoc|dispneia|ofegan",
    NomeSinal.ALTERACAO_CONSCIENCIA: r"desmai|confus|apagar|apagou|perdi os sentidos|desacordad",
    NomeSinal.INICIO_SUBITO: r"de repente|subito|do nada|comecou agora",
    NomeSinal.PIORA_PROGRESSIVA: r"piorando|piorou|cada vez pior|piora rapida",
    NomeSinal.DOR_EM_APERTO: r"\baperto\b|peso no peito|opressao",
    NomeSinal.IRRADIACAO: r"irradia|espalha|vai para o (braco|pescoco|costas|mandibula)",
    NomeSinal.SUOR_FRIO_ENJOO_TONTURA: r"suor frio|suando frio",
    NomeSinal.FEBRE_REFERIDA: r"febre|febril",
    NomeSinal.CALAFRIOS: r"calafrio",
    NomeSinal.VOMITO: r"vomit",
    NomeSinal.SANGUE_VOMITO_FEZES: (r"sangue (no|na|nas|nos|do) (vomito|fezes|coco)|vomit\w* (com )?sangue"
                                    r"|fezes com sangue|melena"),
    NomeSinal.TOSSE_COM_SANGUE: r"(tosse|escarro|catarro) com sangue|tossindo sangue",
    NomeSinal.CHIADO: r"chiado|chiando",
    NomeSinal.DIARREIA: r"diarreia",
    NomeSinal.USO_ANTICOAGULANTE: r"anticoagulante|varfarina|marevan|rivaroxabana|afina(r)? o sangue",
    NomeSinal.USO_INSULINA: r"insulina",
    NomeSinal.DOENCA_CRONICA: (r"diabet|hipertens|pressao alta|\basma\b|cardiopat|problema (no|do) coracao"
                               r"|doenca renal|insuficiencia"),
    NomeSinal.GRAVIDEZ_POSSIVEL: r"gravida|gestante|gravidez",
    NomeSinal.AMAMENTANDO: r"amament",
    NomeSinal.ABDOME_RIGIDO_DISTENDIDO: r"(barriga|abdomen|abdome) (dura|duro|inchada|inchado|distendid)",
    NomeSinal.DOR_ABDOMINAL: (r"dor (na|de|no|em) (barriga|abdomen|abdome|estomago|ventre)|dor abdominal"
                              r"|barriga (doendo|dolorida)|colica"),
    NomeSinal.ANTITERMICO_RECENTE: (r"tomei (dipirona|paracetamol|tylenol|novalgina|ibuprofeno)"
                                    r"|remedio para (a )?febre|antitermico"),
    NomeSinal.ALTERACAO_URINARIA: r"dor ao urinar|ardencia ao urinar|urina com sangue",
    NomeSinal.CONTATO_OU_VIAGEM: r"viajei|viagem|contato com (alguem|pessoa)",
}
_DOENCAS = {"diabet": "diabetes", "hipertens": "hipertensao", "pressao alta": "hipertensao",
            "asma": "pneumopatia", "cardiopat": "cardiopatia", "coracao": "cardiopatia",
            "renal": "renopatia"}

_QUEIXAS = {
    Queixa.DOR_TORACICA: (r"(dor|aperto|pontada|peso|desconforto|opressao)[^,.;]*\b(peito|torax|toracic)"
                          r"|\b(peito|torax)\b[^,.;]*\b(dor|doendo|aperto)"),
    Queixa.DOR_ABDOMINAL: (r"(dor|doendo|colica)[^,.;]*\b(barriga|abdom|estomago|ventre)"
                           r"|\b(barriga|abdom|estomago)[^,.;]*\b(dor|doendo)"),
    Queixa.RESPIRATORIO_FEBRE: r"febre|tosse|falta de ar|gripe|catarro|chiado|resfriado|garganta",
}

_NUMEROS = {"um": 1, "uma": 1, "dois": 2, "duas": 2, "tres": 3, "quatro": 4, "cinco": 5,
            "seis": 6, "sete": 7, "oito": 8, "nove": 9, "dez": 10, "meia": 0.5}
_UNIDADES = {"minuto": "minutos", "minutos": "minutos", "min": "minutos", "hora": "horas",
             "horas": "horas", "h": "horas", "dia": "dias", "dias": "dias", "semana": "semanas",
             "semanas": "semanas", "mes": "meses", "meses": "meses", "ano": "anos", "anos": "anos"}
_DURACAO = re.compile(
    r"\b(?:ha|faz|fazem)\s+(?:cerca de |uns |umas |mais de )?(\d+|" + "|".join(_NUMEROS) + r")\s*"
    r"(minutos?|min|horas?|h|dias?|semanas?|meses|mes|anos?)\b")
_ALERGIA = re.compile(r"alergi\w*\s+(?:a|ao|aos|as)\s+(.+)|alergic[oa]s?\s+(?:a|ao|aos|as)\s+(.+)")
_SEPARADOR = re.compile(r"[,.;:!?]|\bmas\b|\bporem\b|\be\b")


def _oracoes(original: str, normal: str) -> list[tuple[str, str]]:
    """Divide o texto em orações; devolve (trecho original, trecho normalizado)."""
    partes, inicio = [], 0
    for m in list(_SEPARADOR.finditer(normal)) + [None]:
        fim = m.start() if m else len(normal)
        trecho = normal[inicio:fim]
        if trecho.strip():
            partes.append((original[inicio:fim].strip(), trecho.strip()))
        inicio = m.end() if m else len(normal)
    return partes


_NAO_E_MEDICAMENTO = {"tenho", "estou", "sinto", "tive", "com", "mas", "dor", "febre", "tosse", "sou",
                      "ando", "fiquei", "tomei", "e"}


def _alergia(original: str, normal: str) -> list[str] | None:
    """Itens de alergia afirmada ("alérgico a X, Y e Z"); None se não houver ou se for negada."""
    itens: list[str] | None = None
    for m in _ALERGIA.finditer(normal):
        if negacao_antes(normal, m.start()):
            continue
        g = 1 if m.group(1) else 2
        resto = re.split(r"[.;!?]|mas", original[m.start(g):m.end(g)])[0]
        aceitos = []
        for item in normalizar_itens(resto):
            palavras = sem_acentos(item).lower().split()
            if len(palavras) > 2 or palavras[0] in _NAO_E_MEDICAMENTO:
                break  # começou outra frase ("e tenho dor")
            aceitos.append(item)
        itens = (itens or []) + aceitos
    return itens


def _duracao(normal: str) -> tuple[Duracao | None, list[str]]:
    achadas = []
    for m in _DURACAO.finditer(normal):
        n = _NUMEROS.get(m.group(1)) or float(m.group(1))
        achadas.append(Duracao(valor=n, unidade=_UNIDADES[m.group(2)]))
    if "desde ontem" in normal:
        achadas.append(Duracao(valor=1, unidade="dias"))
    avisos = []
    if len({(d.valor, d.unidade) for d in achadas}) > 1:
        avisos.append("o relato cita mais de uma duração; foi usada a primeira")
    return (achadas[0] if achadas else None), avisos


class MockExtrator(Extrator):
    nome = "mock"

    def extrair(self, relato: str) -> Extracao:
        original = relato.strip()
        normal = sem_acentos(original).lower()
        achados: dict[NomeSinal, Sinal] = {}
        queixas: set[Queixa] = set()
        alergia_itens = _alergia(original, normal)
        queixas: set[Queixa] = set()
        primeira_queixa = None

        for trecho, oracao in _oracoes(original, normal):
            nega = tem_negacao(oracao)
            if _ALERGIA.search(oracao):
                continue  # a frase de alergia já foi tratada acima
            for nome, padrao in PALAVRAS.items():
                ocorrencias = list(re.finditer(padrao, oracao))
                if not ocorrencias:
                    continue
                # presente vence negado: basta uma ocorrência não negada
                negado = all(negacao_antes(oracao, m.start()) for m in ocorrencias)
                status = Status.NEGADO if negado else Status.PRESENTE
                atual = achados.get(nome)
                if atual is not None and atual.status == Status.PRESENTE:
                    continue
                itens = []
                if nome == NomeSinal.DOENCA_CRONICA and status == Status.PRESENTE:
                    itens = sorted({v for k, v in _DOENCAS.items() if k in normal})
                achados[nome] = Sinal(nome=nome, status=status, itens=itens, trecho=trecho,
                                      origem=Origem.EXTRAIDO_DO_RELATO)
            if not nega:
                queixas |= {q for q, p in _QUEIXAS.items() if re.search(p, oracao)}
            if primeira_queixa is None:
                primeira_queixa = trecho

        duracao, avisos = _duracao(normal)
        if not queixas:
            queixas = {Queixa.OUTRA} if any(s.status == Status.PRESENTE for s in achados.values()) \
                else {Queixa.INDEFINIDA}
        return Extracao(
            queixa_principal=_resumir(primeira_queixa),
            queixas=sorted(queixas, key=lambda q: q.value),
            duracao=duracao,
            sinais=list(achados.values()),
            alergias=(Alergias(status=Status.PRESENTE, itens=alergia_itens)
                      if alergia_itens is not None else None),
            avisos=avisos,
        )


def _resumir(trecho: str | None, limite: int = 60) -> str | None:
    if not trecho:
        return None
    texto = trecho.lower().strip(" .!?,;")
    if len(texto) > limite:
        texto = texto[:limite].rsplit(" ", 1)[0]  # corta em fim de palavra
    return texto or None
