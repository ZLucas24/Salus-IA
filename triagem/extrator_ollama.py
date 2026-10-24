"""Extrator que usa um modelo local via Ollama.

O modelo só entende o texto e devolve dados estruturados; nunca decide
gravidade. A saída é validada sinal a sinal: um item inválido é descartado
(com aviso), sem derrubar a extração inteira. Garantias do código, que não
dependem do modelo:
  - "negado" só vale se o relato tem alguma palavra de negação;
  - se o mesmo sinal vier presente e negado, vence o presente;
  - alergia só entra como "presente"; negar alergia é função da pergunta direta;
  - todo sinal precisa de um trecho que exista no relato; sem prova, é descartado;
  - valores fora da faixa são descartados (o sinal fica, sem valor).
"""

import json
import logging
import os
from urllib.parse import urlparse

from pydantic import BaseModel, ValidationError

from triagem.extracao import ESTADOS_EXTRAIVEIS, Extracao, Extrator
from triagem.schema import Alergias, Duracao, Sinal
from triagem.sinais import SINAIS_MEDIDOS, NomeSinal, Origem, Queixa, Status
from triagem.texto import normalizar_itens, sem_acentos, tem_negacao

log = logging.getLogger("triagem.ollama")

MODELO_PADRAO = "llama3.1:8b"
LIMITE_TOKENS = 700   # evita geração sem fim (JSON truncado vira erro tratado)
TIMEOUT_S = 120      # a primeira chamada carrega o modelo na memória
TENTATIVAS = 2        # uma nova tentativa se a resposta vier em formato inválido
HOSTS_LOCAIS = {"", "localhost", "127.0.0.1", "::1", "0.0.0.0"}

# sinais que o relato pode citar, com uma dica curta para o modelo
SINAIS_DO_RELATO = {
    "inicio_subito": "começou de repente",
    "piora_progressiva": "está piorando",
    "dor_em_aperto": "dor em aperto / peso",
    "dor": "qualquer dor citada, em qualquer parte do corpo (valor = nota de 0 a 10, só se o paciente disser); 'sem dor' = negado",
    "irradiacao": "a dor se espalha (itens = para onde)",
    "alteracao_consciencia": "desmaio, confusão, sensação de apagar",
    "dispneia": "falta de ar",
    "uso_anticoagulante": "usa remédio para afinar o sangue",
    "uso_insulina": "usa insulina",
    "antitermico_recente": "tomou remédio para febre hoje",
    "doenca_cronica": "doença diagnosticada (itens: diabetes, hipertensao, cardiopatia, pneumopatia, renopatia, outra)",
    "gravidez_possivel": "grávida ou possibilidade de gravidez",
    "amamentando": "amamentando",
    "suor_frio_enjoo_tontura": "suor frio, enjoo ou tontura junto com a dor",
    "dor_abdominal": "dor na barriga (itens = local); nesse caso marque também 'dor'",
    "vomito": "vômito (valor = número de episódios, se dito)",
    "sangue_vomito_fezes": "sangue no vômito ou nas fezes",
    "diarreia": "diarreia",
    "abdome_rigido_distendido": "barriga dura ou inchada",
    "alteracao_urinaria": "alteração ao urinar",
    "febre_referida": "febre (valor = maior temperatura dita, em °C)",
    "calafrios": "calafrios",
    "chiado": "chiado no peito",
    "tosse_com_sangue": "tosse com sangue",
    "contato_ou_viagem": "contato com doente ou viagem recente",
}
FAIXAS_VALOR = {"dor": (0, 10), "febre_referida": (30, 45), "vomito": (1, 100)}

INSTRUCOES = f"""Você extrai dados de um relato curto de paciente, em português.
Responda SOMENTE com JSON no formato pedido. Regras:
- Não avalie gravidade, não dê diagnóstico nem conselho.
- queixa_principal: a queixa em poucas palavras, em minúsculas.
- queixas: categorias entre {", ".join(q.value for q in Queixa)}.
- duracao: só se o relato disser há quanto tempo (unidade: minutos, horas, dias, semanas, meses ou anos); senão null. "ontem" = 1 dia.
- sinais: inclua SOMENTE sinais que o relato diz de forma explícita. status "presente", "negado" (só se o relato nega de forma explícita: "sem X", "não tenho X") ou "incerto" (se estiver em dúvida). NUNCA invente nem deduza sinais que o paciente não disse.
  "trecho" é OBRIGATÓRIO: a cópia literal do pedaço do relato que comprova o sinal. Se não houver trecho, não inclua o sinal.
  Sinais permitidos (nome: significado):
""" + "\n".join(f"  - {n}: {d}" for n, d in SINAIS_DO_RELATO.items()) + """
- alergias: só se o relato afirmar alergia a algo; liste os nomes em "itens". Se não falar de alergia, ou se negar, use null.
- "sem X", "não tenho X" e "nunca teve X" significam "negado", NUNCA "presente"."""

# Exemplos (relato -> JSON esperado). Não podem aparecer no gabarito de avaliação.
EXEMPLOS = [
    ("tosse seca há 3 dias, sem febre",
     {"queixa_principal": "tosse seca", "queixas": ["respiratorio_febre"],
      "duracao": {"valor": 3, "unidade": "dias"},
      "sinais": [{"nome": "febre_referida", "status": "negado", "trecho": "sem febre"}],
      "alergias": None}),
    ("aperto forte no peito desde ontem e falta de ar, alérgico a penicilina",
     {"queixa_principal": "aperto no peito e falta de ar", "queixas": ["dor_toracica"],
      "duracao": {"valor": 1, "unidade": "dias"},
      "sinais": [{"nome": "dor_em_aperto", "status": "presente", "trecho": "aperto forte no peito"},
                 {"nome": "dispneia", "status": "presente", "trecho": "falta de ar"}],
      "alergias": {"itens": ["penicilina"]}}),
    ("barriga doendo há 5 horas, não tenho alergia a remédio, sem vômito",
     {"queixa_principal": "dor na barriga", "queixas": ["dor_abdominal"],
      "duracao": {"valor": 5, "unidade": "horas"},
      "sinais": [{"nome": "dor_abdominal", "status": "presente", "trecho": "barriga doendo"},
                 {"nome": "vomito", "status": "negado", "trecho": "sem vômito"}],
      "alergias": None}),
    ("sou diabético e estou grávida, sem falta de ar, dor de cabeça desde segunda",
     {"queixa_principal": "dor de cabeça", "queixas": ["outra"],
      "duracao": None,
      "sinais": [{"nome": "doenca_cronica", "status": "presente", "itens": ["diabetes"], "trecho": "sou diabético"},
                 {"nome": "gravidez_possivel", "status": "presente", "trecho": "estou grávida"},
                 {"nome": "dispneia", "status": "negado", "trecho": "sem falta de ar"},
                 {"nome": "dor", "status": "presente", "trecho": "dor de cabeça"}],
      "alergias": None}),
]


class ErroExtracao(RuntimeError):
    """O modelo não respondeu ou respondeu algo fora do formato."""


class ErroFormato(ErroExtracao):
    """A resposta chegou, mas fora do formato: vale uma nova tentativa."""


class _Item(BaseModel):
    nome: str
    status: str
    valor: float | None = None
    itens: list[str] = []
    trecho: str | None = None


class _Resposta(BaseModel):
    queixa_principal: str | None = None
    queixas: list[str] = []
    duracao: Duracao | None = None
    sinais: list[_Item] = []
    alergias: dict | None = None


def _aviso_host(host: str | None) -> None:
    alvo = urlparse(host if host and "//" in host else f"//{host or ''}")
    if (alvo.hostname or "") not in HOSTS_LOCAIS:
        log.warning("OLLAMA_HOST (%s) não é local: o texto do paciente sairia desta máquina", host)


class OllamaExtrator(Extrator):
    def __init__(self, modelo: str | None = None, host: str | None = None, cliente=None):
        self.modelo = modelo or os.environ.get("TRIAGEM_MODELO") or MODELO_PADRAO
        self.nome = f"ollama:{self.modelo}"
        if cliente is None:
            import ollama

            host = host or os.environ.get("OLLAMA_HOST") or None
            _aviso_host(host)
            cliente = ollama.Client(host=host, timeout=TIMEOUT_S)
        self.cliente = cliente

    @staticmethod
    def _mensagens(relato: str) -> list[dict]:
        msgs = [{"role": "system", "content": INSTRUCOES}]
        for texto, resposta in EXEMPLOS:
            msgs.append({"role": "user", "content": texto})
            msgs.append({"role": "assistant", "content": json.dumps(resposta, ensure_ascii=False)})
        msgs.append({"role": "user", "content": relato})
        return msgs

    def _chamar(self, relato: str) -> _Resposta:
        try:
            resp = self.cliente.chat(model=self.modelo, messages=self._mensagens(relato),
                                     format=_Resposta.model_json_schema(),
                                     options={"temperature": 0, "num_predict": LIMITE_TOKENS})
            bruto = resp["message"]["content"]
        except Exception as e:  # rede, modelo ausente, timeout etc.
            raise ErroExtracao(f"falha ao consultar o modelo '{self.modelo}': {e}") from e
        try:
            return _Resposta.model_validate_json(bruto)
        except ValidationError as e:
            raise ErroFormato(f"resposta do modelo fora do formato: {e.error_count()} erro(s)") from e

    def extrair(self, relato: str) -> Extracao:
        ultimo = None
        for tentativa in range(1, TENTATIVAS + 1):
            try:
                return self._converter(relato, self._chamar(relato))
            except ErroFormato as e:  # falha de conexão/timeout não se resolve repetindo
                ultimo = e
                log.warning("tentativa %d/%d falhou: %s", tentativa, TENTATIVAS, e)
        raise ultimo

    @staticmethod
    def _converter(relato: str, r: _Resposta) -> Extracao:
        avisos: list[str] = []
        aceita_negado = tem_negacao(relato)
        base = sem_acentos(relato).lower()
        extraiveis = {n.value for n in NomeSinal} - {n.value for n in SINAIS_MEDIDOS}
        peso = {Status.PRESENTE: 2, Status.INCERTO: 1, Status.NEGADO: 0}
        sinais: dict[NomeSinal, Sinal] = {}
        for item in r.sinais:
            try:
                if item.nome not in extraiveis:
                    raise ValueError("sinal fora do vocabulário")
                status = Status(item.status)
                if status not in ESTADOS_EXTRAIVEIS:
                    raise ValueError(f"status {item.status!r} não permitido")
                if status == Status.NEGADO and not aceita_negado:
                    raise ValueError("negação inventada (o relato não nega nada)")
                valor = item.valor
                faixa = FAIXAS_VALOR.get(item.nome)
                if valor is not None and faixa and not faixa[0] <= valor <= faixa[1]:
                    avisos.append(f"valor {valor} de '{item.nome}' fora da faixa; descartado")
                    valor = None
                trecho = (item.trecho or "").strip()
                if not trecho:
                    raise ValueError("sem trecho que comprove")
                if sem_acentos(trecho).lower() not in base:
                    raise ValueError("o trecho citado não consta no relato")
                novo = Sinal(nome=NomeSinal(item.nome), status=status, valor=valor,
                             itens=normalizar_itens(item.itens) if status == Status.PRESENTE else [],
                             trecho=trecho, origem=Origem.EXTRAIDO_DO_RELATO)
            except ValueError as e:
                avisos.append(f"sinal '{item.nome}' descartado: {e}")
                continue
            atual = sinais.get(novo.nome)
            if atual is None or peso[novo.status] > peso[atual.status]:  # presente vence
                sinais[novo.nome] = novo

        queixas = []
        for q in r.queixas:
            try:
                queixas.append(Queixa(q))
            except ValueError:
                avisos.append(f"queixa '{q}' descartada: fora das categorias")

        alergias = None
        if r.alergias and (itens := normalizar_itens(r.alergias.get("itens") or [])):
            alergias = Alergias(status=Status.PRESENTE, itens=itens)
        return Extracao(queixa_principal=(r.queixa_principal or "").strip().lower()[:80] or None,
                        queixas=sorted(set(queixas), key=lambda q: q.value), duracao=r.duracao,
                        sinais=list(sinais.values()), alergias=alergias, avisos=avisos)
