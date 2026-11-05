"""Fluxo da entrevista, em etapas pequenas e testáveis.

ficha -> validar -> interpretar respostas -> extrair relato -> mesclar sinais
-> pendências e alertas -> pontuar.

Princípios: a resposta direta prevalece sobre o relato (mas a divergência vira
alerta visível); falha do extrator não derruba a ficha; dados desconhecidos
nunca viram "não".
"""

import json
import logging
from dataclasses import dataclass, field

from triagem.afericoes import afericoes_faltando, sinais_medidos, validar_dados_atendente
from triagem.extracao import Extracao, Extrator
from triagem.pontuacao import pontuar
from triagem.questionario import (PRIORIDADE, ErroResposta, carregar_questionario, interpretar,
                                  perguntas_por_id, pergunta_se_aplica)
from triagem.regras import carregar_regras
from triagem.schema import (Alergias, Alerta, DadosAtendente, Duracao, Resposta, SaidaTriagem,
                            Sinal)
from triagem.sinais import Cor, NomeSinal, Origem, Queixa, Status

log = logging.getLogger("triagem")

CHAVES_DA_FICHA = {"dados_atendente", "respostas"}
# rotas determinísticas: sinal presente -> módulo de perguntas a ativar
MODULO_POR_SINAL = {
    NomeSinal.DOR_EM_APERTO: "dor_toracica",
    NomeSinal.SUOR_FRIO_ENJOO_TONTURA: "dor_toracica",
    NomeSinal.DOR_ABDOMINAL: "dor_abdominal",
    NomeSinal.VOMITO: "dor_abdominal",
    NomeSinal.SANGUE_VOMITO_FEZES: "dor_abdominal",
    NomeSinal.ABDOME_RIGIDO_DISTENDIDO: "dor_abdominal",
    NomeSinal.FEBRE_REFERIDA: "respiratorio_febre",
    NomeSinal.FEBRE_ATUAL: "respiratorio_febre",
    NomeSinal.DISPNEIA: "respiratorio_febre",
    NomeSinal.HIPOXEMIA: "respiratorio_febre",
    NomeSinal.CHIADO: "respiratorio_febre",
    NomeSinal.TOSSE_COM_SANGUE: "respiratorio_febre",
}
MINUTOS = {"minutos": 1, "horas": 60, "dias": 1440, "semanas": 10080, "meses": 43200, "anos": 525600}


class FichaInvalida(Exception):
    def __init__(self, erros: list[str]):
        super().__init__("; ".join(erros))
        self.erros = erros


@dataclass
class Respondidas:
    """Resultado da interpretação das respostas fechadas."""

    sinais: dict[NomeSinal, Sinal] = field(default_factory=dict)
    respostas: list[Resposta] = field(default_factory=list)
    respondidas: set[str] = field(default_factory=set)
    incompletas: dict[str, list[str]] = field(default_factory=dict)
    desconhecidas: dict[str, list[str]] = field(default_factory=dict)
    nao_se_aplica: set[str] = field(default_factory=set)
    relato: str = ""
    duracao: Duracao | None = None
    alergias: Alergias | None = None


# --- 1. validação -----------------------------------------------------------------

def validar_ficha(ficha) -> tuple[DadosAtendente, dict, list[str]]:
    """Valida a estrutura da ficha e os dados do atendente. Devolve (dados, respostas, erros)."""
    if not isinstance(ficha, dict):
        return None, {}, ["a ficha deve ser um objeto JSON"]
    erros = []
    extras = set(ficha) - CHAVES_DA_FICHA
    if extras:
        erros.append(f"campo(s) desconhecido(s) na ficha: {', '.join(sorted(extras))}")
    dados, e = validar_dados_atendente(ficha.get("dados_atendente"))
    erros += e
    brutas = ficha.get("respostas", {})
    if not isinstance(brutas, dict):
        erros.append('respostas: deve ser um objeto {"Q01": ..., ...}')
        brutas = {}
    conhecidas = perguntas_por_id()
    erros += [f"{pid}: pergunta inexistente no questionário" for pid in brutas
              if pid not in conhecidas]
    return dados, brutas, erros


# --- 2. respostas fechadas -> sinais ----------------------------------------------------

def interpretar_respostas(dados: DadosAtendente | None, brutas: dict) -> tuple[Respondidas, list[str]]:
    r, erros = Respondidas(), []
    for pid, pergunta in perguntas_por_id().items():
        bruto = brutas.get(pid)
        if bruto is None:
            if not pergunta_se_aplica(pergunta, dados):
                r.nao_se_aplica.add(pid)
            continue
        try:
            i = interpretar(pergunta, bruto)
        except ErroResposta as e:
            erros.append(f"{pid} ({pergunta['texto']}): {e}")
            continue
        r.respondidas.add(pid)
        r.respostas.append(Resposta(
            id_pergunta=pid,
            resposta_bruta=bruto if isinstance(bruto, str) else json.dumps(bruto, ensure_ascii=False)))
        r.sinais.update(i.sinais)
        if i.incompleta:
            r.incompletas[pid] = i.incompleta
        if i.desconhecidos:
            r.desconhecidas[pid] = i.desconhecidos
        r.relato = i.relato or r.relato
        r.duracao = i.duracao or r.duracao
        r.alergias = i.alergias or r.alergias
    return r, erros


# --- 3. extração do relato (com degradação) ---------------------------------------------

def extrair_relato(relato: str, extrator: Extrator) -> tuple[Extracao | None, list[Alerta]]:
    """Chama o extrator. Qualquer falha vira alerta e a ficha segue só com as respostas diretas."""
    if not relato:
        return None, []
    try:
        extracao = extrator.extrair(relato)
    except Exception as e:  # ErroExtracao, rede, pacote ausente...
        log.error("extração do relato falhou: %s", e)
        return None, [Alerta(
            codigo="extracao_falhou",
            mensagem=f"Não foi possível interpretar o relato ({e}). A ficha foi montada só com "
                     "as respostas diretas; revise o relato manualmente.",
            referencias=["Q01"])]
    alertas = []
    if extracao.avisos:
        alertas.append(Alerta(codigo="extracao_avisos",
                              mensagem="O extrator descartou itens inválidos: " + "; ".join(extracao.avisos),
                              referencias=["Q01"]))
    return extracao, alertas


# --- 4. mesclagem --------------------------------------------------------------------------

def _minutos(d: Duracao) -> float:
    return d.valor * MINUTOS[d.unidade.value]


def mesclar_sinais(diretos: dict[NomeSinal, Sinal], medidos: dict[NomeSinal, Sinal],
                   extraidos: dict[NomeSinal, Sinal]) -> tuple[list[Sinal], list[Alerta], set[NomeSinal]]:
    """Um sinal por nome. Resposta direta e aferição prevalecem sobre o relato.

    Devolve (sinais, alertas de divergência, sinais divergentes).
    """
    sinais, alertas, divergentes = [], [], set()
    for nome in NomeSinal:
        direto = diretos.get(nome) or medidos.get(nome)
        relato = extraidos.get(nome)
        definitivo = direto is not None and direto.status in (Status.PRESENTE, Status.NEGADO)
        if definitivo:
            sinal = direto
            if relato is not None and relato.status in (Status.PRESENTE, Status.NEGADO) \
                    and relato.status != direto.status:
                divergentes.add(nome)
                sinal = direto.model_copy(update={"status_no_relato": relato.status,
                                                  "trecho": relato.trecho})
        elif relato is not None and (direto is None or direto.status in (Status.NAO_SABE, Status.RECUSOU)):
            sinal = relato  # sem resposta definitiva, vale o que o relato disse
        elif direto is not None:
            sinal = direto
        else:
            sinal = Sinal(nome=nome, status=Status.NAO_MENCIONADO, origem=Origem.NENHUMA)
        sinais.append(sinal)
    if divergentes:
        nomes = sorted(n.value for n in divergentes)
        alertas.append(Alerta(
            codigo="divergencia",
            mensagem="O relato e a resposta direta divergem; vale a resposta direta, mas confirme com o "
                     "paciente (a pontuação considera o sinal citado no relato): " + ", ".join(nomes),
            referencias=nomes))
    return sinais, alertas, divergentes


# --- 5. módulos, pendências e alertas -----------------------------------------------------------

def modulos_ativos(respostas: Respondidas, extracao: Extracao | None,
                   sinais: list[Sinal]) -> list[str]:
    q = carregar_questionario()
    perguntas = perguntas_por_id()
    ativos = {perguntas[pid]["modulo"] for pid in respostas.respondidas if perguntas[pid].get("modulo")}
    if extracao:
        ativos |= {c.value for c in extracao.queixas if c.value in q["modulos"]}
    ativos |= {MODULO_POR_SINAL[s.nome] for s in sinais
               if s.nome in MODULO_POR_SINAL and s.status == Status.PRESENTE}
    return [m for m in q["modulos"] if m in ativos]


def calcular_pendencias(dados: DadosAtendente, respostas: Respondidas, ativos: list[str],
                        divergentes: set[NomeSinal], extracao_falhou: bool) -> list[str]:
    """Ids em ordem de prioridade (segurança, núcleo, módulo). Complementares não entram."""
    ordem = {pid: i for i, pid in enumerate(perguntas_por_id())}
    pendentes = []
    for pid, p in perguntas_por_id().items():
        if p["obrigatoriedade"] == "C" or not pergunta_se_aplica(p, dados):
            continue
        if p.get("modulo") and p["modulo"] not in ativos:
            continue
        nomes = {NomeSinal(s["nome"]) for s in p.get("sinais", [])}
        revisar = pid in respostas.incompletas or bool(nomes & divergentes) \
            or (pid == "Q01" and extracao_falhou)
        if pid not in respostas.respondidas or revisar:
            pendentes.append(pid)
    pendentes.sort(key=lambda pid: (PRIORIDADE[perguntas_por_id()[pid]["obrigatoriedade"]], ordem[pid]))
    return pendentes


def _alertas_de_dados(respostas: Respondidas, dados: DadosAtendente,
                      sinais: list[Sinal]) -> list[Alerta]:
    alertas = []
    perguntas = perguntas_por_id()
    if respostas.incompletas:
        alertas.append(Alerta(
            codigo="dado_incompleto",
            mensagem="Perguntas respondidas pela metade; complete: " + "; ".join(
                f"{pid} ({', '.join(partes)})" for pid, partes in sorted(respostas.incompletas.items())),
            referencias=sorted(respostas.incompletas)))
    seguranca = sorted(pid for pid in respostas.desconhecidas
                       if perguntas[pid]["obrigatoriedade"] == "S")
    if seguranca:
        alertas.append(Alerta(
            codigo="dado_desconhecido",
            mensagem="Pergunta de segurança sem resposta (não sabe/recusou); não vale como 'não': "
                     + ", ".join(seguranca),
            referencias=seguranca))
    por_nome = {s.nome: s for s in sinais}

    def status(n):
        return por_nome[n].status

    if status(NomeSinal.FEBRE_REFERIDA) == Status.PRESENTE and \
            status(NomeSinal.ANTITERMICO_RECENTE) == Status.PRESENTE and \
            status(NomeSinal.FEBRE_ATUAL) != Status.PRESENTE:
        alertas.append(Alerta(
            codigo="febre_mascarada",
            mensagem="Febre referida com antitérmico recente e sem febre na aferição: a febre pode "
                     "estar mascarada pelo remédio.",
            referencias=["febre_referida", "antitermico_recente", "febre_atual"]))
    if status(NomeSinal.FEBRE_ATUAL) == Status.PRESENTE and status(NomeSinal.FEBRE_REFERIDA) == Status.NEGADO:
        alertas.append(Alerta(
            codigo="febre_nao_referida",
            mensagem="O paciente nega febre, mas a temperatura aferida está elevada; vale a aferição.",
            referencias=["febre_referida", "febre_atual"]))
    return alertas


# --- 6. orquestração -----------------------------------------------------------------------------

def processar_ficha(ficha: dict, extrator: Extrator) -> SaidaTriagem:
    dados, brutas, erros = validar_ficha(ficha)
    respostas, erros_respostas = interpretar_respostas(dados, brutas)  # valida mesmo sem cadastro
    erros += erros_respostas
    if erros:
        raise FichaInvalida(erros)

    extracao, alertas = extrair_relato(respostas.relato, extrator)
    extraidos = {s.nome: s for s in extracao.sinais} if extracao else {}
    medidos, alertas_afericao = sinais_medidos(dados)
    alertas += alertas_afericao

    sinais, alertas_div, divergentes = mesclar_sinais(respostas.sinais, medidos, extraidos)
    alertas += alertas_div
    por_nome = {s.nome: s for s in sinais}
    for nome in respostas.nao_se_aplica:  # perguntas que não valem para este paciente
        for spec in perguntas_por_id()[nome].get("sinais", []):
            n = NomeSinal(spec["nome"])
            if por_nome[n].status == Status.NAO_MENCIONADO:
                idx = sinais.index(por_nome[n])
                sinais[idx] = Sinal(nome=n, status=Status.NAO_SE_APLICA, origem=Origem.NENHUMA)

    duracao = respostas.duracao
    if extracao and extracao.duracao:
        if duracao is None:
            duracao = extracao.duracao
        elif not 0.5 <= _minutos(duracao) / max(_minutos(extracao.duracao), 1) <= 2:
            alertas.append(Alerta(
                codigo="duracao_divergente",
                mensagem=f"Duração divergente: Q02 diz {duracao.valor:g} {duracao.unidade.value}, o "
                         f"relato sugere {extracao.duracao.valor:g} {extracao.duracao.unidade.value}.",
                referencias=["Q02", "Q01"]))
    alergias = respostas.alergias or Alergias()
    if extracao and extracao.alergias:
        if alergias.status == Status.NAO_MENCIONADO:
            alergias = extracao.alergias
        elif alergias.status == Status.NEGADO:
            alertas.append(Alerta(
                codigo="alergia_divergente",
                mensagem="O relato cita alergia (" + ", ".join(extracao.alergias.itens) +
                         ") mas a Q10 diz que não há. Confirme com o paciente.",
                referencias=["Q10", "Q01"]))

    ativos = modulos_ativos(respostas, extracao, sinais)
    if not ativos and extracao is not None:
        alertas.append(Alerta(codigo="sem_modulo",
                              mensagem="Nenhum módulo de perguntas se encaixou; seguir só com o núcleo.",
                              referencias=[]))
    alertas += _alertas_de_dados(respostas, dados, sinais)
    pendentes = calcular_pendencias(dados, respostas, ativos, divergentes,
                                    extracao_falhou=bool(respostas.relato) and extracao is None)
    faltando = afericoes_faltando(dados, {s.nome: s for s in sinais})
    if faltando:
        alertas.append(Alerta(codigo="afericao_faltando",
                              mensagem="Aferições não registradas (valem como 'não aferido', "
                                       "nunca como normais): " + ", ".join(faltando),
                              referencias=faltando))

    saida = SaidaTriagem(
        relato_original=respostas.relato,
        respostas=respostas.respostas,
        queixa_principal=extracao.queixa_principal if extracao else None,
        queixas=extracao.queixas if extracao else [],
        modulos_ativos=ativos,
        duracao=duracao,
        sinais=sinais,
        alergias=alergias,
        dados_atendente=dados,
        afericoes_faltando=faltando,
        perguntas_pendentes=pendentes,
        proxima_pergunta=pendentes[0] if pendentes else None,
        alertas=alertas,
        extrator=extrator.nome,
    )
    saida.classificacao = pontuar(saida)
    saida.alertas += _alertas_graves(saida)
    return saida


def _alertas_graves(saida: SaidaTriagem) -> list[Alerta]:
    """Avisa a enfermagem na hora quando uma regra de cor alta foi acionada."""
    regras = {r["id"]: r for r in carregar_regras()["pontuacao"]["regras_cor"]}
    graves = [r for r in saida.classificacao.regras_aplicadas
              if r.id in regras and Cor(regras[r.id]["cor_minima"]).nivel >= Cor.LARANJA.nivel]
    return [Alerta(codigo="sinal_de_alerta", mensagem=f"{r.descricao} ({r.efeito})", referencias=[r.id])
            for r in graves]
