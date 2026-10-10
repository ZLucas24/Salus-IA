"""Fluxo da entrevista: ficha -> validação -> sinais -> extração -> pontuação."""

import json
import logging

from pydantic import ValidationError

from triagem.extracao import Extrator
from triagem.pontuacao import pontuar
from triagem.questionario import ErroResposta, carregar_questionario, interpretar
from triagem.schema import AlergiasMedicamentosas, DadosAtendente, Resposta, SaidaTriagem, Sinal
from triagem.sinais import NomeSinal, Origem, Status

log = logging.getLogger("triagem")
NOMES_SINAIS = {n.value for n in NomeSinal}


class FichaInvalida(Exception):
    def __init__(self, erros: list[str]):
        super().__init__("; ".join(erros))
        self.erros = erros


def _erros_dados_atendente(e: ValidationError) -> list[str]:
    msgs = []
    for err in e.errors():
        campo = ".".join(str(p) for p in err["loc"]) or "dados_atendente"
        if err["type"] == "missing":
            msgs.append(f"dados_atendente.{campo}: campo obrigatório")
        else:
            msgs.append(f"dados_atendente.{campo}: {err['msg']}")
    return msgs


def _bruto_para_texto(v) -> str:
    return v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)


def processar_ficha(ficha: dict, extrator: Extrator) -> SaidaTriagem:
    if not isinstance(ficha, dict):
        raise FichaInvalida(["a ficha deve ser um objeto JSON"])
    erros: list[str] = []
    perguntas = {p["id"]: p for p in carregar_questionario()["perguntas"]}

    # dados do atendente (idade obrigatória)
    dados = None
    dados_brutos = ficha.get("dados_atendente")
    if not isinstance(dados_brutos, dict):
        erros.append("dados_atendente: objeto obrigatório (com pelo menos 'idade')")
    else:
        try:
            dados = DadosAtendente(**dados_brutos)
        except ValidationError as e:
            erros.extend(_erros_dados_atendente(e))

    # respostas fechadas -> sinais (código determinístico)
    brutas = ficha.get("respostas", {})
    if not isinstance(brutas, dict):
        erros.append('respostas: deve ser um objeto {"P01": ..., ...}')
        brutas = {}
    erros.extend(f"{pid}: pergunta inexistente no questionário" for pid in brutas if pid not in perguntas)

    diretos: dict[NomeSinal, Sinal] = {}
    respostas: list[Resposta] = []
    duracao = None
    alergias = AlergiasMedicamentosas()
    for pid, pergunta in perguntas.items():
        bruto = brutas.get(pid)
        if bruto is None:  # não respondida
            continue
        try:
            r = interpretar(pergunta, bruto)
        except ErroResposta as e:
            erros.append(f"{pid} ({pergunta['texto']}): {e}")
            continue
        respostas.append(Resposta(id_pergunta=pid, resposta_bruta=_bruto_para_texto(bruto)))
        diretos.update({s.nome: s for s in r.sinais})
        duracao = r.duracao or duracao
        alergias = r.alergias or alergias

    if erros:
        raise FichaInvalida(erros)

    # extração do relato (P01); em divergência, a resposta direta prevalece
    relato = brutas.get("P01") or ""
    queixa = None
    extraidos: dict[NomeSinal, Sinal] = {}
    if relato:
        ext = extrator.extrair(relato)
        queixa = ext.queixa_principal
        extraidos = {
            s.nome: s.model_copy(update={"origem": Origem.EXTRAIDO_DO_RELATO})
            for s in ext.sinais
            if s.status != Status.NAO_MENCIONADO  # o extrator só informa o que o relato cita
        }
        if duracao is None:
            duracao = ext.duracao
        if alergias.status == Status.NAO_MENCIONADO and ext.alergias_medicamentosas:
            alergias = ext.alergias_medicamentosas

    sinais: list[Sinal] = []
    for nome in NomeSinal:
        direto, do_relato = diretos.get(nome), extraidos.get(nome)
        if direto is not None:
            if do_relato is not None and do_relato.status != direto.status:
                log.info("divergência em '%s': relato=%s, resposta direta=%s (prevalece)",
                         nome.value, do_relato.status.value, direto.status.value)
            sinais.append(direto)
        elif do_relato is not None:
            sinais.append(do_relato)
        else:
            sinais.append(Sinal(nome=nome, status=Status.NAO_MENCIONADO,
                                origem=Origem.RESPOSTA_DIRETA))

    # pendentes: sem resposta ou com algum sinal ainda nao_mencionado
    sem_mencao = {s.nome.value for s in sinais if s.status == Status.NAO_MENCIONADO}
    pendentes = []
    for pid, pergunta in perguntas.items():
        nomes = {p["nome"] for p in pergunta["preenche"] if p["tipo"] == "sinal"} & NOMES_SINAIS
        if brutas.get(pid) is None or nomes & sem_mencao:
            pendentes.append(pid)
    if alergias.status == Status.NAO_MENCIONADO and "P13" not in pendentes:
        pendentes.append("P13")

    saida = SaidaTriagem(
        relato_original=relato,
        respostas=respostas,
        queixa_principal=queixa,
        duracao=duracao,
        sinais=sinais,
        alergias_medicamentosas=alergias,
        dados_atendente=dados,
        perguntas_pendentes=pendentes,
        pontuacao_provisoria=True,
        extrator=extrator.nome,
    )
    saida.pontuacao = pontuar(saida)
    return saida
