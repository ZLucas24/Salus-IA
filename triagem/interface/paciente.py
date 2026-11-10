"""Página do paciente, aberta pelo QR code no celular (Wi-Fi da unidade).

É um servidor SEPARADO do servidor do enfermeiro:
  GET  /p/<código>         status do próprio paciente (HTML montado aqui, com escape)
  POST /p/<código>/piora   aviso de piora: um motivo de uma lista fixa (formulário, sem texto livre)
  GET  /paciente.css       estilo
Qualquer outra rota é 404 e qualquer outro método é 405. Não há rotas de triagem,
de fila nem de exemplos: quem está no Wi-Fi só vê o status de um código que já tem e
só consegue mandar o aviso de piora desse mesmo código. A página não usa JavaScript;
ela se recarrega sozinha.
"""

import logging
from html import escape
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs

from triagem.fila import AVISO_ESPERA, AVISO_OK, Fila
from triagem.interface.servidor import PASTA_ESTATICA

log = logging.getLogger("triagem.interface")

RECARREGAR_SEGUNDOS = 20
LIMITE_FORMULARIO = 200
CABECALHOS = {
    "Cache-Control": "no-store",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Content-Security-Policy": ("default-src 'none'; style-src 'self'; img-src 'self' data:; "
                                "base-uri 'none'; form-action 'self'; frame-ancestors 'none'"),
}
MENSAGENS = {
    "enviado": "Aviso enviado. A equipe de enfermagem foi alertada.",
    "espera": "Você acabou de enviar um aviso. Aguarde um pouco antes de mandar outro.",
    "erro": "Não foi possível enviar o aviso. Procure a recepção.",
}


def _minutos(m: int) -> str:
    if m <= 0:
        return "imediato"
    if m < 60:
        return f"até {m} min"
    horas, resto = divmod(m, 60)
    return f"até {horas} h" + (f" {resto} min" if resto else "")


def _pagina(titulo: str, corpo: str, recarregar: str | None) -> bytes:
    """`recarregar` é o endereço para onde a página volta sozinha (None = não recarrega)."""
    meta = (f'<meta http-equiv="refresh" content="{RECARREGAR_SEGUNDOS};url={escape(recarregar)}">'
            if recarregar else "")
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


def _secao_piora(s: dict, token: str, mensagem: str | None) -> str:
    urgente = ('<p class="urgente">Se tiver <strong>falta de ar forte, dor no peito forte ou desmaio</strong>, '
               "chame alguém da equipe ou vá à recepção <strong>agora</strong>. Não espere pelo celular.</p>")
    partes = ['<section class="cartao piora" aria-labelledby="t-piora"><h2 id="t-piora">Piorou enquanto espera?</h2>',
              urgente]
    if mensagem in MENSAGENS:
        partes.append(f'<p class="msg msg-{escape(mensagem)}" role="status">{escape(MENSAGENS[mensagem])}</p>')
    aviso = s["aviso"]
    if aviso:
        quando = "agora há pouco" if aviso["ha_min"] == 0 else f"há {aviso['ha_min']} min"
        estado = "A equipe já viu." if aviso["visto"] else "Aguardando a equipe ver."
        partes.append(f'<p class="ultimo-aviso">Seu último aviso: <strong>{escape(aviso["motivo"])}</strong>, '
                      f"{quando}. {estado}</p>")
    if aviso and not aviso["pode_avisar_de_novo"]:
        partes.append('<p class="aviso">Você poderá mandar outro aviso em alguns minutos.</p>')
    else:
        botoes = "".join(f'<button type="submit" name="motivo" value="{escape(m["codigo"])}">{escape(m["texto"])}</button>'
                         for m in s["motivos_piora"])
        partes.append(f'<p>Toque no que piorou para avisar a equipe:</p>'
                      f'<form method="post" action="/p/{escape(token)}/piora" class="botoes-piora">{botoes}</form>'
                      '<p class="aviso">O aviso não muda sua classificação sozinho: a equipe avalia e decide.</p>')
    partes.append("</section>")
    return "".join(partes)


def pagina_status(s: dict, token: str = "", mensagem: str | None = None) -> bytes:
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
                    "Se piorar, use o quadro abaixo ou avise a recepção.</p></section>")
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
{'<p class="revisado">A equipe revisou sua classificação.</p>' if s.get('revisado') else ''}
<p class="rotulo">Por quê</p><ul class="motivos">{motivos}</ul></section>
{situacao}
{_secao_piora(s, token, mensagem) if s["estado"] == "aguardando" else ""}
<section class="cartao"><h2>Como a fila funciona</h2>
<p>Quem está em situação mais grave é atendido primeiro, não quem chegou antes.
A classificação é feita pela equipe de enfermagem.</p>
<ol class="ordem">{ordem}</ol></section>
"""
    return _pagina(f"Atendimento {numero}", corpo, recarregar=f"/p/{token}")


def pagina_invalida() -> bytes:
    corpo = ("<section class=\"cartao\"><h2>Código não encontrado</h2>"
             "<p>Este código não existe ou o atendimento já foi concluído. "
             "Em caso de dúvida, procure a recepção.</p></section>")
    return _pagina("Código não encontrado", corpo, recarregar=None)


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
        caminho, _, consulta = self.path.partition("?")
        if caminho == "/paciente.css":
            return self._enviar(200, (PASTA_ESTATICA / "paciente.css").read_bytes(), "text/css; charset=utf-8")
        if caminho.startswith("/p/"):
            token = caminho.removeprefix("/p/")
            status = self.server.fila.status_paciente(token)
            if status is not None:
                mensagem = parse_qs(consulta).get("aviso", [None])[0]
                return self._enviar(200, pagina_status(status, token, mensagem), "text/html; charset=utf-8")
        self._enviar(404, pagina_invalida(), "text/html; charset=utf-8")

    do_HEAD = do_GET

    def do_POST(self):
        """Só aceita o aviso de piora: POST /p/<código>/piora com motivo=<código da lista>."""
        caminho = self.path.split("?", 1)[0]
        try:
            tamanho = int(self.headers.get("Content-Length", ""))
        except ValueError:
            tamanho = -1
        if not (caminho.startswith("/p/") and caminho.endswith("/piora")):
            return self._nao_permitido()
        if not 0 < tamanho <= LIMITE_FORMULARIO:
            self.close_connection = True
            return self._enviar(413, pagina_invalida(), "text/html; charset=utf-8")
        corpo = self.rfile.read(tamanho)
        if not self.headers.get("Content-Type", "").startswith("application/x-www-form-urlencoded"):
            return self._enviar(415, pagina_invalida(), "text/html; charset=utf-8")
        token = caminho.removeprefix("/p/").removesuffix("/piora")
        if self.server.fila.status_paciente(token) is None:
            return self._enviar(404, pagina_invalida(), "text/html; charset=utf-8")
        motivo = parse_qs(corpo.decode("utf-8", "replace")).get("motivo", [""])[0]
        resultado = self.server.fila.avisar_piora(token, motivo)
        if resultado == AVISO_OK:
            log.warning("paciente avisou piora pelo QR (%s)", motivo)
        mensagem = {AVISO_OK: "enviado", AVISO_ESPERA: "espera"}.get(resultado, "erro")
        # POST -> redirect -> GET: recarregar a página não reenvia o aviso
        self.send_response(HTTPStatus.SEE_OTHER)
        self.send_header("Location", f"/p/{token}?aviso={mensagem}")
        self.send_header("Content-Length", "0")
        for chave, valor in CABECALHOS.items():
            self.send_header(chave, valor)
        self.end_headers()

    def _nao_permitido(self):
        self.close_connection = True
        self._enviar(HTTPStatus.METHOD_NOT_ALLOWED.value, b"", "text/plain; charset=utf-8")

    do_PUT = do_DELETE = do_PATCH = _nao_permitido


class ServidorPaciente(ThreadingHTTPServer):
    allow_reuse_address = False
    daemon_threads = True


def criar_servidor_paciente(fila: Fila, host: str = "0.0.0.0", porta: int = 0) -> ServidorPaciente:
    servidor = ServidorPaciente((host, porta), ManipuladorPaciente)
    servidor.fila = fila
    return servidor
