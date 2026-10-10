"""Schema de saída da triagem (JSON final)."""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from triagem.sinais import NomeSinal, Origem, Status

VERSAO_SCHEMA = "0.1.0"


class UnidadeTempo(str, Enum):
    MINUTOS = "minutos"
    HORAS = "horas"
    DIAS = "dias"
    SEMANAS = "semanas"
    MESES = "meses"
    ANOS = "anos"


class Resposta(BaseModel):
    id_pergunta: str = Field(pattern=r"^P\d{2}$")
    resposta_bruta: str


class Duracao(BaseModel):
    valor: float = Field(ge=0)
    unidade: UnidadeTempo


class Sinal(BaseModel):
    nome: NomeSinal
    status: Status
    valor: float | str | None = None
    origem: Origem


class AlergiasMedicamentosas(BaseModel):
    status: Status = Status.NAO_MENCIONADO
    medicamentos: list[str] = Field(default_factory=list)


class DadosAtendente(BaseModel):
    model_config = ConfigDict(extra="forbid")

    idade: int = Field(ge=0, le=130)
    temperatura: float | None = None
    frequencia_cardiaca: int | None = Field(default=None, gt=0)
    pressao_sistolica: int | None = Field(default=None, gt=0)
    pressao_diastolica: int | None = Field(default=None, gt=0)
    saturacao: int | None = Field(default=None, ge=0, le=100)


class SaidaTriagem(BaseModel):
    relato_original: str = Field(max_length=200)
    respostas: list[Resposta] = Field(default_factory=list)
    queixa_principal: str | None = None
    duracao: Duracao | None = None
    sinais: list[Sinal] = Field(default_factory=list)
    alergias_medicamentosas: AlergiasMedicamentosas = Field(
        default_factory=AlergiasMedicamentosas
    )
    dados_atendente: DadosAtendente
    perguntas_pendentes: list[str] = Field(default_factory=list)
    pontuacao: int = 0
    pontuacao_provisoria: bool = True
    versao_schema: str = VERSAO_SCHEMA

    @model_validator(mode="after")
    def _sem_sinais_duplicados(self):
        nomes = [s.nome for s in self.sinais]
        if len(nomes) != len(set(nomes)):
            raise ValueError("cada sinal pode aparecer uma única vez")
        return self
