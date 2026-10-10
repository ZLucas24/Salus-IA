"""Carrega o questionário (dados) e converte cada resposta fechada em sinais."""

import json
from dataclasses import dataclass, field
from pathlib import Path

from triagem.schema import AlergiasMedicamentosas, Duracao, Sinal
from triagem.sinais import NomeSinal, Origem, Status

CAMINHO_QUESTIONARIO = Path(__file__).parent / "dados" / "questionario.json"


class ErroResposta(ValueError):
    """Resposta que não segue o tipo definido para a pergunta."""


@dataclass
class Interpretacao:
    sinais: list[Sinal] = field(default_factory=list)
    duracao: Duracao | None = None
    alergias: AlergiasMedicamentosas | None = None


def carregar_questionario() -> dict:
    with open(CAMINHO_QUESTIONARIO, encoding="utf-8") as f:
        return json.load(f)


# --- validação de valores primitivos -------------------------------------

def _bool(v, rotulo="resposta") -> bool:
    if isinstance(v, bool):
        return v
    raise ErroResposta(f"'{rotulo}' deve ser true ou false")


def _numero(v, rotulo, minimo=None, maximo=None):
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise ErroResposta(f"'{rotulo}' deve ser um número")
    if (minimo is not None and v < minimo) or (maximo is not None and v > maximo):
        raise ErroResposta(f"'{rotulo}' fora do intervalo permitido ({minimo} a {maximo})")
    return v


def _dict(v, obrigatorias, opcionais=()) -> dict:
    if not isinstance(v, dict):
        raise ErroResposta("a resposta deve ser um objeto JSON")
    faltando = [c for c in obrigatorias if c not in v]
    if faltando:
        raise ErroResposta(f"falta(m) o(s) campo(s): {', '.join(faltando)}")
    extras = set(v) - set(obrigatorias) - set(opcionais)
    if extras:
        raise ErroResposta(f"campo(s) desconhecido(s): {', '.join(sorted(extras))}")
    return v


def _sinal(nome: NomeSinal, presente: bool, valor=None) -> Sinal:
    return Sinal(
        nome=nome,
        status=Status.PRESENTE if presente else Status.NEGADO,
        valor=valor if presente else None,
        origem=Origem.RESPOSTA_DIRETA,
    )


# --- interpretação por tipo ----------------------------------------------

def interpretar(pergunta: dict, bruto) -> Interpretacao:
    """Valida `bruto` contra o tipo da pergunta e devolve os sinais/campos."""
    tipo = pergunta["tipo"]

    if tipo == "relato_breve":
        if not isinstance(bruto, str) or not bruto.strip():
            raise ErroResposta("o relato deve ser um texto não vazio")
        if len(bruto) > pergunta["max_caracteres"]:
            raise ErroResposta(
                f"o relato tem {len(bruto)} caracteres; o máximo é {pergunta['max_caracteres']}"
            )
        return Interpretacao()

    if tipo == "numero_unidade":
        d = _dict(bruto, ["valor", "unidade"])
        valor = _numero(d["valor"], "valor", minimo=0)
        if d["unidade"] not in pergunta["unidades"]:
            raise ErroResposta(f"'unidade' deve ser uma de: {', '.join(pergunta['unidades'])}")
        return Interpretacao(duracao=Duracao(valor=valor, unidade=d["unidade"]))

    if tipo == "sim_nao":
        nome = NomeSinal(pergunta["preenche"][0]["nome"])
        return Interpretacao(sinais=[_sinal(nome, _bool(bruto, "sim/não"))])

    if tipo == "sim_nao_escala":
        d = _dict(bruto, ["resposta"], ["escala"])
        tem = _bool(d["resposta"])
        escala = None
        if tem:
            if "escala" not in d:
                raise ErroResposta("informe 'escala' (0 a 10) quando a resposta é sim")
            esc = pergunta["escala"]
            escala = _numero(d["escala"], "escala", esc["min"], esc["max"])
        return Interpretacao(sinais=[_sinal(NomeSinal.DOR, tem, escala)])

    if tipo == "opcao":
        if bruto not in pergunta["opcoes"]:
            raise ErroResposta(f"deve ser uma de: {', '.join(pergunta['opcoes'])}")
        return Interpretacao(sinais=[_sinal(NomeSinal.LOCAL_DOR, True, bruto)])

    if tipo == "sim_nao_duplo":
        d = _dict(bruto, ["ha_sangramento"], ["sangrando_agora"])
        ha = _bool(d["ha_sangramento"], "ha_sangramento")
        agora = _bool(d["sangrando_agora"], "sangrando_agora") if "sangrando_agora" in d else False
        if agora and not ha:
            raise ErroResposta("sangrando_agora=true é incompatível com ha_sangramento=false")
        return Interpretacao(
            sinais=[_sinal(NomeSinal.SANGRAMENTO, ha, "ativo_agora" if agora else None)]
        )

    if tipo == "sim_nao_multiplo":
        d = _dict(bruto, pergunta["partes"])
        return Interpretacao(sinais=[
            _sinal(NomeSinal.ALTERACAO_CONSCIENCIA,
                   _bool(d["desmaiou_ou_confuso"], "desmaiou_ou_confuso")),
            _sinal(NomeSinal.CONVULSAO, _bool(d["convulsao"], "convulsao")),
        ])

    if tipo == "sim_nao_numero":
        d = _dict(bruto, ["resposta"], ["valor"])
        tem = _bool(d["resposta"])
        temperatura = None
        if tem and d.get("valor") is not None:
            temperatura = _numero(d["valor"], "valor", 30, 45)
        return Interpretacao(sinais=[_sinal(NomeSinal.FEBRE, tem, temperatura)])

    if tipo == "sim_nao_opcoes":
        d = _dict(bruto, pergunta["partes"])
        gravida = _bool(d["gravida"], "gravida")
        doencas = d["doenca_cronica"]
        validas = pergunta["opcoes_doenca_cronica"]
        if not isinstance(doencas, list) or any(x not in validas for x in doencas):
            raise ErroResposta(
                f"'doenca_cronica' deve ser uma lista com itens de: {', '.join(validas)}"
            )
        return Interpretacao(sinais=[
            _sinal(NomeSinal.GRAVIDEZ, gravida),
            _sinal(NomeSinal.DOENCA_CRONICA, bool(doencas), ", ".join(doencas)),
        ])

    if tipo == "sim_nao_texto":
        d = _dict(bruto, ["resposta"], ["texto"])
        if not _bool(d["resposta"]):
            return Interpretacao(alergias=AlergiasMedicamentosas(status=Status.NEGADO))
        texto = d.get("texto")
        itens = texto if isinstance(texto, list) else str(texto or "").replace(";", ",").split(",")
        medicamentos = [m.strip() for m in itens if isinstance(m, str) and m.strip()]
        if not medicamentos:
            raise ErroResposta("informe 'texto' com o(s) medicamento(s) quando a resposta é sim")
        return Interpretacao(
            alergias=AlergiasMedicamentosas(status=Status.PRESENTE, medicamentos=medicamentos)
        )

    raise ErroResposta(f"tipo de pergunta desconhecido no questionário: {tipo}")
