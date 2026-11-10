"""Base de treino do EXTRATOR: cada triagem vira um caso anonimizado.

Para que serve: medir e melhorar a leitura do relato. Cada caso guarda o relato (anonimizado)
ao lado do que o extrator achou e do que o enfermeiro respondeu nas perguntas fechadas, que
funcionam como gabarito. As regras de cor e os pesos NUNCA são ajustados com esta base.

O que NÃO é guardado: nome, número de atendimento, código do QR, login do enfermeiro, idade
exata (vira faixa etária) e data exata (só ano e mês).

Anonimização do texto livre (relato e respostas em texto): CPF, cartão do SUS, telefone,
e-mail, CEP, datas, números longos, endereços e nomes apresentados ("meu nome é…", "Dr. …")
viram marcadores como [NOME]. Isso NÃO garante anonimato: um nome solto no meio da frase
pode passar. Por isso cada caso traz `revisar_nomes` (palavras com inicial maiúscula fora do
começo da frase) e a base inteira deve ser tratada como dado sensível de saúde.

Partição fixa: 20% dos casos (pelo `caso_id`) são "teste" e nunca devem entrar em treino.

Comandos:
  python -m triagem.treino resumo
  python -m triagem.treino exportar --particao treino --saida treino.jsonl [--sem-revisar]
"""

import argparse
import hashlib
import json
import re
import sqlite3
import sys
import threading
import time
from datetime import datetime, timezone

VERSAO = 1
PARTES_TEXTO_LIVRE = {"texto", "para_onde"}
PERGUNTAS_TEXTO = {"Q07", "C01", "C02", "C03", "C04"}

_FLAGS = re.IGNORECASE
_PADROES = [
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"), "[EMAIL]"),
    (re.compile(r"\b\d{3}\s?\d{4}\s?\d{4}\s?\d{4}\b"), "[CARTAO_SUS]"),
    (re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b"), "[CPF]"),
    (re.compile(r"\(?\b\d{2}\)?\s?9?\d{4}[-\s]?\d{4}\b"), "[TELEFONE]"),
    (re.compile(r"\b\d{5}-\d{3}\b"), "[CEP]"),
    (re.compile(r"\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b"), "[DATA]"),
    (re.compile(r"\b\d{6,}\b"), "[NUMERO]"),
    # endereço: a palavra-chave e só as palavras do nome da rua (maiúsculas ou "de/da/do"), mais o
    # número; não engole o resto da frase, que costuma ter sintomas
    (re.compile(r"\b(?i:rua|r\.|avenida|av\.|travessa|tv\.|alameda|estrada|rodovia|pra[cç]a)\s+"
                r"(?:(?:d[aeo]s?|[A-ZÀ-Ú0-9][\wÀ-ú.]*)\s*)+(?:,?\s*(?i:n[ºo°.]?)?\s*\d+)?"), "[ENDERECO]"),
    (re.compile(r"\b(?i:dr|dra|sr|sra)\.?\s+[A-ZÀ-Ú][\wÀ-ú]+(?:\s+[A-ZÀ-Ú][\wÀ-ú]+)*"), "[NOME]"),
]
_NOME = r"[\wÀ-ú]+(?:\s+(?:d[aeo]s?\s+)?[A-ZÀ-Ú][\wÀ-ú]+)*"
_APRESENTACAO = re.compile(
    # frases sem ambiguidade aceitam nome minúsculo; "sou o/a" exige maiúscula ("sou a mãe dele")
    rf"\b((?i:meu nome [ée]|me chamo|chamo-me|nome dele [ée]|nome dela [ée]|se chama))\s+({_NOME})"
    rf"|\b((?i:sou (?:o|a)))\s+([A-ZÀ-Ú][\wÀ-ú]*(?:\s+(?:d[aeo]s?\s+)?[A-ZÀ-Ú][\wÀ-ú]+)*)")
_CAPITALIZADA = re.compile(r"(?<![.!?]\s)(?<!^)\b[A-ZÀ-Ú][a-zà-ú]{2,}\b")


def anonimizar(texto: str) -> str:
    if not texto:
        return texto
    t = _APRESENTACAO.sub(lambda m: f"{m.group(1) or m.group(3)} [NOME]", texto)
    for padrao, marcador in _PADROES:
        t = padrao.sub(marcador, t)
    return t


def nomes_suspeitos(texto: str) -> list[str]:
    """Palavras com inicial maiúscula fora do começo da frase: podem ser nomes que escaparam."""
    return sorted(set(_CAPITALIZADA.findall(texto or "")))


def faixa_etaria(idade) -> str | None:
    if not isinstance(idade, (int, float)):
        return None
    for limite, faixa in ((12, "0-11"), (18, "12-17"), (40, "18-39"), (60, "40-59"), (80, "60-79")):
        if idade < limite:
            return faixa
    return "80+"


def particao(caso_id: str) -> str:
    return "teste" if int(hashlib.sha256(caso_id.encode()).hexdigest(), 16) % 5 == 0 else "treino"


def _respostas_anonimas(respostas: dict) -> dict:
    saida = {}
    for pid, valor in (respostas or {}).items():
        if pid == "Q01":
            continue  # o relato vai à parte, anonimizado
        if isinstance(valor, str) and pid in PERGUNTAS_TEXTO:
            saida[pid] = anonimizar(valor)
        elif isinstance(valor, dict):
            saida[pid] = {k: (anonimizar(v) if k in PARTES_TEXTO_LIVRE and isinstance(v, str) else v)
                          for k, v in valor.items()}
        else:
            saida[pid] = valor
    return saida


def montar_caso(caso_id: str, ficha: dict, saida: dict, extrator: str, relogio=time.time,
                crua: dict | None = None) -> dict:
    """Transforma ficha + saída do motor num caso anônimo para a base de treino.

    `crua` é a leitura do relato feita pelo extrator ANTES da mescla com as respostas diretas
    (sem ela, sinais que o relato e a resposta direta concordam somem da extração)."""
    dados = dict(ficha.get("dados_atendente") or {})
    idade, sexo = dados.pop("idade", None), dados.pop("sexo_biologico", None)
    relato = anonimizar(saida.get("relato_original") or "")
    sinais = saida.get("sinais", [])
    return {
        "caso_id": caso_id,
        "versao": VERSAO,
        "mes": datetime.fromtimestamp(relogio(), tz=timezone.utc).strftime("%Y-%m"),
        "particao": particao(caso_id),
        "extrator": extrator,
        "faixa_etaria": faixa_etaria(idade),
        "sexo_biologico": sexo,
        "relato": relato,
        "revisar_nomes": nomes_suspeitos(relato),
        # o que o extrator leu no relato
        "extracao": _extracao(crua) if crua is not None else {
            "queixa_principal": anonimizar(saida.get("queixa_principal") or "") or None,
            "queixas": saida.get("queixas", []),
            "duracao": saida.get("duracao"),
            "sinais": [{"nome": s["nome"], "status": s.get("status_no_relato") or s["status"],
                        "trecho": anonimizar(s.get("trecho") or "") or None}
                       for s in sinais if s.get("origem") == "extraido_do_relato" or s.get("status_no_relato")],
        },
        # gabarito: o que o enfermeiro respondeu diretamente e as aferições
        "respostas": _respostas_anonimas(ficha.get("respostas")),
        "afericoes": dados,
        "sinais_finais": [{"nome": s["nome"], "status": s["status"], "origem": s["origem"]} for s in sinais],
        "divergencias": [a["referencias"] for a in saida.get("alertas", []) if a.get("codigo") == "divergencia"],
        "cor": (saida.get("classificacao") or {}).get("cor"),
    }


def _extracao(crua: dict) -> dict:
    alergias = crua.get("alergias") or None
    if alergias:
        alergias = {**alergias, "itens": [anonimizar(i) for i in alergias.get("itens", [])]}
    return {
        "queixa_principal": anonimizar(crua.get("queixa_principal") or "") or None,
        "queixas": crua.get("queixas", []),
        "duracao": crua.get("duracao"),
        "sinais": [{"nome": s["nome"], "status": s["status"], "valor": s.get("valor"),
                    "trecho": anonimizar(s.get("trecho") or "") or None} for s in crua.get("sinais", [])],
        "alergias": alergias,
    }


class BaseTreino:
    def __init__(self, caminho: str = "treino.db", relogio=time.time):
        self._relogio = relogio
        self._trava = threading.Lock()
        self._con = sqlite3.connect(caminho, check_same_thread=False)
        with self._con:
            self._con.execute("""
                CREATE TABLE IF NOT EXISTS casos (
                    caso_id   TEXT PRIMARY KEY,
                    particao  TEXT NOT NULL,
                    mes       TEXT NOT NULL,
                    revisoes  INTEGER NOT NULL DEFAULT 0,
                    dados     TEXT NOT NULL
                )""")

    def fechar(self) -> None:
        self._con.close()

    def registrar(self, caso_id: str, ficha: dict, saida: dict, extrator: str, crua: dict | None = None) -> dict:
        """Grava (ou atualiza, na reclassificação) o caso anônimo deste atendimento."""
        caso = montar_caso(caso_id, ficha, saida, extrator, self._relogio, crua)
        with self._trava, self._con:
            self._con.execute(
                "INSERT INTO casos (caso_id, particao, mes, dados) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(caso_id) DO UPDATE SET dados = excluded.dados, revisoes = revisoes + 1",
                (caso_id, caso["particao"], caso["mes"], json.dumps(caso, ensure_ascii=False)))
        return caso

    def casos(self, particao: str | None = None, sem_revisar: bool = False) -> list[dict]:
        with self._trava:
            linhas = self._con.execute("SELECT dados, revisoes FROM casos ORDER BY rowid").fetchall()
        saida = []
        for dados, revisoes in linhas:
            c = json.loads(dados)
            c["revisoes"] = revisoes
            if particao and c["particao"] != particao:
                continue
            if sem_revisar and c["revisar_nomes"]:
                continue
            saida.append(c)
        return saida

    def resumo(self) -> dict:
        todos = self.casos()
        return {"casos": len(todos),
                "treino": sum(c["particao"] == "treino" for c in todos),
                "teste": sum(c["particao"] == "teste" for c in todos),
                "com_relato": sum(bool(c["relato"]) for c in todos),
                "revisar_nomes": sum(bool(c["revisar_nomes"]) for c in todos)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m triagem.treino",
                                     description="Base de treino do extrator (dados anonimizados; trate como sensível)")
    parser.add_argument("--arquivo", default="treino.db", help="base de treino (padrão: treino.db)")
    sub = parser.add_subparsers(dest="acao", required=True)
    sub.add_parser("resumo", help="quantos casos há em cada partição")
    e = sub.add_parser("exportar", help="exporta os casos em JSONL (uma linha por caso)")
    e.add_argument("--particao", choices=["treino", "teste"], required=True,
                   help="a partição 'teste' nunca deve ser usada para treinar")
    e.add_argument("--saida", required=True)
    e.add_argument("--sem-revisar", action="store_true",
                   help="deixa de fora os casos com possíveis nomes no relato")
    args = parser.parse_args(argv)
    base = BaseTreino(args.arquivo)
    try:
        if args.acao == "resumo":
            print(json.dumps(base.resumo(), ensure_ascii=False, indent=2))
        else:
            casos = base.casos(args.particao, args.sem_revisar)
            with open(args.saida, "w", encoding="utf-8") as f:
                for c in casos:
                    f.write(json.dumps(c, ensure_ascii=False) + "\n")
            print(f"{len(casos)} caso(s) da partição '{args.particao}' em {args.saida}", file=sys.stderr)
    finally:
        base.fechar()
    return 0


if __name__ == "__main__":
    sys.exit(main())
