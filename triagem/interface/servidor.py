"""Servidor local da interface (somente biblioteca padrão).

Escuta apenas em 127.0.0.1 e serve:
  GET  /                      a página
  GET  /estatico/<arquivo>    css e js
  GET  /api/questionario      perguntas, módulos, aferições e extratores disponíveis
  GET  /api/exemplos          as fichas de `exemplos/`
  POST /api/triagem           {"ficha": {...}, "extrator": "mock"} -> {"saida": {...}}
                              ou 422 {"erros": [...]} quando a ficha é inválida

Defesas simples, porque o conteúdo é de saúde (mesmo que simulado): só loopback,
checagem de Host e Origin (contra DNS rebinding e requisições de outros sites),
limite de tamanho, cabeçalhos restritivos e nenhum arquivo servido fora da lista.
"""

import json
import logging
import re
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from triagem.entrevista import FichaInvalida, processar_ficha
from triagem.extracao import NOME_PADRAO, NOMES_EXTRATORES, criar_extrator
from triagem.questionario import carregar_questionario
from triagem.regras import carregar_regras

log = logging.getLogger("triagem.interface")

PASTA_ESTATICA = Path(__file__).parent / "estatico"
PASTA_EXEMPLOS = Path(__file__).parents[2] / "exemplos"
LIMITE_CORPO = 1_000_000
TIPOS = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
         ".css": "text/css; charset=utf-8"}
CABECALHOS_SEGURANCA = {
    "Cache-Control": "no-store",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Content-Security-Policy": ("default-src 'none'; script-src 'self'; style-src 'self'; "
                                "connect-src 'self'; img-src 'self' data:; base-uri 'none'; "
                                "form-action 'none'; frame-ancestors 'none'"),
}
NOME_ARQUIVO = re.compile(r"^[a-z0-9_.-]+$")


def dados_para_interface() -> dict:
    q = carregar_questionario()
    regras = carregar_regras()
    return {
        "versao": q["versao"], "revisao_clinica": q["revisao_clinica"],
        "obrigatoriedade": q["obrigatoriedade"], "modulos": q["modulos"],
        "perguntas": q["perguntas"], "afericoes": q["afericoes"],
        "extratores": list(NOMES_EXTRATORES), "extrator_padrao": NOME_PADRAO,
        "regras": {"validado": regras["validado"], "aviso": regras["aviso"]},
    }


def listar_exemplos() -> list[dict]:
    exemplos = []
    for arquivo in sorted(PASTA_EXEMPLOS.glob("*.json")):
        try:
            ficha = json.loads(arquivo.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            continue
        nome = arquivo.stem
        titulo = re.sub(r"^ficha_(\d+_)?", "", nome).replace("_", " ").strip().capitalize()
        exemplos.append({"nome": nome, "titulo": titulo or nome, "ficha": ficha,
                         "falha_proposital": nome.endswith("_falha")})
    return exemplos


def calcular(ficha, nome_extrator: str) -> tuple[int, dict]:
    """Roda o fluxo real. Devolve (status HTTP, corpo)."""
    if nome_extrator not in NOMES_EXTRATORES:
        return 400, {"erros": [f"extrator desconhecido: {nome_extrator!r}"]}
    try:
        saida = processar_ficha(ficha, criar_extrator(nome_extrator))
    except FichaInvalida as e:
        return 422, {"erros": e.erros}
    return 200, {"saida": saida.model_dump(mode="json")}


class Manipulador(BaseHTTPRequestHandler):
    server_version = "SalusIA"
    sys_version = ""

    def log_message(self, formato, *args):  # silencia o log por requisição; erros vão pelo logging
        log.debug(formato, *args)

    # --- respostas -----------------------------------------------------------------
    def _enviar(self, status: int, corpo: bytes, tipo: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(corpo)))
        for chave, valor in CABECALHOS_SEGURANCA.items():
            self.send_header(chave, valor)
        self.end_headers()
        self.wfile.write(corpo)

    def _json(self, status: int, dados) -> None:
        corpo = json.dumps(dados, ensure_ascii=False).encode("utf-8")
        self._enviar(status, corpo, "application/json; charset=utf-8")

    def _erro(self, status: HTTPStatus, mensagem: str) -> None:
        self._json(status.value, {"erros": [mensagem]})

    # --- proteção ----------------------------------------------------------------------
    def _origem_confiavel(self, metodo_escreve: bool) -> bool:
        permitidos = self.server.hosts_permitidos
        if self.headers.get("Host", "") not in permitidos:
            return False
        origem = self.headers.get("Origin")
        if metodo_escreve and origem is not None:
            return origem in {f"http://{h}" for h in permitidos}
        return True

    # --- rotas --------------------------------------------------------------------------
    def do_GET(self):
        if not self._origem_confiavel(False):
            return self._erro(HTTPStatus.FORBIDDEN, "host não permitido")
        caminho = self.path.split("?", 1)[0]
        if caminho in ("/", "/index.html"):
            return self._arquivo("index.html")
        if caminho.startswith("/estatico/"):
            return self._arquivo(caminho.removeprefix("/estatico/"))
        if caminho == "/api/questionario":
            return self._json(200, dados_para_interface())
        if caminho == "/api/exemplos":
            return self._json(200, listar_exemplos())
        self._erro(HTTPStatus.NOT_FOUND, "não encontrado")

    def _arquivo(self, nome: str) -> None:
        arquivo = PASTA_ESTATICA / nome
        if not NOME_ARQUIVO.match(nome) or arquivo.suffix not in TIPOS or not arquivo.is_file():
            return self._erro(HTTPStatus.NOT_FOUND, "não encontrado")
        self._enviar(200, arquivo.read_bytes(), TIPOS[arquivo.suffix])

    def do_POST(self):
        if not self._origem_confiavel(True):
            return self._erro(HTTPStatus.FORBIDDEN, "origem não permitida")
        if self.path.split("?", 1)[0] != "/api/triagem":
            return self._erro(HTTPStatus.NOT_FOUND, "não encontrado")
        if not self.headers.get("Content-Type", "").startswith("application/json"):
            return self._erro(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, "envie application/json")
        try:
            tamanho = int(self.headers.get("Content-Length", ""))
        except ValueError:
            return self._erro(HTTPStatus.LENGTH_REQUIRED, "Content-Length obrigatório")
        if not 0 < tamanho <= LIMITE_CORPO:
            return self._erro(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "corpo vazio ou grande demais")
        try:
            corpo = json.loads(self.rfile.read(tamanho).decode("utf-8-sig"))
            ficha, extrator = corpo["ficha"], corpo.get("extrator", NOME_PADRAO)
        except (ValueError, KeyError, TypeError, AttributeError):
            return self._erro(HTTPStatus.BAD_REQUEST, 'JSON inválido; esperado {"ficha": {...}}')
        try:
            status, resposta = calcular(ficha, extrator)
        except Exception:  # bug do sistema: não vaza detalhes ao navegador
            log.exception("erro interno ao processar a ficha")
            return self._erro(HTTPStatus.INTERNAL_SERVER_ERROR, "erro interno; veja o terminal")
        self._json(status, resposta)


class ServidorLocal(ThreadingHTTPServer):
    # No Windows, SO_REUSEADDR deixaria outro processo abrir a MESMA porta ao mesmo tempo
    allow_reuse_address = False
    daemon_threads = True


def criar_servidor(porta: int = 0) -> ServidorLocal:
    """Cria o servidor em loopback (porta 0 = qualquer porta livre)."""
    servidor = ServidorLocal(("127.0.0.1", porta), Manipulador)
    p = servidor.server_address[1]
    servidor.hosts_permitidos = {f"127.0.0.1:{p}", f"localhost:{p}"}
    return servidor


def main(argv: list[str] | None = None) -> int:
    import argparse
    import webbrowser

    from triagem.cli import carregar_env, configurar_io

    parser = argparse.ArgumentParser(
        prog="python -m triagem.interface",
        description="Interface web local do Salus IA (dados simulados; só aceita conexões locais)")
    parser.add_argument("--porta", type=int, default=8765)
    parser.add_argument("--abrir", action="store_true", help="abre o navegador")
    args = parser.parse_args(argv)
    configurar_io()
    carregar_env()
    try:
        servidor = criar_servidor(args.porta)
    except OSError as e:
        log.error("não foi possível usar a porta %d: %s", args.porta, e)
        return 2
    url = f"http://127.0.0.1:{servidor.server_address[1]}/"
    log.info("interface em %s (Ctrl+C para encerrar)", url)
    if args.abrir:
        webbrowser.open(url)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        log.info("encerrando")
    finally:
        servidor.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
