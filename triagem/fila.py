"""Fila de atendimento da unidade.

Ordem: cor (mais grave primeiro), depois pontuação dentro da cor (maior primeiro), depois
quem chegou antes. Cada paciente recebe um número de atendimento e um código aleatório
(o do QR), que só serve para consultar o próprio status e deixa de valer quando ele é
atendido.

O paciente nunca vê a pontuação, a posição exata nem dados de outros pacientes: vê a cor,
o motivo em linguagem simples, uma faixa de pessoas à frente e o tempo-alvo da cor.

Guarda tudo num SQLite local (biblioteca padrão), para a fila sobreviver a um reinício.
"""

import json
import re
import secrets
import sqlite3
import threading
import time

from triagem.regras import carregar_regras
from triagem.schema import Classificacao
from triagem.sinais import Cor

AGUARDANDO, CHAMADO, ATENDIDO = "aguardando", "chamado", "atendido"
FORMATO_TOKEN = re.compile(r"^[A-Za-z0-9_-]{20,64}$")

# (mínimo, máximo, texto) de pessoas à frente; máximo None = sem limite
FAIXAS = [
    (0, 0, "Você é o próximo"),
    (1, 3, "De 1 a 3 pessoas antes de você"),
    (4, 6, "De 4 a 6 pessoas antes de você"),
    (7, 10, "De 7 a 10 pessoas antes de você"),
    (11, None, "Mais de 10 pessoas antes de você"),
]

NOME_COR = {
    Cor.VERMELHO: "Vermelho — emergência",
    Cor.LARANJA: "Laranja — muito urgente",
    Cor.AMARELO: "Amarelo — urgente",
    Cor.VERDE: "Verde — pouco urgente",
    Cor.AZUL: "Azul — não urgente",
}


def faixa(a_frente: int) -> str:
    for minimo, maximo, texto in FAIXAS:
        if a_frente >= minimo and (maximo is None or a_frente <= maximo):
            return texto
    raise ValueError(f"número de pessoas à frente inválido: {a_frente}")


def explicacoes(classificacao: Classificacao) -> list[str]:
    """Motivo da cor em linguagem simples, a partir das regras de cor aplicadas."""
    regras = carregar_regras()
    textos = {r["id"]: r["explicacao_paciente"] for r in regras["pontuacao"]["regras_cor"]}
    motivos = []
    for r in classificacao.regras_aplicadas:
        texto = textos.get(r.id) or (regras["fila"]["explicacao_promocao"] if r.id == "PROMOCAO" else None)
        if texto and texto not in motivos:
            motivos.append(texto)
    return motivos or [regras["fila"]["explicacao_sem_regra"]]


def ordem_das_cores() -> list[dict]:
    """A regra geral da fila, para o paciente entender por que alguém passa na frente."""
    tempos = carregar_regras()["fila"]["tempos_alvo_minutos"]
    return [{"cor": c.value, "nome": NOME_COR[c], "tempo_alvo_min": tempos[c.value]}
            for c in sorted(Cor, key=lambda c: c.nivel, reverse=True)]


class Fila:
    def __init__(self, caminho: str = ":memory:", relogio=time.time):
        self._relogio = relogio
        self._trava = threading.Lock()
        self._con = sqlite3.connect(caminho, check_same_thread=False)
        self._con.row_factory = sqlite3.Row
        with self._con:
            self._con.execute("""
                CREATE TABLE IF NOT EXISTS pacientes (
                    numero     INTEGER PRIMARY KEY AUTOINCREMENT,
                    token      TEXT UNIQUE NOT NULL,
                    cor        TEXT NOT NULL,
                    nivel      INTEGER NOT NULL,
                    pontuacao  INTEGER NOT NULL,
                    motivos    TEXT NOT NULL,
                    chegada    REAL NOT NULL,
                    estado     TEXT NOT NULL,
                    chamado_em REAL,
                    atendido_em REAL
                )""")

    def fechar(self) -> None:
        self._con.close()

    # --- escrita ------------------------------------------------------------------------
    def entrar(self, classificacao: Classificacao) -> dict:
        token = secrets.token_urlsafe(24)
        with self._trava, self._con:
            cur = self._con.execute(
                "INSERT INTO pacientes (token, cor, nivel, pontuacao, motivos, chegada, estado) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (token, classificacao.cor.value, classificacao.cor.nivel, classificacao.pontuacao,
                 json.dumps(explicacoes(classificacao), ensure_ascii=False), self._relogio(), AGUARDANDO))
        return {"numero": cur.lastrowid, "token": token}

    def chamar(self, numero: int) -> bool:
        return self._mudar(numero, CHAMADO, "chamado_em", de=(AGUARDANDO,))

    def concluir(self, numero: int) -> bool:
        return self._mudar(numero, ATENDIDO, "atendido_em", de=(AGUARDANDO, CHAMADO))

    def _mudar(self, numero, novo: str, coluna: str, de: tuple[str, ...]) -> bool:
        if not isinstance(numero, int) or isinstance(numero, bool):
            return False
        marcas = ",".join("?" * len(de))
        with self._trava, self._con:
            cur = self._con.execute(
                f"UPDATE pacientes SET estado = ?, {coluna} = ? WHERE numero = ? AND estado IN ({marcas})",
                (novo, self._relogio(), numero, *de))
        return cur.rowcount == 1

    # --- leitura ------------------------------------------------------------------------
    def _aguardando(self) -> list[sqlite3.Row]:
        return self._con.execute(
            "SELECT * FROM pacientes WHERE estado = ? "
            "ORDER BY nivel DESC, pontuacao DESC, chegada ASC, numero ASC", (AGUARDANDO,)).fetchall()

    def listar(self) -> list[dict]:
        """Visão do enfermeiro: chamados primeiro, depois a fila em ordem."""
        agora = self._relogio()
        with self._trava:
            chamados = self._con.execute(
                "SELECT * FROM pacientes WHERE estado = ? ORDER BY chamado_em", (CHAMADO,)).fetchall()
            fila = self._aguardando()
        linhas = []
        for posicao, p in enumerate(fila, start=1):
            linhas.append(self._linha(p, agora, posicao))
        return [self._linha(p, agora, None) for p in chamados] + linhas

    def _linha(self, p: sqlite3.Row, agora: float, posicao: int | None) -> dict:
        return {"numero": p["numero"], "cor": p["cor"], "pontuacao": p["pontuacao"],
                "motivos": json.loads(p["motivos"]), "estado": p["estado"], "posicao": posicao,
                "espera_min": int((agora - p["chegada"]) // 60), "token": p["token"]}

    def status_paciente(self, token: str) -> dict | None:
        """Visão do paciente. None se o código não existe ou já foi atendido."""
        if not isinstance(token, str) or not FORMATO_TOKEN.match(token):
            return None
        with self._trava:
            p = self._con.execute("SELECT * FROM pacientes WHERE token = ?", (token,)).fetchone()
            if p is None or p["estado"] == ATENDIDO:
                return None
            fila = self._aguardando()
        cor = Cor(p["cor"])
        a_frente = next((i for i, x in enumerate(fila) if x["numero"] == p["numero"]), None)
        return {
            "numero": p["numero"],
            "cor": cor.value,
            "nome_cor": NOME_COR[cor],
            "motivos": json.loads(p["motivos"]),
            "estado": p["estado"],
            "faixa": faixa(a_frente) if a_frente is not None else None,
            "tempo_alvo_min": carregar_regras()["fila"]["tempos_alvo_minutos"][cor.value],
            "espera_min": int((self._relogio() - p["chegada"]) // 60),
            "ordem": ordem_das_cores(),
        }
