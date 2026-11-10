"""Página do paciente, aberta pelo QR code no celular (Wi-Fi da unidade).

É um servidor SEPARADO do servidor do enfermeiro e só faz leitura:
  GET /p/<código>     status do próprio paciente (HTML montado aqui, com escape)
  GET /paciente.css   estilo
Qualquer outra rota é 404 e qualquer outro método é 405. Não há rotas de triagem,
de fila nem de exemplos: quem está no Wi-Fi só consegue ver o status de um código
que já tem. A página não usa JavaScript; ela se recarrega sozinha.
"""

import logging
from html import escape
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from triagem.fila import Fila
from triagem.interface.servidor import PASTA_ESTATICA

log = logging.getLogger("triagem.interface")

RECARREGAR_SEGUNDOS = 20
CABECALHOS = {
    "Cache-Control": "no-store",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Content-Security-Policy": ("default-src 'none'; style-src 'self'; img-src 'self' data:; "
                                "base-uri 'none'; form-action 'none'; frame-ancestors 'none'"),
}


def _minutos(m: int) -> str:
    if m <= 0:
        return "imediato"
    if m < 60:
        return f"até {m} min"
    horas, resto = divmod(m, 60)
    return f"até {horas} h" + (f" {resto} min" if resto else "")


def _pagina(titulo: str, corpo: str, recarregar: bool) -> bytes:
    meta = f'<meta http-equiv="refresh" content="{RECARREGAR_SEGUNDOS}">' if recarregar else ""
    return f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
{meta}
<title>{escape(titulo)} · SalUS.ia</title>
<link rel="stylesheet" href="/paciente.css">
</head>
<body>
<main>
{corpo}
<p class="rodape">SalUS.ia · protótipo com dados simulados.</p>
</main>
</body>
</html>
""".encode("utf-8")


def pagina_status(s: dict) -> bytes:
    numero = f"{s['numero']:03d}"
    motivos = "".join(f"<li>{escape(m)}</li>" for m in s["motivos"])
    if s["estado"] == "chamado":
        situacao = ('<section class="chamado" role="status"><h2>Você foi chamado</h2>'
                    "<p>Dirija-se ao atendimento.</p></section>")
    else:
        situacao = (f'<section class="posicao" role="status"><p class="faixa">{escape(s["faixa"])}</p>'
                    f'<p>Você está esperando há {s["espera_min"]} min. '
                    f'Tempo-alvo para a sua cor: <strong>{_minutos(s["tempo_alvo_min"])}</strong>.</p>'
                    "<p class=\"aviso\">Sua posição pode mudar se chegar alguém em situação mais grave. "
                    "Se você piorar, avise a equipe na recepção.</p></section>")
    ordem = "".join(
        f'<li class="cor-{c["cor"]}{" sua" if c["cor"] == s["cor"] else ""}">'
        f'<span class="bolinha"></span><span class="nome">{escape(c["nome"])}</span>'
        f'<span class="tempo">{_minutos(c["tempo_alvo_min"])}</span></li>'
        for c in s["ordem"])
    corpo = f"""
<header><p class="marca">Sal<span>US</span>.ia</p><p class="numero-rotulo">Seu número</p>
<p class="numero">{numero}</p></header>
<section class="cartao cor cor-{s['cor']}"><p class="rotulo">Sua classificação</p>
<p class="nome-cor">{escape(s['nome_cor'])}</p>
<p class="rotulo">Por quê</p><ul class="motivos">{motivos}</ul></section>
{situacao}
<section class="cartao"><h2>Como a fila funciona</h2>
<p>Quem está em situação mais grave é atendido primeiro, não quem chegou antes.
A classificação é feita pela equipe de enfermagem.</p>
<ol class="ordem">{ordem}</ol></section>
"""
    return _pagina(f"Atendimento {numero}", corpo, recarregar=True)


def pagina_invalida() -> bytes:
    corpo = ("<section class=\"cartao\"><h2>Código não encontrado</h2>"
             "<p>Este código não existe ou o atendimento já foi concluído. "
             "Em caso de dúvida, procure a recepção.</p></section>")
    return _pagina("Código não encontrado", corpo, recarregar=False)


class ManipuladorPaciente(BaseHTTPRequestHandler):
    server_version = "SalusIA"
    sys_version = ""

    def log_message(self, formato, *args):
        log.debug(formato, *args)

    def _enviar(self, status: int, corpo: bytes, tipo: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(corpo)))
        for chave, valor in CABECALHOS.items():
            self.send_header(chave, valor)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(corpo)

    def do_GET(self):
        caminho = self.path.split("?", 1)[0]
        if caminho == "/paciente.css":
            return self._enviar(200, (PASTA_ESTATICA / "paciente.css").read_bytes(), "text/css; charset=utf-8")
        if caminho.startswith("/p/"):
            status = self.server.fila.status_paciente(caminho.removeprefix("/p/"))
            if status is not None:
                return self._enviar(200, pagina_status(status), "text/html; charset=utf-8")
        self._enviar(404, pagina_invalida(), "text/html; charset=utf-8")

    do_HEAD = do_GET

    def _nao_permitido(self):
        self.close_connection = True
        self._enviar(HTTPStatus.METHOD_NOT_ALLOWED.value, b"", "text/plain; charset=utf-8")

    do_POST = do_PUT = do_DELETE = do_PATCH = _nao_permitido


class ServidorPaciente(ThreadingHTTPServer):
    allow_reuse_address = False
    daemon_threads = True


def criar_servidor_paciente(fila: Fila, host: str = "0.0.0.0", porta: int = 0) -> ServidorPaciente:
    servidor = ServidorPaciente((host, porta), ManipuladorPaciente)
    servidor.fila = fila
    return servidor
