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
  POST /api/voz?pergunta=Q09&parte=resposta   corpo = áudio gravado (audio/webm, audio/wav...)
                              -> {"transcricao", "valor", "entendido", "motivo"}
                              O áudio é transcrito na memória e descartado; nada é gravado.

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
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from triagem.entrevista import FichaInvalida, processar_ficha
from triagem.fila import Fila
from triagem.extracao import NOME_PADRAO, NOMES_EXTRATORES, criar_extrator
from triagem.questionario import carregar_questionario
from triagem.regras import carregar_regras
from triagem.schema import Classificacao
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


def calcular(ficha, nome_extrator: str) -> tuple[int, dict]:
    """Roda o fluxo real. Devolve (status HTTP, corpo)."""
    if nome_extrator not in NOMES_EXTRATORES:
        return 400, {"erros": [f"extrator desconhecido: {nome_extrator!r}"]}
    try:
        saida = processar_ficha(ficha, criar_extrator(nome_extrator))
    except FichaInvalida as e:
        return 422, {"erros": e.erros}
    return 200, {"saida": saida.model_dump(mode="json")}


def qr_svg(url: str) -> str | None:
    """QR code como data URI SVG (biblioteca `segno`, sem rede). None se ela não estiver instalada."""
    try:
        import segno
    except ImportError:
        return None
    return segno.make(url, error="m").svg_data_uri(scale=6, border=2)


def url_paciente(base: str | None, token: str) -> str | None:
    return f"{base}/p/{token}" if base else None


def colocar_na_fila(fila: Fila, base_url: str | None, ficha, nome_extrator: str) -> tuple[int, dict]:
    """Processa a ficha aqui mesmo (a cor nunca vem do navegador) e põe o paciente na fila."""
    status, corpo = calcular(ficha, nome_extrator)
    if status != 200:
        return status, corpo
    entrada = fila.entrar(Classificacao.model_validate(corpo["saida"]["classificacao"]))
    url = url_paciente(base_url, entrada["token"])
    return 200, {"numero": entrada["numero"], "url": url, "qr": qr_svg(url) if url else None}


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
        return colocar_na_fila(self.server.fila, self.server.url_paciente, *par)

    def _fila_qr(self, corpo: dict) -> tuple[int, dict]:
        n = self._numero(corpo)
        p = next((x for x in self.server.fila.listar() if x["numero"] == n), None)
        if p is None:
            return 404, {"erros": ["paciente não está na fila"]}
        url = url_paciente(self.server.url_paciente, p["token"])
        return 200, {"numero": n, "url": url, "qr": qr_svg(url) if url else None}

    def _fila_chamar(self, corpo: dict) -> tuple[int, dict]:
        if self.server.fila.chamar(self._numero(corpo)):
            return 200, {"ok": True}
        return 404, {"erros": ["paciente não está aguardando"]}

    def _fila_concluir(self, corpo: dict) -> tuple[int, dict]:
        if self.server.fila.concluir(self._numero(corpo)):
            return 200, {"ok": True}
        return 404, {"erros": ["paciente não está na fila"]}

    def _fila_aviso_visto(self, corpo: dict) -> tuple[int, dict]:
        if self.server.fila.marcar_aviso_visto(self._numero(corpo)):
            return 200, {"ok": True}
        return 404, {"erros": ["não há aviso pendente para este paciente"]}


ROTAS_POST = {"/api/triagem": "_triagem", "/api/fila": "_fila_entrar", "/api/fila/qr": "_fila_qr",
              "/api/fila/chamar": "_fila_chamar", "/api/fila/concluir": "_fila_concluir",
              "/api/fila/aviso-visto": "_fila_aviso_visto"}


class ServidorLocal(ThreadingHTTPServer):
    # No Windows, SO_REUSEADDR deixaria outro processo abrir a MESMA porta ao mesmo tempo
    allow_reuse_address = False
    daemon_threads = True


def criar_servidor(porta: int = 0, fila: Fila | None = None, url_paciente: str | None = None,
                   transcritor: Transcritor | None = None) -> ServidorLocal:
    """Cria o servidor em loopback (porta 0 = qualquer porta livre).

    `url_paciente` é o endereço da página do paciente no Wi-Fi (ex.: http://192.168.0.10:8766);
    sem ele, a fila funciona, mas não gera QR. Sem `transcritor`, a voz fica desligada."""
    servidor = ServidorLocal(("127.0.0.1", porta), Manipulador)
    p = servidor.server_address[1]
    servidor.hosts_permitidos = {f"127.0.0.1:{p}", f"localhost:{p}"}
    servidor.fila = fila if fila is not None else Fila()
    servidor.url_paciente = url_paciente
    servidor.transcritor = transcritor
    return servidor


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
    args = parser.parse_args(argv)
    configurar_io()
    carregar_env()

    from triagem.interface.paciente import criar_servidor_paciente

    fila = Fila(args.fila)
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
        servidor = criar_servidor(args.porta, fila, base, transcritor)
    except OSError as e:
        log.error("não foi possível abrir a porta: %s", e)
        if paciente:
            paciente.server_close()
        fila.fechar()
        return 2
    url = f"http://127.0.0.1:{servidor.server_address[1]}/"
    log.info("interface do enfermeiro em %s (só nesta máquina; Ctrl+C para encerrar)", url)
    if paciente:
        threading.Thread(target=paciente.serve_forever, daemon=True).start()
        log.info("página do paciente no Wi-Fi em %s/p/<código> (o QR aponta para cá)", base)
    if transcritor is not None:
        # carrega o modelo em segundo plano para a primeira gravação não demorar
        threading.Thread(target=_precarregar, args=(transcritor,), daemon=True).start()
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
    return 0


if __name__ == "__main__":
    sys.exit(main())
