"""Aferições do atendente: validação, sinais derivados e o que falta medir.

Aferição ausente é "não aferida", nunca "normal". Os limites vêm de
`dados/regras.json` (propostas da equipe, sem revisão clínica).
"""

from pydantic import ValidationError

from triagem.questionario import carregar_questionario
from triagem.regras import carregar_regras
from triagem.schema import Alerta, DadosAtendente, Sinal
from triagem.sinais import NomeSinal, Origem, Status

CAMPOS_PLAUSIVEIS = ("temperatura", "saturacao", "pressao_sistolica", "pressao_diastolica",
                     "frequencia_cardiaca", "frequencia_respiratoria", "glicemia", "glasgow")


def validar_dados_atendente(bruto) -> tuple[DadosAtendente | None, list[str]]:
    """Valida cadastro e aferições. Devolve (dados, erros); a idade é obrigatória."""
    if not isinstance(bruto, dict):
        return None, ["dados_atendente: objeto obrigatório (com pelo menos 'idade')"]
    try:
        dados = DadosAtendente(**bruto)
    except ValidationError as e:
        erros = []
        for err in e.errors():
            campo = ".".join(str(p) for p in err["loc"]) or "dados_atendente"
            msg = "campo obrigatório" if err["type"] == "missing" else err["msg"]
            erros.append(f"dados_atendente.{campo}: {msg}")
        return None, erros

    plaus = carregar_regras()["plausibilidade"]
    erros = []
    if not plaus["idade"][0] <= dados.idade <= plaus["idade"][1]:
        erros.append(f"dados_atendente.idade: {dados.idade} fora do intervalo plausível")
    for campo in CAMPOS_PLAUSIVEIS:
        v = getattr(dados, campo)
        chave = campo
        if v is not None and not plaus[chave][0] <= v <= plaus[chave][1]:
            erros.append(f"dados_atendente.{campo}: recebi {v!r}; o intervalo plausível é "
                         f"{plaus[chave][0]} a {plaus[chave][1]}")
    if (dados.pressao_sistolica is not None and dados.pressao_diastolica is not None
            and dados.pressao_sistolica < dados.pressao_diastolica):
        erros.append("dados_atendente.pressao_sistolica: menor que a diastólica "
                     f"({dados.pressao_sistolica} < {dados.pressao_diastolica})")
    if (dados.pressao_sistolica is None) != (dados.pressao_diastolica is None):
        erros.append("dados_atendente: informe pressão sistólica e diastólica juntas")
    return (None, erros) if erros else (dados, [])


def _sinal(nome: NomeSinal, presente: bool, valor: float) -> Sinal:
    return Sinal(nome=nome, status=Status.PRESENTE if presente else Status.NEGADO,
                 valor=float(valor), origem=Origem.MEDIDO_PELO_ATENDENTE)


def sinais_medidos(dados: DadosAtendente) -> tuple[dict[NomeSinal, Sinal], list[Alerta]]:
    """Converte aferições em sinais, aplicando os limites do arquivo de regras."""
    lim = carregar_regras()["limites_aferidos"]
    adulto = dados.idade >= lim["idade_adulto"]
    sinais: dict[NomeSinal, Sinal] = {}
    alertas: list[Alerta] = []

    if dados.temperatura is not None:
        corte = lim["febre_adulto_c"] if adulto else lim["febre_crianca_c"]
        sinais[NomeSinal.FEBRE_ATUAL] = _sinal(
            NomeSinal.FEBRE_ATUAL, dados.temperatura >= corte, dados.temperatura)
    if dados.glasgow is not None:
        sinais[NomeSinal.GLASGOW_REDUZIDO] = _sinal(
            NomeSinal.GLASGOW_REDUZIDO, dados.glasgow < lim["glasgow_abaixo"], dados.glasgow)

    adultos = [
        (NomeSinal.HIPOXEMIA, dados.saturacao, lambda v: v < lim["hipoxemia_saturacao_abaixo"]),
        (NomeSinal.TAQUICARDIA, dados.frequencia_cardiaca, lambda v: v > lim["taquicardia_fc_acima"]),
        (NomeSinal.TAQUIPNEIA, dados.frequencia_respiratoria, lambda v: v > lim["taquipneia_fr_acima"]),
        (NomeSinal.HIPOTENSAO, dados.pressao_sistolica, lambda v: v < lim["hipotensao_pas_abaixo"]),
        (NomeSinal.GLICEMIA_ALTERADA, dados.glicemia,
         lambda v: v < lim["glicemia_abaixo"] or v > lim["glicemia_acima"]),
    ]
    medidas = [(n, v) for n, v, _ in adultos if v is not None]
    if adulto:
        for nome, valor, avalia in adultos:
            if valor is not None:
                sinais[nome] = _sinal(nome, avalia(valor), valor)
    elif medidas:
        alertas.append(Alerta(
            codigo="limites_pediatricos",
            mensagem="Paciente com menos de 18 anos: os limites de saturação, frequências, "
                     "pressão e glicemia ainda não têm tabela pediátrica e não foram avaliados.",
            referencias=[n.value for n, _ in medidas]))
    return sinais, alertas


def afericoes_faltando(dados: DadosAtendente, sinais: dict[NomeSinal, Sinal]) -> list[str]:
    """Ids (E01...) das aferições essenciais ou condicionais ainda não registradas."""
    regras = carregar_regras()
    ids = {a["campo"]: a["id"] for a in carregar_questionario()["afericoes"]}
    medido = {
        "temperatura": dados.temperatura is not None,
        "saturacao": dados.saturacao is not None,
        "pressao": dados.pressao_sistolica is not None and dados.pressao_diastolica is not None,
        "frequencia_cardiaca": dados.frequencia_cardiaca is not None,
        "frequencia_respiratoria": dados.frequencia_respiratoria is not None,
        "glicemia": dados.glicemia is not None,
        "glasgow": dados.glasgow is not None,
    }

    def presente(nome: NomeSinal) -> bool:
        s = sinais.get(nome)
        return s is not None and s.status == Status.PRESENTE

    necessarias = list(regras["afericoes_essenciais"])
    consciencia = presente(NomeSinal.ALTERACAO_CONSCIENCIA)
    diabetes = "diabetes" in (sinais.get(NomeSinal.DOENCA_CRONICA).itens
                              if NomeSinal.DOENCA_CRONICA in sinais else [])
    if consciencia or diabetes:
        necessarias.append("glicemia")
    if consciencia:
        necessarias.append("glasgow")
    if presente(NomeSinal.DISPNEIA):
        necessarias.append("frequencia_respiratoria")
    return [ids[c] for c in dict.fromkeys(necessarias) if not medido[c]]
