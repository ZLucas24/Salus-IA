"""Schema de saída da triagem (JSON final) e modelos auxiliares."""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from triagem.sinais import Cor, NomeSinal, Origem, Queixa, SexoBiologico, Status

VERSAO_SCHEMA = "0.2.0"


class UnidadeTempo(str, Enum):
    MINUTOS = "minutos"
    HORAS = "horas"
    DIAS = "dias"
    SEMANAS = "semanas"
    MESES = "meses"
    ANOS = "anos"


class Resposta(BaseModel):
    """Resposta como o atendente a registrou, guardada para auditoria."""

    id_pergunta: str = Field(pattern=r"^[A-Z]\d{2}$")
    resposta_bruta: str


class Duracao(BaseModel):
    valor: float = Field(ge=0, le=1000, allow_inf_nan=False)
    unidade: UnidadeTempo


class Sinal(BaseModel):
    """Um achado do vocabulário fechado.

    `valor` é sempre numérico (nota da dor, temperatura medida etc.) e `itens`
    guarda listas de opções (doenças, local da dor). `status_no_relato` só é
    preenchido quando o relato diverge da resposta direta, que prevalece.
    """

    nome: NomeSinal
    status: Status
    valor: float | None = Field(default=None, allow_inf_nan=False)
    itens: list[str] = Field(default_factory=list)
    origem: Origem
    trecho: str | None = None
    status_no_relato: Status | None = None


class Alergias(BaseModel):
    """Informação de segurança para a equipe; não entra na pontuação."""

    status: Status = Status.NAO_MENCIONADO
    tipos: list[str] = Field(default_factory=list)  # medicamento, alimento, contraste
    itens: list[str] = Field(default_factory=list)  # nomes informados


class DadosAtendente(BaseModel):
    """Cadastro e aferições registrados pela enfermagem. Só a idade é obrigatória.

    Aferição ausente significa "não aferido", nunca "normal".
    """

    model_config = ConfigDict(extra="forbid")

    idade: int = Field(ge=0, le=130)
    sexo_biologico: SexoBiologico = SexoBiologico.AUSENTE
    temperatura: float | None = Field(default=None, allow_inf_nan=False)
    saturacao: float | None = Field(default=None, allow_inf_nan=False)
    pressao_sistolica: float | None = Field(default=None, allow_inf_nan=False)
    pressao_diastolica: float | None = Field(default=None, allow_inf_nan=False)
    frequencia_cardiaca: float | None = Field(default=None, allow_inf_nan=False)
    frequencia_respiratoria: float | None = Field(default=None, allow_inf_nan=False)
    glicemia: float | None = Field(default=None, allow_inf_nan=False)
    glasgow: int | None = None


class Alerta(BaseModel):
    """Aviso visível ao profissional (divergência, dado incompleto, falha)."""

    codigo: str
    mensagem: str
    referencias: list[str] = Field(default_factory=list)


class RegraAplicada(BaseModel):
    id: str
    descricao: str
    efeito: str


class Classificacao(BaseModel):
    """Resultado do motor de regras. Sempre provisório neste protótipo."""

    cor: Cor = Cor.VERDE
    pontuacao: int = Field(default=0, ge=0, le=100)
    provisoria: bool = True
    regras_validadas: bool = False
    regras_aplicadas: list[RegraAplicada] = Field(default_factory=list)


class SaidaTriagem(BaseModel):
    relato_original: str = Field(default="", max_length=200)
    respostas: list[Resposta] = Field(default_factory=list)
    queixa_principal: str | None = None
    queixas: list[Queixa] = Field(default_factory=list)
    modulos_ativos: list[str] = Field(default_factory=list)
    duracao: Duracao | None = None
    sinais: list[Sinal] = Field(default_factory=list)
    alergias: Alergias = Field(default_factory=Alergias)
    dados_atendente: DadosAtendente
    afericoes_faltando: list[str] = Field(default_factory=list)
    perguntas_pendentes: list[str] = Field(default_factory=list)
    proxima_pergunta: str | None = None
    alertas: list[Alerta] = Field(default_factory=list)
    classificacao: Classificacao = Field(default_factory=Classificacao)
    extrator: str
    versao_schema: str = VERSAO_SCHEMA

    @model_validator(mode="after")
    def _sem_sinais_duplicados(self):
        nomes = [s.nome for s in self.sinais]
        if len(nomes) != len(set(nomes)):
            raise ValueError("cada sinal pode aparecer uma única vez")
        return self
