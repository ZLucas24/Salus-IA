"""Questionário (dados) e interpretação determinística das respostas.

O banco de perguntas está em `dados/questionario.json`. Cada pergunta tem
partes tipadas e uma tabela `sinais`/`campos` que diz o que cada parte
preenche. Nenhuma IA participa daqui: resposta fechada vira sinal por código.
"""

import json
import math
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from triagem.schema import Alergias, DadosAtendente, Duracao, Sinal
from triagem.sinais import (MARCADORES, SINAIS_MEDIDOS, NomeSinal, Origem, SexoBiologico,
                            Status)
from triagem.texto import normalizar_itens

CAMINHO_QUESTIONARIO = Path(__file__).parent / "dados" / "questionario.json"
FORMAS = {"texto", "sim_nao", "escala", "numero", "opcao", "multiplas", "numero_unidade"}
PRIORIDADE = {"S": 0, "N": 1, "M": 2, "C": 3}
OBRIGATORIAS = {"sim_nao", "opcao", "multiplas", "escala"}


class ErroResposta(ValueError):
    """Resposta que não segue o tipo definido para a pergunta."""


class QuestionarioInvalido(ValueError):
    """O arquivo do questionário está inconsistente (erro de quem edita os dados)."""


# --- carga e validação do próprio questionário -------------------------------

@lru_cache(maxsize=1)
def carregar_questionario() -> dict:
    with open(CAMINHO_QUESTIONARIO, encoding="utf-8-sig") as f:
        q = json.load(f)
    _validar_questionario(q)
    return q


def perguntas_por_id() -> dict[str, dict]:
    return {p["id"]: p for p in carregar_questionario()["perguntas"]}


def _validar_questionario(q: dict) -> None:
    nomes_sinais = {n.value for n in NomeSinal}
    modulos = set(q.get("modulos", {}))
    ids = set()
    for p in q["perguntas"]:
        pid = p.get("id", "?")
        if pid in ids:
            raise QuestionarioInvalido(f"{pid}: id repetido")
        ids.add(pid)
        if p.get("obrigatoriedade") not in PRIORIDADE:
            raise QuestionarioInvalido(f"{pid}: obrigatoriedade inválida")
        if p.get("modulo") and p["modulo"] not in modulos:
            raise QuestionarioInvalido(f"{pid}: módulo desconhecido {p['modulo']!r}")
        if (p["obrigatoriedade"] == "M") != bool(p.get("modulo")):
            raise QuestionarioInvalido(f"{pid}: só perguntas de módulo (M) têm 'modulo'")
        partes = {x["nome"]: x for x in p["partes"]}
        if len(partes) != len(p["partes"]):
            raise QuestionarioInvalido(f"{pid}: partes repetidas")
        for x in p["partes"]:
            if x["forma"] not in FORMAS:
                raise QuestionarioInvalido(f"{pid}.{x['nome']}: forma desconhecida {x['forma']!r}")
            if x["forma"] in ("opcao", "multiplas") and not x.get("opcoes"):
                raise QuestionarioInvalido(f"{pid}.{x['nome']}: faltam 'opcoes'")
            dep = x.get("depende_de")
            if dep and dep["parte"] not in partes:
                raise QuestionarioInvalido(f"{pid}.{x['nome']}: depende de parte inexistente")
        for s in p.get("sinais", []):
            if s["nome"] not in nomes_sinais:
                raise QuestionarioInvalido(f"{pid}: sinal desconhecido {s['nome']!r}")
            if NomeSinal(s["nome"]) in SINAIS_MEDIDOS:
                raise QuestionarioInvalido(f"{pid}: {s['nome']} vem das aferições, não de perguntas")
            for ref in ([s["de"]] if isinstance(s["de"], str) else s["de"]):
                if ref not in partes:
                    raise QuestionarioInvalido(f"{pid}: 'de' aponta para parte inexistente {ref!r}")
            for chave in ("valor_de", "itens_de"):
                if chave in s and s[chave] not in partes:
                    raise QuestionarioInvalido(f"{pid}: '{chave}' aponta para parte inexistente")
        for c in p.get("campos", []):
            if c["campo"] not in {"relato", "duracao", "alergias"}:
                raise QuestionarioInvalido(f"{pid}: campo desconhecido {c['campo']!r}")
            if c["de"] not in partes:
                raise QuestionarioInvalido(f"{pid}: campo aponta para parte inexistente")


def ids_de_sinais_do_questionario() -> set[str]:
    return {s["nome"] for p in carregar_questionario()["perguntas"] for s in p.get("sinais", [])}


# --- aplicabilidade -----------------------------------------------------------

def pergunta_se_aplica(pergunta: dict, dados: DadosAtendente | None) -> bool:
    """Sem cadastro válido (dados None) a pergunta é tratada como aplicável."""
    cond = pergunta.get("aplica_se")
    if not cond or dados is None:
        return True
    if "sexo_em" in cond and dados.sexo_biologico.value not in cond["sexo_em"]:
        return False
    if "idade_entre" in cond:
        minimo, maximo = cond["idade_entre"]
        if not minimo <= dados.idade <= maximo:
            return False
    return True


# --- validação de valores por forma ---------------------------------------------

def _eh_numero(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _validar_parte(parte: dict, v):
    """Devolve o valor normalizado ou um Status (marcador). Levanta ErroResposta."""
    nome, forma = parte["nome"], parte["forma"]
    if isinstance(v, str) and v in MARCADORES:
        return MARCADORES[v]

    def erro(msg):
        return ErroResposta(f"'{nome}': {msg}; recebi {v!r}")

    if forma == "texto":
        if not isinstance(v, str) or not v.strip():
            raise erro("deve ser um texto não vazio")
        limpo = v.strip()
        if len(limpo) > parte.get("max_caracteres", 200):
            raise ErroResposta(
                f"'{nome}': tem {len(limpo)} caracteres; o máximo é {parte.get('max_caracteres', 200)}")
        return limpo
    if forma == "sim_nao":
        if not isinstance(v, bool):
            raise erro("deve ser true ou false")
        return v
    if forma in ("escala", "numero"):
        if not _eh_numero(v):
            raise erro("deve ser um número finito")
        if forma == "escala" and v != int(v):
            raise erro("deve ser um número inteiro")
        minimo, maximo = parte.get("minimo"), parte.get("maximo")
        if (minimo is not None and v < minimo) or (maximo is not None and v > maximo):
            raise erro(f"deve estar entre {minimo} e {maximo}")
        return int(v) if forma == "escala" else float(v)
    if forma == "opcao":
        if v not in parte["opcoes"]:
            raise erro(f"deve ser uma de: {', '.join(parte['opcoes'])}")
        return v
    if forma == "multiplas":
        if not isinstance(v, list) or any(x not in parte["opcoes"] for x in v):
            raise erro(f"deve ser uma lista com itens de: {', '.join(parte['opcoes'])}")
        if len(set(v)) != len(v):
            raise erro("tem item repetido")
        return list(v)
    if forma == "numero_unidade":
        if not isinstance(v, dict) or set(v) != {"valor", "unidade"}:
            raise erro('deve ser {"valor": N, "unidade": "..."}')
        if not _eh_numero(v["valor"]) or not 0 <= v["valor"] <= 1000:
            raise erro("'valor' deve ser um número entre 0 e 1000")
        if v["unidade"] not in parte["unidades"]:
            raise erro(f"'unidade' deve ser uma de: {', '.join(parte['unidades'])}")
        return Duracao(valor=v["valor"], unidade=v["unidade"])
    raise QuestionarioInvalido(f"forma desconhecida: {forma}")


# --- interpretação de uma pergunta ------------------------------------------------

@dataclass
class Interpretacao:
    sinais: dict[NomeSinal, Sinal] = field(default_factory=dict)
    duracao: Duracao | None = None
    alergias: Alergias | None = None
    relato: str | None = None
    incompleta: list[str] = field(default_factory=list)  # partes que faltam
    desconhecidos: list[str] = field(default_factory=list)  # partes "não sabe"/"recusou"


def _partes_brutas(pergunta: dict, bruto) -> dict:
    partes = pergunta["partes"]
    if isinstance(bruto, str) and bruto in MARCADORES:
        return {p["nome"]: bruto for p in partes}
    if len(partes) == 1 and partes[0]["nome"] == "resposta":
        return {"resposta": bruto}
    if not isinstance(bruto, dict):
        raise ErroResposta(f"a resposta deve ser um objeto com os campos "
                           f"{', '.join(p['nome'] for p in partes)}; recebi {bruto!r}")
    desconhecidos = set(bruto) - {p["nome"] for p in partes}
    if desconhecidos:
        raise ErroResposta(f"campo(s) desconhecido(s): {', '.join(sorted(desconhecidos))}")
    return bruto


def _status_simples(parte: dict, v, spec: dict) -> Status:
    """Status de um sinal a partir do valor (já validado) de uma parte."""
    if isinstance(v, Status):
        return v
    forma = parte["forma"]
    if forma == "sim_nao":
        presente = (not v) if spec.get("inverter") else v
    elif forma == "opcao":
        quando = spec.get("quando")
        presente = True if quando is None else v in ([quando] if isinstance(quando, str) else quando)
    elif forma in ("escala", "numero"):
        presente = v > 0
    elif forma == "multiplas":
        quando = spec.get("quando")
        presente = (quando in v) if quando else len(v) > 0
    else:  # texto
        presente = bool(v)
    return Status.PRESENTE if presente else Status.NEGADO


def interpretar(pergunta: dict, bruto) -> Interpretacao:
    """Valida `bruto` contra a pergunta e devolve sinais e campos preenchidos."""
    partes = {p["nome"]: p for p in pergunta["partes"]}
    brutas = _partes_brutas(pergunta, bruto)
    valores: dict[str, object] = {}
    erros = []
    for nome, parte in partes.items():
        v = brutas.get(nome)
        if v is None:
            continue
        try:
            valores[nome] = _validar_parte(parte, v)
        except ErroResposta as e:
            erros.append(str(e))
    if erros:
        raise ErroResposta("; ".join(erros))

    r = Interpretacao()
    # partes obrigatórias que faltam deixam a pergunta incompleta (e pendente);
    # texto, número e duração são detalhes opcionais
    for nome, parte in partes.items():
        if nome in valores or parte["forma"] not in OBRIGATORIAS or parte.get("opcional"):
            continue
        dep = parte.get("depende_de")
        if dep is None:
            r.incompleta.append(nome)
        else:
            pai = valores.get(dep["parte"])
            if pai is not None and not isinstance(pai, Status) and pai == dep["igual"]:
                r.incompleta.append(nome)
    # parte que só faz sentido sob uma condição, informada fora dela: contradição
    for nome, parte in partes.items():
        dep = parte.get("depende_de")
        if not dep or nome not in valores or isinstance(valores[nome], Status):
            continue
        pai = valores.get(dep["parte"])
        if pai is not None and not isinstance(pai, Status) and pai != dep["igual"]:
            raise ErroResposta(
                f"'{nome}' só se aplica quando '{dep['parte']}' é {dep['igual']}; "
                f"recebi {brutas[nome]!r} com '{dep['parte']}'={pai!r}")
    r.desconhecidos = [n for n, v in valores.items() if isinstance(v, Status)]

    def status_da_parte(nome: str, spec: dict) -> Status | None:
        v = valores.get(nome)
        if v is not None:
            return _status_simples(partes[nome], v, spec)
        dep = partes[nome].get("depende_de")
        if dep:  # filho de um "não" é "não"; filho de um marcador herda o marcador
            pai = valores.get(dep["parte"])
            if isinstance(pai, Status):
                return pai
            if pai is not None and pai != dep["igual"]:
                return Status.NEGADO
        return None

    for spec in pergunta.get("sinais", []):
        refs = [spec["de"]] if isinstance(spec["de"], str) else spec["de"]
        estados = [status_da_parte(ref, spec) for ref in refs]
        if Status.PRESENTE in estados:
            status = Status.PRESENTE
        elif all(e == Status.NEGADO for e in estados):
            status = Status.NEGADO
        else:
            marcador = next((e for e in estados if e is not None and e != Status.NEGADO), None)
            if marcador is None:
                continue  # parte(s) não respondida(s): o sinal fica nao_mencionado
            status = marcador
        valor, itens = None, []
        if status == Status.PRESENTE:
            vv = valores.get(spec.get("valor_de", ""))
            valor = float(vv) if _eh_numero(vv) else None
            iv = valores.get(spec.get("itens_de", ""))
            if isinstance(iv, list):
                itens = iv
            elif isinstance(iv, str) and not isinstance(iv, Status):
                itens = normalizar_itens(iv)
        r.sinais[NomeSinal(spec["nome"])] = Sinal(
            nome=NomeSinal(spec["nome"]), status=status, valor=valor, itens=itens,
            origem=Origem.RESPOSTA_DIRETA)

    for campo in pergunta.get("campos", []):
        v = valores.get(campo["de"])
        if campo["campo"] == "relato" and isinstance(v, str):
            r.relato = v
        elif campo["campo"] == "duracao" and isinstance(v, Duracao):
            r.duracao = v
        elif campo["campo"] == "alergias" and v is not None:
            r.alergias = _montar_alergias(campo, valores, partes, r)
    return r


def _montar_alergias(campo: dict, valores: dict, partes: dict, r: Interpretacao) -> Alergias:
    v = valores[campo["de"]]
    if isinstance(v, Status):
        return Alergias(status=v)
    if not v:
        return Alergias(status=Status.NEGADO)
    itens_v = valores.get(campo.get("itens_de", ""))
    itens = normalizar_itens(itens_v) if isinstance(itens_v, str) else []
    tipos = valores.get(campo.get("tipos_de", ""))
    if not itens:
        r.incompleta.append(campo.get("itens_de", "texto"))
    return Alergias(status=Status.PRESENTE, itens=itens,
                    tipos=tipos if isinstance(tipos, list) else [])
