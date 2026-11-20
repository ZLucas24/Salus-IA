"""Histórico do paciente e cruzamento com a ficha de hoje.

Duas partes separadas:

1. **Fonte** (`FonteHistorico`): de onde o histórico vem. Neste protótipo é um arquivo de
   pacientes SIMULADOS (`dados/historico_simulado.json`). Numa rede hospitalar, basta escrever
   outra implementação que consulte o prontuário eletrônico; o resto do sistema não muda.
   A Salus só LÊ o histórico: nada do paciente é gravado aqui.
2. **Cruzamento** (`cruzar`): compara o histórico com a triagem de hoje e devolve PADRÕES,
   por regra escrita em código (sem IA). Regras de segurança:
   - um padrão é um aviso para o enfermeiro e o médico; NÃO é diagnóstico;
   - nunca muda a cor nem a pontuação (o cruzamento roda depois da classificação);
   - "diagnóstico registrado" é só o que consta em atendimentos anteriores, citado como registro;
   - os limites (dias, quantidade) moram em `regras.json`, marcados como não validados.
"""

import json
import re
from abc import ABC, abstractmethod
from collections import Counter
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path

from triagem.regras import carregar_regras
from triagem.texto import sem_acentos

ARQUIVO_SIMULADO = Path(__file__).parent / "dados" / "historico_simulado.json"
FORMATO_PRONTUARIO = re.compile(r"^[0-9]{4,12}$")
QUEIXAS_SEM_PADRAO = {"outra", "indefinida"}  # genéricas demais para dizer "mesma queixa"
NOME_QUEIXA = {"dor_toracica": "dor no peito", "dor_abdominal": "dor abdominal",
               "respiratorio_febre": "queixa respiratória ou febre"}
# sinal de hoje que o histórico pode contradizer -> (campo do histórico, texto)
SINAIS_DO_HISTORICO = {
    "uso_anticoagulante": "uso de remédio para afinar o sangue (anticoagulante)",
    "uso_insulina": "uso de insulina",
    "doenca_cronica": "doença crônica",
}


class HistoricoInvalido(ValueError):
    pass


def prontuario_valido(prontuario) -> bool:
    return isinstance(prontuario, str) and FORMATO_PRONTUARIO.fullmatch(prontuario) is not None


class FonteHistorico(ABC):
    """De onde vem o histórico. Trocar a implementação é o ponto de integração com o hospital."""

    nome: str

    @abstractmethod
    def buscar(self, prontuario: str) -> dict | None:
        """Histórico do paciente ou None se o prontuário não existe."""

    def exemplos(self) -> list[str]:
        """Prontuários de demonstração (vazio numa fonte real)."""
        return []


@lru_cache(maxsize=1)
def _carregar_simulado() -> dict:
    dados = json.loads(ARQUIVO_SIMULADO.read_text(encoding="utf-8"))
    for prontuario, p in dados["pacientes"].items():
        if not prontuario_valido(prontuario):
            raise HistoricoInvalido(f"prontuário inválido no arquivo simulado: {prontuario!r}")
        for a in p["atendimentos"]:
            if not isinstance(a["dias_atras"], int) or a["dias_atras"] < 0:
                raise HistoricoInvalido(f"{prontuario}: dias_atras deve ser inteiro >= 0")
    return dados


class HistoricoSimulado(FonteHistorico):
    """Pacientes inventados. As datas são relativas a hoje, para a demonstração não envelhecer."""

    nome = "simulado"

    def __init__(self, hoje=date.today):
        self._hoje = hoje

    def buscar(self, prontuario: str) -> dict | None:
        if not prontuario_valido(prontuario):
            return None
        p = _carregar_simulado()["pacientes"].get(prontuario)
        if p is None:
            return None
        hoje = self._hoje()
        atendimentos = sorted(p["atendimentos"], key=lambda a: a["dias_atras"])
        return {
            "prontuario": prontuario, "fonte": self.nome, "simulado": True,
            "idade": p.get("idade"), "sexo_biologico": p.get("sexo_biologico"),
            "condicoes": list(p.get("condicoes", [])), "alergias": list(p.get("alergias", [])),
            "medicamentos": list(p.get("medicamentos", [])), "sinais": list(p.get("sinais", [])),
            "atendimentos": [{
                "data": (hoje - timedelta(days=a["dias_atras"])).isoformat(), "ha_dias": a["dias_atras"],
                "queixa": a["queixa"], "descricao": a["descricao"], "cor": a["cor"],
                "diagnostico": a.get("diagnostico"), "desfecho": a.get("desfecho"),
            } for a in atendimentos],
        }

    def exemplos(self) -> list[str]:
        return sorted(_carregar_simulado()["pacientes"])


def _ha(dias: int) -> str:
    return "hoje" if dias == 0 else "ontem" if dias == 1 else f"há {dias} dias"


def _padrao(codigo: str, nivel: str, mensagem: str) -> dict:
    return {"codigo": codigo, "nivel": nivel, "mensagem": mensagem}


def cruzar(historico: dict, saida: dict) -> list[dict]:
    """Padrões entre o histórico e a triagem de hoje (`saida` = SaidaTriagem em dicionário).

    Só informa: não altera `saida` e nunca devolve nada que reduza ou aumente a prioridade."""
    limites = carregar_regras()["historico"]
    # do mais recente para o mais antigo, seja qual for a ordem da fonte
    atendimentos = sorted(historico["atendimentos"], key=lambda a: a["ha_dias"])
    padroes = []

    recentes = [a for a in atendimentos if a["ha_dias"] <= limites["janela_retorno_dias"]]
    if atendimentos and atendimentos[0]["ha_dias"] <= limites["retorno_precoce_dias"]:
        a = atendimentos[0]
        padroes.append(_padrao("retorno_precoce", "atencao",
                               f"Retorno em pouco tempo: o último atendimento foi {_ha(a['ha_dias'])} "
                               f"({a['descricao']}; desfecho registrado: {a.get('desfecho') or 'não informado'})."))
    if len(recentes) >= limites["atendimentos_para_retorno_frequente"]:
        padroes.append(_padrao("retorno_frequente", "atencao",
                               f"Esta é a {len(recentes) + 1}ª vinda em {limites['janela_retorno_dias']} dias."))

    for queixa in saida.get("queixas", []):
        if queixa in QUEIXAS_SEM_PADRAO:
            continue
        iguais = [a for a in atendimentos if a["queixa"] == queixa]
        if not iguais:
            continue
        nome = NOME_QUEIXA.get(queixa, queixa.replace("_", " "))
        vezes = "1 atendimento anterior" if len(iguais) == 1 else f"{len(iguais)} atendimentos anteriores"
        texto = f"Mesma queixa ({nome}) em {vezes}; o mais recente foi {_ha(iguais[0]['ha_dias'])}."
        diagnosticos = Counter(a["diagnostico"] for a in iguais if a.get("diagnostico"))
        if diagnosticos:
            lista = "; ".join(f"{d} ({n}x)" if n > 1 else d for d, n in diagnosticos.most_common())
            texto += f" Diagnóstico registrado nesses atendimentos: {lista}. É registro anterior, não diagnóstico de hoje."
        padroes.append(_padrao("queixa_repetida", "atencao", texto))

    alergias = saida.get("alergias", {})
    if historico["alergias"]:
        ditas = sem_acentos(" ".join(alergias.get("itens", []))).lower()
        faltam = [a for a in historico["alergias"] if sem_acentos(a).lower() not in ditas]
        if alergias.get("status") != "presente" or faltam:
            padroes.append(_padrao("alergia_no_historico", "grave",
                                   f"O histórico registra alergia a {', '.join(faltam or historico['alergias'])}, "
                                   "que não aparece na ficha de hoje. Confirme com o paciente."))

    status = {s["nome"]: s["status"] for s in saida.get("sinais", [])}
    for sinal, texto in SINAIS_DO_HISTORICO.items():
        if sinal in historico["sinais"] and status.get(sinal) != "presente":
            padroes.append(_padrao("historico_diverge_da_ficha", "atencao",
                                   f"O histórico registra {texto}, mas isso não está confirmado na ficha de hoje. "
                                   "Confirme com o paciente."))
    return padroes


def consultar(fonte: FonteHistorico | None, prontuario, saida: dict | None = None) -> dict | None:
    """Histórico (e, com `saida`, os padrões). None se não há fonte ou o prontuário não existe."""
    if fonte is None or not prontuario_valido(prontuario):
        return None
    historico = fonte.buscar(prontuario)
    if historico is None:
        return None
    if saida is not None:
        historico["padroes"] = cruzar(historico, saida)
    return historico
