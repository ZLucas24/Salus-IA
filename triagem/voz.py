"""Voz do enfermeiro: transcrição local e interpretação da fala em resposta.

Duas etapas separadas, de propósito:

1. **Transcrição** (`Transcritor`): áudio -> texto. A implementação real usa o
   faster-whisper, rodando NESTA máquina (sem internet depois de baixar o modelo).
   O áudio só existe na memória durante a requisição; nunca é gravado em disco.
2. **Interpretação** (`interpretar_fala`): texto -> valor de uma parte da pergunta.
   É código determinístico, sem IA. Regras de segurança:
   - "não sei", "acho que...", "talvez", "mais ou menos" viram `nao_sabe`, nunca "não";
   - frase com "sim" e "não" ao mesmo tempo não é entendida (o enfermeiro decide);
   - o que não for entendido volta como `entendido=False`, e nada é preenchido.
   O valor sempre passa pela confirmação do enfermeiro antes de entrar na ficha.
"""

import importlib.util
import io
import logging
import os
import re
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from triagem.texto import sem_acentos

log = logging.getLogger("triagem.voz")

MODELO_PADRAO = "small"        # relato livre: precisa de mais acerto
MODELO_RAPIDO_PADRAO = "base"  # respostas curtas: ~3x mais rápido em CPU
MAX_TOKENS_CURTA = 24


class ErroVoz(RuntimeError):
    pass


# --- transcrição ----------------------------------------------------------------------------

class Transcritor(ABC):
    nome: str

    @abstractmethod
    def transcrever(self, audio: bytes, curta: bool = False, dica: str | None = None,
                    preciso: bool = False) -> str:
        """Devolve o texto falado. Levanta ErroVoz se não conseguir.

        `curta`: a resposta esperada é curta (sim/não, número, opção) e pode ir pelo modelo
        rápido. `dica`: vocabulário esperado. `preciso`: força o modelo maior (segunda tentativa)."""

    tem_reserva = False  # True se há um modelo maior para tentar de novo quando o rápido não entende


def whisper_instalado() -> bool:
    return importlib.util.find_spec("faster_whisper") is not None


class TranscritorWhisper(Transcritor):
    """faster-whisper local, em CPU (int8). Dois modelos, carregados uma vez e reaproveitados:
    o rápido para respostas curtas e o maior para o relato (e como reserva do rápido)."""

    # Vocabulário do domínio: ajuda o modelo a escrever as palavras certas.
    DICA = ("Triagem em pronto-socorro. Dor no peito, falta de ar, febre, vômito, diarreia, desmaio, "
            "alergia, dipirona, insulina, anticoagulante, pressão alta, diabetes.")

    def __init__(self, modelo: str | None = None, rapido: str | None = None):
        self.modelo_nome = modelo or os.environ.get("TRIAGEM_WHISPER", MODELO_PADRAO)
        self.rapido_nome = rapido or os.environ.get("TRIAGEM_WHISPER_RAPIDO", MODELO_RAPIDO_PADRAO)
        self.tem_reserva = self.rapido_nome != self.modelo_nome
        self.nome = (f"whisper:{self.rapido_nome}+{self.modelo_nome}" if self.tem_reserva
                     else f"whisper:{self.modelo_nome}")
        self._modelos: dict[str, Any] = {}
        self._trava = threading.Lock()

    def carregar(self, nome: str | None = None):
        """Carrega (uma vez) o modelo pedido; sem nome, carrega os dois."""
        if nome is None:
            self._rapido()
            return self.carregar(self.modelo_nome)
        with self._trava:
            if nome not in self._modelos:
                try:
                    from faster_whisper import WhisperModel
                except ImportError as e:
                    raise ErroVoz("faster-whisper não está instalado (pip install -r requirements-voz.txt)") from e
                log.info("carregando o modelo de voz %s", nome)
                try:  # usa o modelo já baixado, sem tocar na rede
                    modelo = WhisperModel(nome, device="cpu", compute_type="int8", local_files_only=True)
                except Exception:
                    log.info("modelo %s ainda não baixado; baixando (só na primeira vez)", nome)
                    try:
                        modelo = WhisperModel(nome, device="cpu", compute_type="int8")
                    except Exception as e:
                        raise ErroVoz(f"não foi possível carregar o modelo de voz '{nome}' "
                                      f"(sem internet para baixar? {type(e).__name__})") from e
                self._modelos[nome] = modelo
            return self._modelos[nome]

    def _rapido(self):
        """Modelo das respostas curtas. Se ele não carregar (ex.: máquina sem internet para o
        primeiro download), as respostas curtas passam a usar o modelo principal: mais lento,
        mas a voz continua funcionando."""
        if self.tem_reserva:
            try:
                return self.carregar(self.rapido_nome)
            except ErroVoz as e:
                log.warning("%s; as respostas curtas vão usar o modelo %s", e, self.modelo_nome)
                self.rapido_nome, self.tem_reserva = self.modelo_nome, False
                self.nome = f"whisper:{self.modelo_nome}"
        return self.carregar(self.modelo_nome)

    def transcrever(self, audio: bytes, curta: bool = False, dica: str | None = None,
                    preciso: bool = False) -> str:
        modelo = self._rapido() if curta and not preciso else self.carregar(self.modelo_nome)
        amostras = decodificar(audio)
        try:
            # busca gulosa, sem marcas de tempo e sem VAD: a gravação já chega recortada pela página
            segmentos, _ = modelo.transcribe(
                amostras, language="pt", beam_size=1 if curta else 3, temperature=0.0,
                without_timestamps=True, condition_on_previous_text=False, vad_filter=not curta,
                # resposta curta tem poucas palavras: o limite impede o modelo de "inventar" um
                # texto longo (e demorar segundos) quando o áudio é ruim
                max_new_tokens=MAX_TOKENS_CURTA if curta else None,
                initial_prompt=dica or self.DICA)
            return " ".join(s.text.strip() for s in segmentos).strip()
        except Exception as e:
            raise ErroVoz(f"não foi possível transcrever o áudio ({type(e).__name__})") from e


def dica_da_parte(parte: dict) -> str | None:
    """Vocabulário esperado na resposta, para o modelo escrever a palavra certa ("10", não "des")."""
    forma = parte["forma"]
    if forma == "sim_nao":
        return "Resposta: sim. Não. Não sabe. Recusou."
    if forma in ("escala", "numero"):
        return "Resposta em número: 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10."
    if forma == "numero_unidade":
        return "Resposta: 30 minutos. 2 horas. 3 dias. 1 semana."
    if forma in ("opcao", "multiplas"):
        return "Resposta: " + ", ".join(o.replace("_", " ") for o in parte["opcoes"]) + ". Nenhuma. Não sabe."
    return None


def forma_curta(parte: dict) -> bool:
    return parte["forma"] != "texto"


def decodificar(audio: bytes):
    """Áudio (webm/opus do navegador, wav, ogg...) -> amostras float32 mono a 16 kHz, na memória.

    Feito aqui com o PyAV, em vez da função do faster-whisper, para não depender de uma
    versão exata do PyAV."""
    import av
    import numpy as np
    try:
        partes = []
        with av.open(io.BytesIO(audio), mode="r") as entrada:
            reamostrador = av.AudioResampler(format="s16", layout="mono", rate=16000)
            for quadro in entrada.decode(audio=0):
                for q in reamostrador.resample(quadro):
                    partes.append(q.to_ndarray().reshape(-1))
            for q in reamostrador.resample(None):
                partes.append(q.to_ndarray().reshape(-1))
    except Exception as e:  # áudio corrompido, formato não suportado...
        raise ErroVoz(f"áudio inválido ou em formato não suportado ({type(e).__name__})") from e
    if not partes:
        raise ErroVoz("o áudio está vazio")
    return np.concatenate(partes).astype(np.float32) / 32768.0


# --- interpretação ----------------------------------------------------------------------------

@dataclass
class Entendido:
    valor: Any = None
    entendido: bool = False
    motivo: str = ""


NAO_SE_APLICA = ["nao se aplica"]
RECUSOU = ["nao quer responder", "nao quis responder", "prefere nao", "prefiro nao", "recusou",
           "se recusa", "recusa"]
NAO_SABE = ["nao sabe", "nao sei", "sei la", "nao lembra", "nao lembro", "nao tem certeza",
            "nao tenho certeza", "talvez", "acho", "acha", "pode ser", "mais ou menos", "duvida",
            "incerto", "nao sabe dizer", "nao soube"]

NEGACAO = {"nao", "nunca", "negativo", "nenhum", "nenhuma", "nada", "jamais", "sem", "nem"}
# "sin", "cim": como o modelo às vezes escreve um "sim" curto. Para o "não" NÃO há variantes
# aproximadas, de propósito: um "não" só entra quando foi ouvido com clareza.
SIM = {"sim", "sin", "cim", "positivo", "afirmativo", "isso", "claro", "uhum", "aham", "exato", "correto",
       "certeza", "verdade"}
AFIRMA = {"tenho", "tem", "teve", "tive", "estou", "esta", "sinto", "sente", "sentiu", "senti",
          "consigo", "consegue", "usa", "uso", "toma", "tomo", "tomou", "tomei", "fez", "fiz",
          "fica", "ficou", "desmaiou", "desmaiei", "vomitou", "vomitando", "esta"}

UNIDADES = {"zero": 0, "um": 1, "uma": 1, "dois": 2, "duas": 2, "tres": 3, "quatro": 4,
            "cinco": 5, "seis": 6, "sete": 7, "oito": 8, "nove": 9, "dez": 10, "onze": 11,
            "doze": 12, "treze": 13, "quatorze": 14, "catorze": 14, "quinze": 15,
            "dezesseis": 16, "dezessete": 17, "dezoito": 18, "dezenove": 19}
# Como o modelo costuma escrever um número curto dito sozinho ("Des." para "dez").
# Só vale onde a pergunta espera um número; o enfermeiro confirma antes de entrar na ficha.
NUMEROS_APROXIMADOS = {"zeru": 0, "cero": 0, "hum": 1, "doiz": 2, "doi": 2, "treis": 3, "trez": 3,
                       "tre": 3, "quatru": 4, "cuatro": 4, "sinco": 5, "cinto": 5, "seiz": 6, "ceis": 6,
                       "seti": 7, "sette": 7, "oitu": 8, "oto": 8, "novi": 9, "des": 10, "deis": 10,
                       "dex": 10, "deiz": 10, "dess": 10}
DEZENAS = {"vinte": 20, "trinta": 30, "quarenta": 40, "cinquenta": 50, "sessenta": 60,
           "setenta": 70, "oitenta": 80, "noventa": 90}
TEMPO = {"minuto": "minutos", "minutos": "minutos", "min": "minutos", "hora": "horas",
         "horas": "horas", "dia": "dias", "dias": "dias", "semana": "semanas",
         "semanas": "semanas", "mes": "meses", "meses": "meses", "ano": "anos", "anos": "anos"}

# Como cada opção do questionário pode ser dita. Sem entrada aqui, vale o próprio nome
# da opção (com espaços no lugar de "_").
SINONIMOS = {
    "de_repente": ["de repente", "subito", "do nada", "de uma vez", "derrepente"],
    "aos_poucos": ["aos poucos", "devagar", "gradual", "gradualmente", "foi aumentando"],
    "igual": ["igual", "mesma coisa", "do mesmo jeito", "nao mudou", "estavel"],
    "melhorando": ["melhorando", "melhorou", "melhor"],
    "piorando": ["piorando", "piorou", "pior"],
    "queimacao": ["queimacao", "queimando", "queima", "ardencia", "ardendo", "arde"],
    "aperto": ["aperto", "apertando", "aperta", "pressao no peito", "peso no peito", "esmagando"],
    "pontada": ["pontada", "pontadas", "fisgada", "agulhada", "facada"],
    "colica": ["colica", "colicas"],
    "outro": ["outro", "outra", "outro tipo", "outro lugar"],
    "outra": ["outra", "outro", "outra doenca"],
    "parte_superior": ["parte de cima", "parte superior", "em cima", "boca do estomago", "estomago"],
    "parte_inferior_direita": ["embaixo a direita", "inferior direita", "lado direito"],
    "parte_inferior_esquerda": ["embaixo a esquerda", "inferior esquerda", "lado esquerdo"],
    "ao_redor_do_umbigo": ["umbigo"],
    "toda_a_barriga": ["toda a barriga", "barriga toda", "barriga inteira", "toda"],
    "medicamento": ["medicamento", "medicamentos", "remedio", "remedios"],
    "alimento": ["alimento", "alimentos", "comida", "comidas"],
    "contraste": ["contraste"],
    "antitermico": ["antitermico", "para febre", "pra febre"],
    "analgesico": ["analgesico", "para dor", "pra dor"],
    "diabetes": ["diabetes", "diabetico", "diabetica", "acucar no sangue"],
    "hipertensao": ["hipertensao", "hipertenso", "hipertensa", "pressao alta"],
    "cardiopatia": ["cardiopatia", "coracao", "cardiaco", "cardiaca"],
    "pneumopatia": ["pneumopatia", "pulmao", "asma", "bronquite", "enfisema", "dpoc"],
    "renopatia": ["renopatia", "rim", "rins", "renal"],
    "cirurgia": ["cirurgia", "cirurgias", "operou", "operado", "operada", "operacao"],
    "internacao": ["internacao", "internado", "internada", "internou"],
    "transfusao": ["transfusao", "transfusao de sangue", "recebeu sangue"],
}


def normalizar(texto: str) -> str:
    t = sem_acentos(texto).lower()
    t = re.sub(r"(\d)[.,](\d)", r"\1#\2", t)          # preserva a vírgula decimal
    t = re.sub(r"[^a-z0-9#]+", " ", t).replace("#", ".")
    return f" {t.strip()} "


def _tem(norm: str, frases) -> bool:
    return any(f" {f} " in norm for f in frases)


def _tokens(norm: str) -> list[str]:
    return norm.split()


def _numeros(tokens: list[str]) -> list[float]:
    nums, i = [], 0
    while i < len(tokens):
        t = tokens[i]
        if re.fullmatch(r"\d+(\.\d+)?", t):
            nums.append(float(t))
            i += 1
            continue
        if t in DEZENAS or t in UNIDADES:
            v = DEZENAS.get(t, UNIDADES.get(t))
            i += 1
            if t in DEZENAS and i + 1 < len(tokens) and tokens[i] == "e" and UNIDADES.get(tokens[i + 1], 99) < 10:
                v += UNIDADES[tokens[i + 1]]
                i += 2
            if i + 1 < len(tokens) and tokens[i] == "e" and tokens[i + 1] in ("meio", "meia"):
                v += 0.5
                i += 2
            nums.append(float(v))
            continue
        if t in ("meia", "meio"):
            nums.append(0.5)
        elif t in NUMEROS_APROXIMADOS:
            nums.append(float(NUMEROS_APROXIMADOS[t]))
        i += 1
    return nums


def _marcador(norm: str) -> str | None:
    if _tem(norm, NAO_SE_APLICA):
        return "nao_se_aplica"
    if _tem(norm, RECUSOU):
        return "recusou"
    if _tem(norm, NAO_SABE):
        return "nao_sabe"
    return None


def _opcoes_citadas(norm: str, opcoes: list[str]) -> tuple[list[str], str]:
    """Opções citadas (na ordem do questionário) e o texto que sobrou sem elas."""
    citadas, resto = [], norm
    for o in opcoes:
        frases = sorted(SINONIMOS.get(o, [o.replace("_", " ")]), key=len, reverse=True)
        achou = False
        for f in frases:
            if f" {f} " in resto:
                resto = resto.replace(f" {f} ", " ")
                achou = True
        if achou:
            citadas.append(o)
    return citadas, resto


def interpretar_fala(parte: dict, texto: str) -> Entendido:
    """Transforma o que foi dito no valor de UMA parte de uma pergunta do questionário."""
    texto = (texto or "").strip()
    if not texto:
        return Entendido(motivo="nada foi dito")
    forma = parte["forma"]
    if forma == "texto":
        return Entendido(valor=texto, entendido=True)

    norm = normalizar(texto)
    marcador = _marcador(norm)
    if marcador:
        return Entendido(valor=marcador, entendido=True)
    tokens = set(_tokens(norm))

    if forma == "sim_nao":
        nega, sim = bool(tokens & NEGACAO), bool(tokens & SIM)
        if nega and sim:
            return Entendido(motivo="a frase tem 'sim' e 'não' ao mesmo tempo")
        if nega:
            return Entendido(valor=False, entendido=True)
        # verbo afirmativo só conta abrindo a frase ("Tem falta de ar", "Ela tem"), para
        # "o paciente está aqui" não virar "sim"
        toks = _tokens(norm)
        if not toks:  # só pontuação ou ruído ("...", "?")
            return Entendido(motivo="não reconheci sim nem não")
        abre = toks[1] if len(toks) > 1 and toks[0] in ("ele", "ela") else toks[0]
        if sim or abre in AFIRMA or toks == ["e"]:  # "É."
            return Entendido(valor=True, entendido=True)
        return Entendido(motivo="não reconheci sim nem não")

    if forma in ("escala", "numero"):
        nums = _numeros(_tokens(norm))
        if forma == "escala":
            nums = [n for n in nums if n == int(n) and 0 <= n <= 10]
        if len(set(nums)) != 1:
            return Entendido(motivo="não reconheci um único número" if nums else "não reconheci número")
        n = nums[0]
        minimo, maximo = parte.get("minimo"), parte.get("maximo")
        if (minimo is not None and n < minimo) or (maximo is not None and n > maximo):
            return Entendido(motivo=f"{n:g} está fora do intervalo esperado")
        return Entendido(valor=int(n) if forma == "escala" or n == int(n) else n, entendido=True)

    if forma == "opcao":
        citadas, resto = _opcoes_citadas(norm, parte["opcoes"])
        if len(citadas) != 1:
            return Entendido(motivo="mais de uma opção citada" if citadas else "nenhuma opção reconhecida")
        if set(_tokens(resto)) & NEGACAO:
            return Entendido(motivo="a frase tem negação; confirme na ficha")
        return Entendido(valor=citadas[0], entendido=True)

    if forma == "multiplas":
        citadas, resto = _opcoes_citadas(norm, parte["opcoes"])
        nega = bool(set(_tokens(resto)) & NEGACAO)
        if citadas and nega:
            return Entendido(motivo="a frase cita opções e tem negação; confirme na ficha")
        if citadas:
            return Entendido(valor=citadas, entendido=True)
        if nega:
            return Entendido(valor=[], entendido=True)
        return Entendido(motivo="nenhuma opção reconhecida")

    if forma == "numero_unidade":
        meio = re.search(r" (minutos?|horas?|dias?|semanas?|mes|meses|anos?) e mei[ao] ", norm)
        if meio:
            norm = norm.replace(meio.group(0), f" {meio.group(1)} ")
        toks = _tokens(norm)
        if toks == ["ontem"]:
            return Entendido(valor={"valor": 1, "unidade": "dias"}, entendido=True) \
                if "dias" in parte["unidades"] else Entendido(motivo="unidade não aceita aqui")
        unidades = {TEMPO[t] for t in toks if t in TEMPO}
        nums = _numeros([t for t in toks if t not in TEMPO])
        if not nums and unidades and any(t in ("um", "uma") for t in toks):
            nums = [1.0]
        if len(unidades) != 1 or len(nums) != 1:
            return Entendido(motivo="diga um número e uma unidade (ex.: 2 horas)")
        valor = nums[0] + (0.5 if meio else 0)
        unidade = unidades.pop()
        if unidade not in parte["unidades"]:
            return Entendido(motivo=f"'{unidade}' não é aceito aqui")
        return Entendido(valor={"valor": int(valor) if valor == int(valor) else valor, "unidade": unidade},
                         entendido=True)

    return Entendido(motivo=f"forma de resposta não suportada por voz: {forma}")
