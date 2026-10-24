"""Gera `docs/roteiro_entrevista.md` a partir do questionário.

O roteiro nunca é escrito à mão: ele é derivado de `dados/questionario.json`,
então não fica desatualizado. Um teste confere que o arquivo versionado
corresponde à saída deste gerador.

Uso: python -m triagem.roteiro            # grava docs/roteiro_entrevista.md
     python -m triagem.roteiro --stdout   # só imprime
"""

import argparse
import json
import sys
from pathlib import Path

from triagem.questionario import carregar_questionario

DESTINO = Path(__file__).parent.parent / "docs" / "roteiro_entrevista.md"
TITULOS = {"S": "Segurança (nunca pular por suposição)", "N": "Núcleo (todo paciente)",
           "M": "Módulos por queixa", "C": "Complementares (para o médico)"}

CABECALHO = """# Roteiro de entrevista

> Gerado automaticamente por `python -m triagem.roteiro` a partir de
> [triagem/dados/questionario.json](../triagem/dados/questionario.json). **Não edite à mão:**
> altere o questionário e gere de novo.

Guia para o atendente conduzir a entrevista de triagem do Salus IA. Protótipo com
**dados simulados**; não use com pacientes reais. O questionário ainda aguarda revisão por
enfermeiro ou médico.

## Princípios

- Leia as perguntas **como estão escritas**, uma de cada vez, em linguagem simples.
- Registre o que o paciente **disse**, sem interpretar. O sistema não decide gravidade.
- Se o paciente **não souber** ou **não quiser responder**, registre `"nao_sabe"` ou `"recusou"`
  no lugar da resposta. Isso **não** vale como "não": o sistema mantém o aviso. Se a pergunta
  não se aplica ao paciente, use `"nao_se_aplica"`.
- Não insista em pergunta que o paciente não quer ou não consegue responder.
- Não peça medidas numéricas ao paciente: temperatura, saturação, pressão e pulso vêm da
  aferição da enfermagem.
- Se houver sinal de alerta grave, avise a enfermagem imediatamente, sem esperar o fim.
- Se o paciente piorar durante a entrevista, siga o protocolo do serviço.

## Antes de começar: cadastro e aferições

Só a **idade é obrigatória**. Aferição que não foi feita fica **em branco** e vale como
"não aferida", nunca como normal.

| Campo | Observação |
|---|---|
| `idade` | obrigatória, em anos |
| `sexo_biologico` | `feminino`, `masculino`, `intersexo` ou `ausente` (padrão). Se ausente, as perguntas ligadas ao sexo continuam valendo |
{afericoes}
"""

RODAPE = """
## Depois da entrevista

1. Monte a ficha no formato descrito no [README](../README.md#formato-da-ficha).
2. Rode `python -m triagem ficha.json`.
3. Confira `perguntas_pendentes` e `alertas`. A `proxima_pergunta` é a mais importante que falta.
4. Relato e resposta direta podem divergir. A resposta direta prevalece, mas o sistema avisa
   (`alertas`) e a pontuação não diminui.
"""


def _exemplo(parte: dict):
    forma = parte["forma"]
    if forma == "sim_nao":
        return True
    if forma == "escala":
        return 5
    if forma == "numero":
        return parte.get("minimo", 1)
    if forma == "opcao":
        return parte["opcoes"][0]
    if forma == "multiplas":
        return [parte["opcoes"][0]]
    if forma == "numero_unidade":
        return {"valor": 2, "unidade": parte["unidades"][1]}
    return "texto curto"


def _formato(pergunta: dict) -> str:
    partes = pergunta["partes"]
    if len(partes) == 1 and partes[0]["nome"] == "resposta":
        return json.dumps(_exemplo(partes[0]), ensure_ascii=False)
    return json.dumps({p["nome"]: _exemplo(p) for p in partes}, ensure_ascii=False)


def _descricao_parte(parte: dict) -> str:
    forma = parte["forma"]
    base = {"sim_nao": "`true` ou `false`", "escala": "número inteiro de "
            f"{parte.get('minimo', 0)} a {parte.get('maximo', 10)}",
            "numero": "número", "texto": "texto curto",
            "numero_unidade": "número e unidade (" + ", ".join(parte.get("unidades", [])) + ")"}.get(forma)
    if forma == "opcao":
        base = "uma opção: " + ", ".join(f"`{o}`" for o in parte["opcoes"])
    if forma == "multiplas":
        base = "lista com: " + ", ".join(f"`{o}`" for o in parte["opcoes"]) + " (`[]` = nenhuma)"
    extra = ""
    if parte.get("depende_de"):
        dep = parte["depende_de"]
        extra = f" — só se `{dep['parte']}` for `{str(dep['igual']).lower()}`"
    if parte.get("opcional"):
        extra += " (opcional)"
    return f"{base}{extra}"


def gerar() -> str:
    q = carregar_questionario()
    afericoes = "\n".join(f"| `{a['campo']}` ({a['id']}) | {a['nome']} ({a['unidade']}) |"
                          for a in q["afericoes"] if a["campo"] != "pressao")
    afericoes += "\n| `pressao_sistolica` e `pressao_diastolica` (E03) | pressão arterial (mmHg), as duas juntas |"
    texto = CABECALHO.format(afericoes=afericoes.replace("`glasgow` (E07)", "`glasgow` (E07)"))

    for ob in ("S", "N", "M", "C"):
        grupo = [p for p in q["perguntas"] if p["obrigatoriedade"] == ob]
        texto += f"\n## {TITULOS[ob]}\n"
        modulo_atual = None
        for p in grupo:
            if p.get("modulo") and p["modulo"] != modulo_atual:
                modulo_atual = p["modulo"]
                texto += f"\n### Módulo: {q['modulos'][modulo_atual]}\n"
            texto += f"\n#### {p['id']}\n\n**Pergunte:** \"{p['texto']}\"  \n**Serve para:** {p['finalidade']}  \n"
            if p.get("aplica_se"):
                texto += f"**Quando se aplica:** {p['aplica_se']['nota']}  \n"
            if len(p["partes"]) == 1 and p["partes"][0]["nome"] == "resposta":
                texto += f"**Registre:** {_descricao_parte(p['partes'][0])}  \n"
            else:
                texto += "**Registre:**\n\n" + "\n".join(
                    f"- `{x['nome']}`: {_descricao_parte(x)}" for x in p["partes"]) + "\n\n"
            texto += f"**Exemplo:** `\"{p['id']}\": {_formato(p)}`\n"

    texto += RODAPE
    return texto


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m triagem.roteiro")
    parser.add_argument("--stdout", action="store_true", help="imprime em vez de gravar o arquivo")
    args = parser.parse_args(argv)
    texto = gerar()
    if args.stdout:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stdout.write(texto)
    else:
        DESTINO.write_text(texto, encoding="utf-8", newline="\n")
        print(f"roteiro gravado em {DESTINO}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
