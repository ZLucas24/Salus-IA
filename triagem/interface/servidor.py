"""Servidor local da interface (somente biblioteca padrão).

Escuta apenas em 127.0.0.1 e serve:
  GET  /                      a página
  GET  /estatico/<arquivo>    css e js
  GET  /api/questionario      perguntas, módulos, aferições e extratores disponíveis
  GET  /api/exemplos          as fichas de `exemplos/`
  POST /api/triagem           {"ficha": {...}, "extrator": "mock"} -> {"saida": {...}}
                              ou 422 {"erros": [...]} quando a ficha é inválida
  GET  /api/fila              pacientes chamados e aguardando, em ordem
  POST /api/fila              {"ficha": {...}, "extrator": "mock"} -> {"numero", "url", "qr"}
                              (a ficha é processada de novo aqui; o navegador não manda a cor)
  POST /api/fila/qr           {"numero": 7} -> {"numero", "url", "qr"} (mostrar o QR de novo)
  POST /api/fila/chamar       {"numero": 7}
  POST /api/fila/concluir     {"numero": 7} (o código do QR deixa de valer)
  POST /api/fila/aviso-visto  {"numero": 7} (o enfermeiro viu o aviso de piora do paciente)
  POST /api/fila/ficha        {"numero": 7} -> a ficha guardada, para reclassificar
  POST /api/fila/reclassificar {"numero": 7, "ficha": {...}, "extrator": "mock", "confirmar_reducao": false}
                              mesmo número, QR e chegada; cor mais baixa exige confirmar_reducao (senão 409)
  POST /api/voz?pergunta=Q09&parte=resposta   corpo = áudio gravado (audio/webm, audio/wav...)
                              -> {"transcricao", "valor", "entendido", "motivo"}
                              O áudio é transcrito na memória e descartado; nada é gravado.

  GET  /login, POST /login, POST /logout, GET /api/eu   login do enfermeiro

Tudo, menos /login e o CSS, exige sessão de enfermeiro (cookie HttpOnly, SameSite=Strict);
as contas ficam em `usuarios.db` (`python -m triagem.usuarios`). Sem sessão, a página vai
para /login e a API responde 401. Cada ação na fila registra quem a fez.

A página do paciente (aberta pelo QR) é outro servidor, em `paciente.py`.

Defesas simples, porque o conteúdo é de saúde (mesmo que simulado): só loopback,
checagem de Host e Origin (contra DNS rebinding e requisições de outros sites),
limite de tamanho, cabeçalhos restritivos e nenhum arquivo servido fora da lista.
"""

import json
import logging
import re
import sys
import threading
from http import HTTPStatus
from http.cookies import SimpleCookie
from urllib.parse import parse_qs
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from triagem.entrevista import FichaInvalida, processar_ficha
from triagem.fila import Fila
from triagem.extracao import NOME_PADRAO, NOMES_EXTRATORES, Extracao, Extrator, criar_extrator
from triagem.questionario import carregar_questionario
from triagem.regras import carregar_regras
from triagem.schema import Classificacao
from triagem.treino import BaseTreino
from triagem.usuarios import SESSAO_MAX_S, Usuarios
from triagem.voz import ErroVoz, Transcritor, TranscritorWhisper, interpretar_fala, whisper_instalado

log = logging.getLogger("triagem.interface")

PASTA_ESTATICA = Path(__file__).parent / "estatico"
PASTA_EXEMPLOS = Path(__file__).parents[2] / "exemplos"
LIMITE_CORPO = 1_000_000
LIMITE_AUDIO = 8_000_000   # cerca de 2 minutos de áudio comprimido do navegador
TIPOS = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
         ".css": "text/css; charset=utf-8"}
CABECALHOS_SEGURANCA = {
    "Cache-Control": "no-store",
    "X-Content-Type-Options": "nosniff",
    # same-origin (e não no-referrer): com no-referrer o navegador manda "Origin: null" nos
    # formulários (login/sair), e a checagem de origem os recusaria
    "Referrer-Policy": "same-origin",
    "Content-Security-Policy": ("default-src 'none'; script-src 'self'; style-src 'self'; "
                                "connect-src 'self'; img-src 'self' data:; base-uri 'none'; "
                                "form-action 'self'; frame-ancestors 'none'"),
}
COOKIE = "salus_sessao"
LIVRES = {"/login", "/estatico/estilo.css"}   # o resto exige sessão
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


def ouvir(transcritor: Transcritor | None, pergunta_id: str, nome_parte: str, audio: bytes) -> tuple[int, dict]:
    """Transcreve e interpreta a resposta falada para uma parte de uma pergunta."""
    if transcritor is None:
        return 503, {"erros": ["voz indisponível: instale com pip install -r requirements-voz.txt"]}
    pergunta = next((p for p in carregar_questionario()["perguntas"] if p["id"] == pergunta_id), None)
    parte = next((x for x in (pergunta or {}).get("partes", []) if x["nome"] == nome_parte), None)
    if parte is None:
        return 400, {"erros": [f"pergunta ou parte desconhecida: {pergunta_id!r} / {nome_parte!r}"]}
    try:
        texto = transcritor.transcrever(audio)
    except ErroVoz as e:
        return 422, {"erros": [str(e)]}
    finally:
        del audio  # o áudio não é guardado em lugar nenhum
    e = interpretar_fala(parte, texto)
    return 200, {"pergunta": pergunta_id, "parte": nome_parte, "transcricao": texto,
                 "valor": e.valor, "entendido": e.entendido, "motivo": e.motivo}


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


class ExtratorGravador(Extrator):
    """Repassa ao extrator real e guarda a leitura CRUA do relato (antes da mescla com as
    respostas diretas), que é o que interessa à base de treino."""

    def __init__(self, real: Extrator):
        self.real, self.nome, self.extracao = real, real.nome, None

    def extrair(self, relato: str) -> Extracao:
        self.extracao = self.real.extrair(relato)
        return self.extracao


def processar(ficha, nome_extrator: str) -> tuple[int, dict, dict | None]:
    """Roda o fluxo real. Devolve (status HTTP, corpo, leitura crua do relato ou None)."""
    if nome_extrator not in NOMES_EXTRATORES:
        return 400, {"erros": [f"extrator desconhecido: {nome_extrator!r}"]}, None
    gravador = ExtratorGravador(criar_extrator(nome_extrator))
    try:
        saida = processar_ficha(ficha, gravador)
    except FichaInvalida as e:
        return 422, {"erros": e.erros}, None
    crua = gravador.extracao.model_dump(mode="json") if gravador.extracao else None
    return 200, {"saida": saida.model_dump(mode="json")}, crua


def calcular(ficha, nome_extrator: str) -> tuple[int, dict]:
    """Roda o fluxo real. Devolve (status HTTP, corpo)."""
    status, corpo, _ = processar(ficha, nome_extrator)
    return status, corpo


def qr_svg(url: str) -> str | None:
    """QR code como data URI SVG (biblioteca `segno`, sem rede). None se ela não estiver instalada."""
    try:
        import segno
    except ImportError:
        return None
    return segno.make(url, error="m").svg_data_uri(scale=6, border=2)


def url_paciente(base: str | None, token: str) -> str | None:
    return f"{base}/p/{token}" if base else None


def guardar_para_treino(treino: BaseTreino | None, caso_id: str | None, ficha, saida: dict,
                        extrator: str, crua: dict | None) -> None:
    """Grava o caso anônimo na base de treino. Uma falha aqui nunca atrapalha a triagem."""
    if treino is None or not caso_id:
        return
    try:
        treino.registrar(caso_id, ficha, saida, extrator, crua)
    except Exception:
        log.exception("não foi possível gravar o caso na base de treino")


def colocar_na_fila(fila: Fila, base_url: str | None, ficha, nome_extrator: str,
                    por: str | None = None, treino: BaseTreino | None = None) -> tuple[int, dict]:
    """Processa a ficha aqui mesmo (a cor nunca vem do navegador) e põe o paciente na fila."""
    status, corpo, crua = processar(ficha, nome_extrator)
    if status != 200:
        return status, corpo
    entrada = fila.entrar(Classificacao.model_validate(corpo["saida"]["classificacao"]), ficha, nome_extrator,
                          por=por)
    guardar_para_treino(treino, entrada["caso_id"], ficha, corpo["saida"], nome_extrator, crua)
    url = url_paciente(base_url, entrada["token"])
    return 200, {"numero": entrada["numero"], "url": url, "qr": qr_svg(url) if url else None}


def reclassificar(fila: Fila, numero, ficha, nome_extrator: str, permitir_reducao: bool,
                  por: str | None = None, treino: BaseTreino | None = None) -> tuple[int, dict]:
    """Processa a ficha de novo, aqui no servidor, e troca a classificação de quem já está na fila."""
    if fila.ficha(numero) is None:
        return 404, {"erros": ["paciente não está na fila"]}
    status, corpo, crua = processar(ficha, nome_extrator)
    if status != 200:
        return status, corpo
    r = fila.reclassificar(numero, Classificacao.model_validate(corpo["saida"]["classificacao"]),
                           ficha, nome_extrator, permitir_reducao, por=por)
    if r["ok"]:
        guardar_para_treino(treino, r.pop("caso_id"), ficha, corpo["saida"], nome_extrator, crua)
        return 200, r
    if r["motivo"] == "precisa_confirmar":
        r.pop("caso_id", None)
        return 409, {**r, "erros": [f"a cor baixaria de {r['cor_antes']} para {r['cor_depois']}; confirme"]}
    return 404, {"erros": ["paciente não está na fila"]}


class Manipulador(BaseHTTPRequestHandler):
    server_version = "SalusIA"
    sys_version = ""

    def log_message(self, formato, *args):  # silencia o log por requisição; erros vão pelo logging
        log.debug(formato, *args)

    # --- respostas -----------------------------------------------------------------
    def _enviar(self, status: int, corpo: bytes, tipo: str, extras: dict | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(corpo)))
        for chave, valor in {**CABECALHOS_SEGURANCA, **(extras or {})}.items():
            self.send_header(chave, valor)
        self.end_headers()
        self.wfile.write(corpo)

    def _redirecionar(self, destino: str, cookie: str | None = None) -> None:
        extras = {"Location": destino}
        if cookie is not None:
            extras["Set-Cookie"] = cookie
        self._enviar(HTTPStatus.SEE_OTHER.value, b"", "text/plain; charset=utf-8", extras)

    # --- sessão ---------------------------------------------------------------------------
    def _codigo_sessao(self) -> str | None:
        try:
            biscoito = SimpleCookie(self.headers.get("Cookie", ""))
        except Exception:
            return None
        return biscoito[COOKIE].value if COOKIE in biscoito else None

    def _quem(self) -> dict | None:
        """Enfermeiro logado. Sem `usuarios` no servidor (só nos testes), o login fica desligado."""
        if self.server.usuarios is None:
            return {"login": None, "nome": None}
        return self.server.usuarios.sessao(self._codigo_sessao())

    @property
    def _por(self) -> str | None:
        quem = self._quem()
        return quem["login"] if quem else None

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
        caminho, _, consulta = self.path.partition("?")
        if caminho == "/login":
            if self.server.usuarios is None or self._quem():
                return self._redirecionar("/")
            return self._enviar(200, pagina_login("erro" in parse_qs(consulta)), "text/html; charset=utf-8")
        quem = self._quem()
        if quem is None and caminho not in LIVRES:
            if caminho in ("/", "/index.html"):
                return self._redirecionar("/login")
            return self._erro(HTTPStatus.UNAUTHORIZED, "faça login")
        if caminho == "/api/eu":
            return self._json(200, quem)
        if caminho in ("/", "/index.html"):
            return self._arquivo("index.html")
        if caminho.startswith("/estatico/"):
            return self._arquivo(caminho.removeprefix("/estatico/"))
        if caminho == "/api/questionario":
            return self._json(200, {**dados_para_interface(), "voz": self.server.transcritor is not None})
        if caminho == "/api/exemplos":
            return self._json(200, listar_exemplos())
        if caminho == "/api/fila":
            pacientes = [{k: v for k, v in p.items() if k != "token"} for p in self.server.fila.listar()]
            return self._json(200, {"pacientes": pacientes, "avisos": self.server.fila.avisos_pendentes(),
                                    "pagina_paciente": bool(self.server.url_paciente)})
        self._erro(HTTPStatus.NOT_FOUND, "não encontrado")

    def _arquivo(self, nome: str) -> None:
        arquivo = PASTA_ESTATICA / nome
        if not NOME_ARQUIVO.match(nome) or arquivo.suffix not in TIPOS or not arquivo.is_file():
            return self._erro(HTTPStatus.NOT_FOUND, "não encontrado")
        self._enviar(200, arquivo.read_bytes(), TIPOS[arquivo.suffix])

    def _ler_corpo(self, limite: int) -> bytes | None:
        """Lê o corpo antes de qualquer resposta (o Windows derruba a conexão se sobrar corpo
        não lido). Devolve None se o tamanho for ausente, nulo ou acima do limite."""
        try:
            tamanho = int(self.headers.get("Content-Length", ""))
        except ValueError:
            return None
        if not 0 < tamanho <= limite:
            return None
        return self.rfile.read(tamanho)

    def do_POST(self):
        caminho, _, consulta = self.path.partition("?")
        corpo_bruto = self._ler_corpo(LIMITE_AUDIO if caminho == "/api/voz" else LIMITE_CORPO)
        if not self._origem_confiavel(True):
            return self._erro(HTTPStatus.FORBIDDEN, "origem não permitida")
        if caminho == "/login":
            return self._login(corpo_bruto)
        if caminho == "/logout":
            if self.server.usuarios is not None:
                self.server.usuarios.sair(self._codigo_sessao())
            return self._redirecionar("/login", f"{COOKIE}=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0")
        if self._quem() is None:
            return self._erro(HTTPStatus.UNAUTHORIZED, "faça login")
        if caminho == "/api/voz":
            return self._voz(corpo_bruto, consulta)
        if caminho not in ROTAS_POST:
            return self._erro(HTTPStatus.NOT_FOUND, "não encontrado")
        if not self.headers.get("Content-Type", "").startswith("application/json"):
            return self._erro(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, "envie application/json")
        if corpo_bruto is None:
            self.close_connection = True
            return self._erro(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "corpo ausente, vazio ou grande demais")
        try:
            corpo = json.loads(corpo_bruto.decode("utf-8-sig"))
            if not isinstance(corpo, dict):
                raise TypeError
        except (ValueError, TypeError):
            return self._erro(HTTPStatus.BAD_REQUEST, "JSON inválido; esperado um objeto")
        try:
            status, resposta = getattr(self, ROTAS_POST[caminho])(corpo)
        except Exception:  # bug do sistema: não vaza detalhes ao navegador
            log.exception("erro interno em %s", caminho)
            return self._erro(HTTPStatus.INTERNAL_SERVER_ERROR, "erro interno; veja o terminal")
        self._json(status, resposta)

    def _login(self, corpo: bytes | None) -> None:
        if self.server.usuarios is None:
            return self._redirecionar("/")
        if corpo is None or not self.headers.get("Content-Type", "").startswith("application/x-www-form-urlencoded"):
            return self._redirecionar("/login?erro=1")
        campos = parse_qs(corpo.decode("utf-8", "replace"))
        login = campos.get("login", [""])[0]
        sessao = self.server.usuarios.entrar(login, campos.get("senha", [""])[0])
        if sessao is None:
            log.warning("login recusado: %s", login[:40])
            return self._redirecionar("/login?erro=1")
        log.info("login: %s", login.strip().lower())
        self._redirecionar("/", f"{COOKIE}={sessao}; HttpOnly; SameSite=Strict; Path=/; Max-Age={SESSAO_MAX_S}")

    def _voz(self, audio: bytes | None, consulta: str) -> None:
        from urllib.parse import parse_qs
        if not self.headers.get("Content-Type", "").split(";")[0].strip().startswith("audio/"):
            return self._erro(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, "envie o áudio com Content-Type audio/*")
        if audio is None:
            self.close_connection = True
            return self._erro(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "áudio ausente, vazio ou longo demais")
        params = parse_qs(consulta)
        try:
            status, resposta = ouvir(self.server.transcritor, params.get("pergunta", [""])[0],
                                     params.get("parte", ["resposta"])[0], audio)
        except Exception:
            log.exception("erro interno ao transcrever")
            return self._erro(HTTPStatus.INTERNAL_SERVER_ERROR, "erro interno; veja o terminal")
        self._json(status, resposta)

    # --- ações (cada uma devolve status HTTP e corpo) ------------------------------------
    @staticmethod
    def _ficha_e_extrator(corpo: dict):
        if "ficha" not in corpo:
            return None
        return corpo["ficha"], corpo.get("extrator", NOME_PADRAO)

    @staticmethod
    def _numero(corpo: dict) -> int | None:
        n = corpo.get("numero")
        return n if isinstance(n, int) and not isinstance(n, bool) else None

    def _triagem(self, corpo: dict) -> tuple[int, dict]:
        par = self._ficha_e_extrator(corpo)
        if par is None:
            return 400, {"erros": ['JSON inválido; esperado {"ficha": {...}}']}
        return calcular(*par)

    def _fila_entrar(self, corpo: dict) -> tuple[int, dict]:
        par = self._ficha_e_extrator(corpo)
        if par is None:
            return 400, {"erros": ['JSON inválido; esperado {"ficha": {...}}']}
        return colocar_na_fila(self.server.fila, self.server.url_paciente, *par, por=self._por,
                               treino=self.server.treino)

    def _fila_qr(self, corpo: dict) -> tuple[int, dict]:
        n = self._numero(corpo)
        p = next((x for x in self.server.fila.listar() if x["numero"] == n), None)
        if p is None:
            return 404, {"erros": ["paciente não está na fila"]}
        url = url_paciente(self.server.url_paciente, p["token"])
        return 200, {"numero": n, "url": url, "qr": qr_svg(url) if url else None}

    def _fila_chamar(self, corpo: dict) -> tuple[int, dict]:
        if self.server.fila.chamar(self._numero(corpo), por=self._por):
            return 200, {"ok": True}
        return 404, {"erros": ["paciente não está aguardando"]}

    def _fila_concluir(self, corpo: dict) -> tuple[int, dict]:
        if self.server.fila.concluir(self._numero(corpo), por=self._por):
            return 200, {"ok": True}
        return 404, {"erros": ["paciente não está na fila"]}

    def _fila_ficha(self, corpo: dict) -> tuple[int, dict]:
        f = self.server.fila.ficha(self._numero(corpo))
        if f is None:
            return 404, {"erros": ["paciente não está na fila"]}
        f.pop("caso_id", None)  # o vínculo com a base de treino não sai do servidor
        return 200, f

    def _fila_reclassificar(self, corpo: dict) -> tuple[int, dict]:
        par = self._ficha_e_extrator(corpo)
        if par is None:
            return 400, {"erros": ['JSON inválido; esperado {"numero": 7, "ficha": {...}}']}
        return reclassificar(self.server.fila, self._numero(corpo), *par,
                             permitir_reducao=corpo.get("confirmar_reducao") is True, por=self._por,
                             treino=self.server.treino)

    def _fila_aviso_visto(self, corpo: dict) -> tuple[int, dict]:
        if self.server.fila.marcar_aviso_visto(self._numero(corpo), por=self._por):
            return 200, {"ok": True}
        return 404, {"erros": ["não há aviso pendente para este paciente"]}


ROTAS_POST = {"/api/triagem": "_triagem", "/api/fila": "_fila_entrar", "/api/fila/qr": "_fila_qr",
              "/api/fila/chamar": "_fila_chamar", "/api/fila/concluir": "_fila_concluir",
              "/api/fila/aviso-visto": "_fila_aviso_visto", "/api/fila/ficha": "_fila_ficha",
              "/api/fila/reclassificar": "_fila_reclassificar"}


class ServidorLocal(ThreadingHTTPServer):
    # No Windows, SO_REUSEADDR deixaria outro processo abrir a MESMA porta ao mesmo tempo
    allow_reuse_address = False
    daemon_threads = True


def criar_servidor(porta: int = 0, fila: Fila | None = None, url_paciente: str | None = None,
                   transcritor: Transcritor | None = None, usuarios: Usuarios | None = None,
                   treino: BaseTreino | None = None) -> ServidorLocal:
    """Cria o servidor em loopback (porta 0 = qualquer porta livre).

    `url_paciente` é o endereço da página do paciente no Wi-Fi (ex.: http://192.168.0.10:8766);
    sem ele, a fila funciona, mas não gera QR. Sem `transcritor`, a voz fica desligada.
    Sem `usuarios`, o login fica DESLIGADO: isso só é usado nos testes; o comando sempre liga."""
    servidor = ServidorLocal(("127.0.0.1", porta), Manipulador)
    p = servidor.server_address[1]
    servidor.hosts_permitidos = {f"127.0.0.1:{p}", f"localhost:{p}"}
    servidor.fila = fila if fila is not None else Fila()
    servidor.url_paciente = url_paciente
    servidor.transcritor = transcritor
    servidor.usuarios = usuarios
    servidor.treino = treino
    return servidor


def pagina_login(erro: bool) -> bytes:
    aviso = ('<p class="alerta atencao" role="alert">Login ou senha incorretos (ou conta bloqueada '
             "por alguns minutos depois de várias tentativas).</p>") if erro else ""
    return f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Entrar · SalUS.ia</title>
<link rel="stylesheet" href="/estatico/estilo.css">
</head>
<body>
<main class="tela-login">
<form class="cartao" method="post" action="/login">
<div class="marca"><span class="logo" aria-hidden="true">+</span>
<div><h1>Sal<span>US</span>.ia</h1><p>Tela do enfermeiro</p></div></div>
{aviso}
<label class="campo">Login<input name="login" autocomplete="username" required autofocus></label>
<label class="campo">Senha<input name="senha" type="password" autocomplete="current-password" required></label>
<button class="pilula" type="submit">Entrar</button>
<p class="dica">Contas: <code>python -m triagem.usuarios criar &lt;login&gt; --nome "Nome"</code></p>
</form>
</main>
</body>
</html>
""".encode("utf-8")


def ip_na_rede() -> str:
    """IP desta máquina na rede local. Não envia nada: só consulta a tabela de rotas."""
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def _precarregar(transcritor: TranscritorWhisper) -> None:
    try:
        transcritor.carregar()
        log.info("voz pronta (%s)", transcritor.nome)
    except Exception as e:  # sem o modelo, a página avisa na hora de gravar
        log.error("não foi possível carregar o modelo de voz: %s", e)


def main(argv: list[str] | None = None) -> int:
    import argparse
    import webbrowser

    from triagem.cli import carregar_env, configurar_io

    parser = argparse.ArgumentParser(
        prog="python -m triagem.interface",
        description="Interface web local do Salus IA (dados simulados; só aceita conexões locais)")
    parser.add_argument("--porta", type=int, default=8765)
    parser.add_argument("--abrir", action="store_true", help="abre o navegador")
    parser.add_argument("--fila", default="fila.db", help="arquivo SQLite da fila (padrão: fila.db)")
    parser.add_argument("--porta-paciente", type=int, default=8766,
                        help="porta da página do paciente no Wi-Fi da unidade (padrão: 8766)")
    parser.add_argument("--ip", help="IP desta máquina no Wi-Fi, usado no QR (padrão: detectado)")
    parser.add_argument("--sem-paciente", action="store_true",
                        help="não abre a página do paciente na rede (a fila funciona sem QR)")
    parser.add_argument("--sem-voz", action="store_true", help="desliga a entrevista por voz")
    parser.add_argument("--usuarios", default="usuarios.db", help="contas de enfermeiro (padrão: usuarios.db)")
    parser.add_argument("--treino", default="treino.db",
                        help="base de treino do extrator, anonimizada (padrão: treino.db)")
    parser.add_argument("--sem-treino", action="store_true", help="não grava casos na base de treino")
    args = parser.parse_args(argv)
    configurar_io()
    carregar_env()

    from triagem.interface.paciente import criar_servidor_paciente

    usuarios = Usuarios(args.usuarios)
    if not usuarios.existe_algum_ativo():
        log.error("nenhuma conta de enfermeiro. Crie a primeira com:\n"
                  "  python -m triagem.usuarios criar <login> --nome \"Seu Nome\"")
        usuarios.fechar()
        return 2
    fila = Fila(args.fila)
    treino = None if args.sem_treino else BaseTreino(args.treino)
    paciente, base = None, None
    try:
        if not args.sem_paciente:
            paciente = criar_servidor_paciente(fila, "0.0.0.0", args.porta_paciente)
            base = f"http://{args.ip or ip_na_rede()}:{paciente.server_address[1]}"
        transcritor = None
        if not args.sem_voz and whisper_instalado():
            transcritor = TranscritorWhisper()
        elif not args.sem_voz:
            log.info("voz desligada: faster-whisper não instalado (pip install -r requirements-voz.txt)")
        servidor = criar_servidor(args.porta, fila, base, transcritor, usuarios, treino)
    except OSError as e:
        log.error("não foi possível abrir a porta: %s", e)
        if paciente:
            paciente.server_close()
        fila.fechar()
        usuarios.fechar()
        if treino:
            treino.fechar()
        return 2
    url = f"http://127.0.0.1:{servidor.server_address[1]}/"
    log.info("interface do enfermeiro em %s (só nesta máquina; Ctrl+C para encerrar)", url)
    if paciente:
        threading.Thread(target=paciente.serve_forever, daemon=True).start()
        log.info("página do paciente no Wi-Fi em %s/p/<código> (o QR aponta para cá)", base)
    if transcritor is not None:
        # carrega o modelo em segundo plano para a primeira gravação não demorar
        threading.Thread(target=_precarregar, args=(transcritor,), daemon=True).start()
    if treino:
        log.info("base de treino ligada em %s (anonimizada; trate como dado sensível; --sem-treino desliga)",
                 args.treino)
    if args.abrir:
        webbrowser.open(url)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        log.info("encerrando")
    finally:
        servidor.server_close()
        if paciente:
            paciente.shutdown()
            paciente.server_close()
        fila.fechar()
        usuarios.fechar()
        if treino:
            treino.fechar()
    return 0


if __name__ == "__main__":
    sys.exit(main())
