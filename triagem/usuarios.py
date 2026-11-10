"""Contas de enfermeiro e sessões da tela do enfermeiro.

- Senhas guardadas com scrypt (biblioteca padrão), com sal aleatório; nunca em texto.
- Sessões só na memória do servidor: reiniciar a interface desloga todo mundo.
- Bloqueio de 5 minutos depois de 5 senhas erradas seguidas no mesmo login.

Comandos (a senha é pedida sem aparecer na tela):
  python -m triagem.usuarios criar <login> --nome "Maria Souza"
  python -m triagem.usuarios listar
  python -m triagem.usuarios desativar <login>
  python -m triagem.usuarios senha <login>
"""

import argparse
import getpass
import hashlib
import hmac
import logging
import re
import secrets
import sqlite3
import sys
import threading
import time

log = logging.getLogger("triagem.usuarios")

FORMATO_LOGIN = re.compile(r"^[a-z0-9._-]{3,32}$")
SENHA_MINIMA = 8
SESSAO_MAX_S = 12 * 3600       # um plantão
SESSAO_OCIOSA_S = 60 * 60      # sem uso por 1 hora, pede a senha de novo
TENTATIVAS = 5
BLOQUEIO_S = 5 * 60
_SCRYPT = {"n": 2 ** 14, "r": 8, "p": 1, "dklen": 32}


class ErroUsuario(ValueError):
    pass


def _hash(senha: str, sal: bytes) -> bytes:
    return hashlib.scrypt(senha.encode("utf-8"), salt=sal, **_SCRYPT)


class Usuarios:
    def __init__(self, caminho: str = "usuarios.db", relogio=time.time):
        self._relogio = relogio
        self._trava = threading.Lock()
        self._con = sqlite3.connect(caminho, check_same_thread=False)
        self._con.row_factory = sqlite3.Row
        with self._con:
            self._con.execute("""
                CREATE TABLE IF NOT EXISTS usuarios (
                    login     TEXT PRIMARY KEY,
                    nome      TEXT NOT NULL,
                    sal       BLOB NOT NULL,
                    hash      BLOB NOT NULL,
                    ativo     INTEGER NOT NULL DEFAULT 1,
                    criado_em REAL NOT NULL
                )""")
        self._sessoes: dict[str, dict] = {}
        self._falhas: dict[str, tuple[int, float]] = {}

    def fechar(self) -> None:
        self._con.close()

    # --- contas -------------------------------------------------------------------------
    def criar(self, login: str, nome: str, senha: str) -> None:
        login = (login or "").strip().lower()
        if not FORMATO_LOGIN.match(login):
            raise ErroUsuario("login: 3 a 32 caracteres, só letras minúsculas, números, ponto, hífen ou _")
        if not (nome or "").strip():
            raise ErroUsuario("informe o nome")
        if len(senha or "") < SENHA_MINIMA:
            raise ErroUsuario(f"a senha precisa de pelo menos {SENHA_MINIMA} caracteres")
        sal = secrets.token_bytes(16)
        try:
            with self._trava, self._con:
                self._con.execute("INSERT INTO usuarios (login, nome, sal, hash, criado_em) VALUES (?, ?, ?, ?, ?)",
                                  (login, nome.strip(), sal, _hash(senha, sal), self._relogio()))
        except sqlite3.IntegrityError:
            raise ErroUsuario(f"o login {login!r} já existe") from None

    def trocar_senha(self, login: str, senha: str) -> None:
        if len(senha or "") < SENHA_MINIMA:
            raise ErroUsuario(f"a senha precisa de pelo menos {SENHA_MINIMA} caracteres")
        sal = secrets.token_bytes(16)
        with self._trava, self._con:
            cur = self._con.execute("UPDATE usuarios SET sal = ?, hash = ? WHERE login = ?",
                                    (sal, _hash(senha, sal), login))
        if cur.rowcount == 0:
            raise ErroUsuario(f"login {login!r} não existe")
        self._encerrar_sessoes(login)

    def desativar(self, login: str) -> bool:
        with self._trava, self._con:
            cur = self._con.execute("UPDATE usuarios SET ativo = 0 WHERE login = ?", (login,))
        self._encerrar_sessoes(login)
        return cur.rowcount == 1

    def listar(self) -> list[dict]:
        with self._trava:
            linhas = self._con.execute("SELECT login, nome, ativo FROM usuarios ORDER BY login").fetchall()
        return [dict(x) for x in linhas]

    def existe_algum_ativo(self) -> bool:
        with self._trava:
            return self._con.execute("SELECT 1 FROM usuarios WHERE ativo = 1 LIMIT 1").fetchone() is not None

    # --- login e sessões ---------------------------------------------------------------------
    def entrar(self, login: str, senha: str) -> str | None:
        """Devolve o código da sessão, ou None (login/senha errados, conta inativa ou bloqueada)."""
        login = (login or "").strip().lower()
        agora = self._relogio()
        falhas, desde = self._falhas.get(login, (0, 0.0))
        if falhas >= TENTATIVAS and agora - desde < BLOQUEIO_S:
            log.warning("login bloqueado por tentativas: %s", login)
            return None
        with self._trava:
            u = self._con.execute("SELECT * FROM usuarios WHERE login = ? AND ativo = 1", (login,)).fetchone()
        # calcula o hash mesmo sem usuário, para o tempo de resposta não revelar quais logins existem
        sal = u["sal"] if u else b"\0" * 16
        certo = hmac.compare_digest(_hash(senha or "", sal), u["hash"] if u else b"\0" * 32)
        if not (u and certo):
            self._falhas[login] = (falhas + 1 if agora - desde < BLOQUEIO_S else 1, agora)
            return None
        self._falhas.pop(login, None)
        sessao = secrets.token_urlsafe(32)
        with self._trava:
            self._sessoes[sessao] = {"login": login, "nome": u["nome"], "inicio": agora, "uso": agora}
        return sessao

    def sessao(self, codigo: str | None) -> dict | None:
        """Quem está logado com este código (e renova o tempo ocioso), ou None."""
        if not codigo:
            return None
        agora = self._relogio()
        with self._trava:
            s = self._sessoes.get(codigo)
            if s is None:
                return None
            if agora - s["inicio"] > SESSAO_MAX_S or agora - s["uso"] > SESSAO_OCIOSA_S:
                del self._sessoes[codigo]
                return None
            s["uso"] = agora
            return {"login": s["login"], "nome": s["nome"]}

    def sair(self, codigo: str | None) -> None:
        with self._trava:
            self._sessoes.pop(codigo or "", None)

    def _encerrar_sessoes(self, login: str) -> None:
        with self._trava:
            for codigo in [c for c, s in self._sessoes.items() if s["login"] == login]:
                del self._sessoes[codigo]


# --- comando --------------------------------------------------------------------------------

def _pedir_senha() -> str:
    senha = getpass.getpass("Senha: ")
    if senha != getpass.getpass("Repita a senha: "):
        raise ErroUsuario("as senhas não conferem")
    return senha


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m triagem.usuarios",
                                     description="Contas de enfermeiro da interface do Salus IA")
    parser.add_argument("--arquivo", default="usuarios.db", help="banco de contas (padrão: usuarios.db)")
    sub = parser.add_subparsers(dest="acao", required=True)
    c = sub.add_parser("criar", help="cria uma conta (pede a senha)")
    c.add_argument("login")
    c.add_argument("--nome", required=True)
    sub.add_parser("listar", help="lista as contas")
    d = sub.add_parser("desativar", help="desativa uma conta e encerra as sessões dela")
    d.add_argument("login")
    s = sub.add_parser("senha", help="troca a senha de uma conta")
    s.add_argument("login")
    args = parser.parse_args(argv)
    usuarios = Usuarios(args.arquivo)
    try:
        if args.acao == "criar":
            usuarios.criar(args.login, args.nome, _pedir_senha())
            print(f"conta criada: {args.login.strip().lower()}", file=sys.stderr)
        elif args.acao == "listar":
            for u in usuarios.listar():
                print(f"{u['login']:<20} {u['nome']}{'' if u['ativo'] else '  (desativada)'}")
        elif args.acao == "desativar":
            if not usuarios.desativar(args.login):
                raise ErroUsuario(f"login {args.login!r} não existe")
            print(f"conta desativada: {args.login}", file=sys.stderr)
        elif args.acao == "senha":
            usuarios.trocar_senha(args.login, _pedir_senha())
            print(f"senha trocada: {args.login}", file=sys.stderr)
    except ErroUsuario as e:
        print(f"erro: {e}", file=sys.stderr)
        return 1
    finally:
        usuarios.fechar()
    return 0


if __name__ == "__main__":
    sys.exit(main())
