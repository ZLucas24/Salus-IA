"""Motor de regras: cor e pontuação (0 a 100 dentro da cor).

Tudo é regra explícita em código + tabela em `dados/regras.json`. Nenhuma IA
participa. Garantias:
  - os pesos nunca são negativos e o resultado só aumenta quando entram novos
    achados (ordem: cor, depois pontos);
  - um sinal só entra se estiver presente; "não sabe", "recusou" e "incerto"
    nunca contam como ausência (geram alerta em outro módulo, não pontos);
  - quando o relato cita um sinal e a resposta direta o nega, o status mostrado
    é o da resposta, mas a pontuação o conta como presente (configurável);
  - os resultados são sempre provisórios: as regras não foram validadas.
"""

from triagem.regras import carregar_regras
from triagem.schema import Classificacao, RegraAplicada, SaidaTriagem, Sinal
from triagem.sinais import Cor, NomeSinal, Status


def _conta_como_presente(sinal: Sinal, divergencia_conta: bool) -> bool:
    if sinal.status == Status.PRESENTE:
        return True
    return (divergencia_conta and sinal.status == Status.NEGADO
            and sinal.status_no_relato == Status.PRESENTE)


def _condicao_ok(cond, ativos: dict[NomeSinal, Sinal]) -> bool:
    nome = cond if isinstance(cond, str) else cond["sinal"]
    sinal = ativos.get(NomeSinal(nome))
    if sinal is None:
        return False
    if isinstance(cond, dict):
        if "valor_min" in cond and (sinal.valor is None or sinal.valor < cond["valor_min"]):
            return False
        if "valor_max" in cond and (sinal.valor is None or sinal.valor > cond["valor_max"]):
            return False
    return True


def pontuar(extracao: SaidaTriagem) -> Classificacao:
    """Recebe o objeto estruturado (nunca o texto cru) e devolve cor e pontuação."""
    cfg = carregar_regras()["pontuacao"]
    divergencia = cfg["divergencia_conta_como_presente"]
    ativos = {s.nome: s for s in extracao.sinais if _conta_como_presente(s, divergencia)}
    aplicadas: list[RegraAplicada] = []

    cor = Cor(cfg["cor_base"])
    for regra in cfg["regras_cor"]:
        if all(_condicao_ok(c, ativos) for c in regra["todos"]):
            minima = Cor(regra["cor_minima"])
            aplicadas.append(RegraAplicada(
                id=regra["id"], descricao=regra["descricao"],
                efeito=f"cor mínima {minima.value}"))
            if minima.nivel > cor.nivel:
                cor = minima

    total = 0.0
    for nome, sinal in ativos.items():
        peso = cfg["pesos"].get(nome.value, 0)
        if not peso:
            continue
        if nome == NomeSinal.DOR:
            fracao = max(cfg["dor_fracao_minima"], (sinal.valor or 0) / 10)
            pontos = peso * min(fracao, 1.0)
        else:
            pontos = peso
        total += pontos
        aplicadas.append(RegraAplicada(
            id=f"PESO-{nome.value}", descricao=f"sinal {nome.value}",
            efeito=f"+{pontos:g} pontos"))

    teto = cfg["teto"]
    while total >= teto and cor != Cor.VERMELHO:
        anterior, cor = cor, list(Cor)[cor.nivel + 1]
        total -= teto
        aplicadas.append(RegraAplicada(
            id="PROMOCAO", descricao="pontuação chegou ao teto",
            efeito=f"subiu de {anterior.value} para {cor.value}"))
    pontuacao = int(min(total, teto))
    return Classificacao(cor=cor, pontuacao=pontuacao, provisoria=True,
                         regras_validadas=bool(carregar_regras()["validado"]),
                         regras_aplicadas=aplicadas)
