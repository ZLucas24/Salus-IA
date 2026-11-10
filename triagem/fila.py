"""Fila de atendimento da unidade.

Ordem: cor (mais grave primeiro), depois pontuação dentro da cor (maior primeiro), depois
quem chegou antes. Cada paciente recebe um número de atendimento e um código aleatório
(o do QR), que só serve para consultar o próprio status e deixa de valer quando ele é
atendido.

O paciente nunca vê a pontuação, a posição exata nem dados de outros pacientes: vê a cor,
o motivo em linguagem simples, uma faixa de pessoas à frente e o tempo-alvo da cor. Ele pode
avisar que piorou (um motivo de uma lista fixa); o aviso alerta a equipe, mas não muda a cor
nem a posição.

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

# Aviso de piora: o paciente escolhe UM motivo da lista (sem texto livre). O aviso NÃO muda
# a cor nem a posição; só alerta a equipe, que decide o que fazer.
MOTIVOS_PIORA = {
    "falta_de_ar": "Falta de ar",
    "dor": "A dor aumentou",
    "desmaio": "Tontura ou sensação de desmaio",
    "sangramento": "Sangramento",
    "febre": "Febre ou calafrios",
    "vomito": "Vômito",
    "outro": "Outro motivo",
}
ESPERA_ENTRE_AVISOS_S = 120  # evita repetição acidental do mesmo paciente
AVISO_OK, AVISO_ESPERA, AVISO_INVALIDO = "ok", "espera", "invalido"

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
            # colunas novas em filas criadas por versões anteriores
            colunas = {c["name"] for c in self._con.execute("PRAGMA table_info(pacientes)")}
            for nome, tipo in (("ficha", "TEXT"), ("extrator", "TEXT"), ("reclassificado_em", "REAL"),
                               ("triado_por", "TEXT"), ("chamado_por", "TEXT"), ("atendido_por", "TEXT"),
                               ("caso_id", "TEXT")):
                if nome not in colunas:
                    self._con.execute(f"ALTER TABLE pacientes ADD COLUMN {nome} {tipo}")
            self._con.execute("""
                CREATE TABLE IF NOT EXISTS reclassificacoes (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    numero          INTEGER NOT NULL REFERENCES pacientes(numero),
                    cor_antes       TEXT NOT NULL,
                    cor_depois      TEXT NOT NULL,
                    pontuacao_antes INTEGER NOT NULL,
                    pontuacao_depois INTEGER NOT NULL,
                    em              REAL NOT NULL
                )""")
            if "por" not in {c["name"] for c in self._con.execute("PRAGMA table_info(reclassificacoes)")}:
                self._con.execute("ALTER TABLE reclassificacoes ADD COLUMN por TEXT")
            self._con.execute("""
                CREATE TABLE IF NOT EXISTS avisos (
                    id        INTEGER PRIMARY KEY AUTOINCREMENT,
                    numero    INTEGER NOT NULL REFERENCES pacientes(numero),
                    motivo    TEXT NOT NULL,
                    criado_em REAL NOT NULL,
                    visto_em  REAL
                )""")
            if "visto_por" not in {c["name"] for c in self._con.execute("PRAGMA table_info(avisos)")}:
                self._con.execute("ALTER TABLE avisos ADD COLUMN visto_por TEXT")

    def fechar(self) -> None:
        self._con.close()

    # --- escrita ------------------------------------------------------------------------
    def entrar(self, classificacao: Classificacao, ficha: dict | None = None, extrator: str | None = None,
               por: str | None = None) -> dict:
        """Põe o paciente na fila. A ficha fica guardada (só nesta máquina) para a reclassificação.

        `caso_id` é um código aleatório que liga este atendimento ao registro anônimo da base de
        treino (o registro de lá não tem número, código do QR nem nome)."""
        token = secrets.token_urlsafe(24)
        caso_id = secrets.token_hex(8)
        with self._trava, self._con:
            cur = self._con.execute(
                "INSERT INTO pacientes (token, cor, nivel, pontuacao, motivos, chegada, estado, ficha, extrator, "
                "triado_por, caso_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (token, classificacao.cor.value, classificacao.cor.nivel, classificacao.pontuacao,
                 json.dumps(explicacoes(classificacao), ensure_ascii=False), self._relogio(), AGUARDANDO,
                 json.dumps(ficha, ensure_ascii=False) if ficha is not None else None, extrator, por, caso_id))
        return {"numero": cur.lastrowid, "token": token, "caso_id": caso_id}

    def ficha(self, numero: int) -> dict | None:
        """Ficha guardada de quem ainda está na fila (aguardando ou chamado)."""
        if not isinstance(numero, int) or isinstance(numero, bool):
            return None
        with self._trava:
            p = self._con.execute("SELECT * FROM pacientes WHERE numero = ? AND estado != ?",
                                  (numero, ATENDIDO)).fetchone()
        if p is None:
            return None
        return {"numero": p["numero"], "cor": p["cor"], "pontuacao": p["pontuacao"],
                "ficha": json.loads(p["ficha"]) if p["ficha"] else None, "extrator": p["extrator"],
                "caso_id": p["caso_id"]}

    def reclassificar(self, numero: int, classificacao: Classificacao, ficha: dict, extrator: str,
                      permitir_reducao: bool = False, por: str | None = None) -> dict:
        """Troca a classificação de quem já está na fila, mantendo número, QR e hora de chegada.

        Se a cor nova for MAIS BAIXA, só aplica com `permitir_reducao=True` (confirmação explícita
        do enfermeiro). Reclassificar marca como vistos os avisos de piora pendentes do paciente.
        Devolve {"ok": True, ...} ou {"ok": False, "motivo": "nao_encontrado" | "precisa_confirmar", ...}.
        """
        if not isinstance(numero, int) or isinstance(numero, bool):
            return {"ok": False, "motivo": "nao_encontrado"}
        agora = self._relogio()
        nova = classificacao.cor
        with self._trava, self._con:
            p = self._con.execute("SELECT * FROM pacientes WHERE numero = ? AND estado != ?",
                                  (numero, ATENDIDO)).fetchone()
            if p is None:
                return {"ok": False, "motivo": "nao_encontrado"}
            resumo = {"numero": numero, "cor_antes": p["cor"], "cor_depois": nova.value,
                      "pontuacao_antes": p["pontuacao"], "pontuacao_depois": classificacao.pontuacao,
                      "caso_id": p["caso_id"]}
            if nova.nivel < p["nivel"] and not permitir_reducao:
                return {"ok": False, "motivo": "precisa_confirmar", **resumo}
            self._con.execute(
                "UPDATE pacientes SET cor = ?, nivel = ?, pontuacao = ?, motivos = ?, ficha = ?, extrator = ?, "
                "reclassificado_em = ? WHERE numero = ?",
                (nova.value, nova.nivel, classificacao.pontuacao,
                 json.dumps(explicacoes(classificacao), ensure_ascii=False),
                 json.dumps(ficha, ensure_ascii=False), extrator, agora, numero))
            self._con.execute(
                "INSERT INTO reclassificacoes (numero, cor_antes, cor_depois, pontuacao_antes, pontuacao_depois, "
                "em, por) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (numero, p["cor"], nova.value, p["pontuacao"], classificacao.pontuacao, agora, por))
            self._con.execute("UPDATE avisos SET visto_em = ?, visto_por = ? WHERE numero = ? AND visto_em IS NULL",
                              (agora, por, numero))
        return {"ok": True, **resumo}

    def historico(self, numero: int) -> list[dict]:
        with self._trava:
            linhas = self._con.execute(
                "SELECT cor_antes, cor_depois, pontuacao_antes, pontuacao_depois, em, por FROM reclassificacoes "
                "WHERE numero = ? ORDER BY em, id", (numero,)).fetchall()
        return [dict(x) for x in linhas]

    def chamar(self, numero: int, por: str | None = None) -> bool:
        return self._mudar(numero, CHAMADO, "chamado", por, de=(AGUARDANDO,))

    def concluir(self, numero: int, por: str | None = None) -> bool:
        return self._mudar(numero, ATENDIDO, "atendido", por, de=(AGUARDANDO, CHAMADO))

    def _mudar(self, numero, novo: str, prefixo: str, por: str | None, de: tuple[str, ...]) -> bool:
        if not isinstance(numero, int) or isinstance(numero, bool):
            return False
        marcas = ",".join("?" * len(de))
        with self._trava, self._con:
            cur = self._con.execute(
                f"UPDATE pacientes SET estado = ?, {prefixo}_em = ?, {prefixo}_por = ? "
                f"WHERE numero = ? AND estado IN ({marcas})",
                (novo, self._relogio(), por, numero, *de))
        return cur.rowcount == 1

    def avisar_piora(self, token: str, motivo: str) -> str:
        """Paciente avisa que piorou. Devolve AVISO_OK, AVISO_ESPERA (aviso recente) ou AVISO_INVALIDO."""
        if motivo not in MOTIVOS_PIORA or not isinstance(token, str) or not FORMATO_TOKEN.match(token):
            return AVISO_INVALIDO
        agora = self._relogio()
        with self._trava, self._con:
            p = self._con.execute("SELECT numero, estado FROM pacientes WHERE token = ?", (token,)).fetchone()
            if p is None or p["estado"] == ATENDIDO:
                return AVISO_INVALIDO
            ultimo = self._con.execute("SELECT MAX(criado_em) FROM avisos WHERE numero = ?",
                                       (p["numero"],)).fetchone()[0]
            if ultimo is not None and agora - ultimo < ESPERA_ENTRE_AVISOS_S:
                return AVISO_ESPERA
            self._con.execute("INSERT INTO avisos (numero, motivo, criado_em) VALUES (?, ?, ?)",
                              (p["numero"], motivo, agora))
        return AVISO_OK

    def marcar_aviso_visto(self, numero: int, por: str | None = None) -> bool:
        if not isinstance(numero, int) or isinstance(numero, bool):
            return False
        with self._trava, self._con:
            cur = self._con.execute(
                "UPDATE avisos SET visto_em = ?, visto_por = ? WHERE numero = ? AND visto_em IS NULL",
                (self._relogio(), por, numero))
        return cur.rowcount > 0

    def avisos_pendentes(self) -> list[dict]:
        """Avisos ainda não vistos, de quem não foi atendido, do mais antigo para o mais novo."""
        agora = self._relogio()
        with self._trava:
            linhas = self._con.execute(
                "SELECT a.id, a.numero, a.motivo, a.criado_em, p.cor FROM avisos a "
                "JOIN pacientes p ON p.numero = a.numero "
                "WHERE a.visto_em IS NULL AND p.estado != ? ORDER BY a.criado_em, a.id", (ATENDIDO,)).fetchall()
        return [{"id": a["id"], "numero": a["numero"], "cor": a["cor"], "motivo": MOTIVOS_PIORA[a["motivo"]],
                 "ha_min": int((agora - a["criado_em"]) // 60)} for a in linhas]

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
        avisos: dict[int, list[dict]] = {}
        for a in self.avisos_pendentes():
            avisos.setdefault(a["numero"], []).append({"motivo": a["motivo"], "ha_min": a["ha_min"]})
        linhas = []
        for posicao, p in enumerate(fila, start=1):
            linhas.append(self._linha(p, agora, posicao, avisos))
        return [self._linha(p, agora, None, avisos) for p in chamados] + linhas

    def _linha(self, p: sqlite3.Row, agora: float, posicao: int | None, avisos: dict) -> dict:
        return {"numero": p["numero"], "cor": p["cor"], "pontuacao": p["pontuacao"],
                "motivos": json.loads(p["motivos"]), "estado": p["estado"], "posicao": posicao,
                "espera_min": int((agora - p["chegada"]) // 60), "token": p["token"],
                "avisos_piora": avisos.get(p["numero"], []), "triado_por": p["triado_por"],
                "reclassificado_ha_min": (int((agora - p["reclassificado_em"]) // 60)
                                          if p["reclassificado_em"] is not None else None)}

    def status_paciente(self, token: str) -> dict | None:
        """Visão do paciente. None se o código não existe ou já foi atendido."""
        if not isinstance(token, str) or not FORMATO_TOKEN.match(token):
            return None
        with self._trava:
            p = self._con.execute("SELECT * FROM pacientes WHERE token = ?", (token,)).fetchone()
            if p is None or p["estado"] == ATENDIDO:
                return None
            fila = self._aguardando()
            ultimo = self._con.execute(
                "SELECT motivo, criado_em, visto_em FROM avisos WHERE numero = ? "
                "ORDER BY criado_em DESC, id DESC LIMIT 1", (p["numero"],)).fetchone()
        agora = self._relogio()
        aviso = None
        if ultimo is not None:
            aviso = {"motivo": MOTIVOS_PIORA[ultimo["motivo"]], "ha_min": int((agora - ultimo["criado_em"]) // 60),
                     "visto": ultimo["visto_em"] is not None,
                     "pode_avisar_de_novo": agora - ultimo["criado_em"] >= ESPERA_ENTRE_AVISOS_S}
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
            "espera_min": int((agora - p["chegada"]) // 60),
            "ordem": ordem_das_cores(),
            "aviso": aviso,
            "revisado": p["reclassificado_em"] is not None,
            "motivos_piora": [{"codigo": k, "texto": v} for k, v in MOTIVOS_PIORA.items()],
        }
