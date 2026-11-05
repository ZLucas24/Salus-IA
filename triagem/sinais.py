"""Vocabulário fechado: sinais (achados), status, origem, cores e queixas.

Os nomes dos sinais são validados contra `dados/questionario.json` e
`dados/regras.json` por testes, para que nada fique fora de sincronia.
Alergia não é sinal: é informação de segurança e fica em campo próprio.
"""

from enum import Enum


class NomeSinal(str, Enum):
    # --- núcleo (Q02-Q15) ---
    INICIO_SUBITO = "inicio_subito"
    PIORA_PROGRESSIVA = "piora_progressiva"
    DOR_EM_APERTO = "dor_em_aperto"
    DOR = "dor"                                  # valor: nota de 0 a 10
    IRRADIACAO = "irradiacao"
    ALTERACAO_CONSCIENCIA = "alteracao_consciencia"
    DISPNEIA = "dispneia"
    USO_ANTICOAGULANTE = "uso_anticoagulante"
    USO_INSULINA = "uso_insulina"
    ANTITERMICO_RECENTE = "antitermico_recente"
    DOENCA_CRONICA = "doenca_cronica"            # itens: doenças
    CIRURGIA_INTERNACAO_PREVIA = "cirurgia_internacao_previa"
    GRAVIDEZ_POSSIVEL = "gravidez_possivel"
    AMAMENTANDO = "amamentando"
    # --- módulo dor no peito (T01-T03) ---
    SUOR_FRIO_ENJOO_TONTURA = "suor_frio_enjoo_tontura"
    DOR_PIORA_ESFORCO_RESPIRAR = "dor_piora_esforco_respirar"
    RISCO_TROMBOEMBOLICO = "risco_tromboembolico"
    # --- módulo dor abdominal (A01-A05) ---
    DOR_ABDOMINAL = "dor_abdominal"              # itens: local
    DOR_MIGRATORIA = "dor_migratoria"
    VOMITO = "vomito"                            # valor: episódios, se informado
    SANGUE_VOMITO_FEZES = "sangue_vomito_fezes"
    SEM_GASES_EVACUACAO = "sem_gases_evacuacao"
    DIARREIA = "diarreia"
    ABDOME_RIGIDO_DISTENDIDO = "abdome_rigido_distendido"
    ALTERACAO_URINARIA = "alteracao_urinaria"
    # --- módulo febre e respiratório (R01-R05) ---
    FEBRE_REFERIDA = "febre_referida"            # valor: maior temperatura referida
    CALAFRIOS = "calafrios"
    FALA_ENTRECORTADA = "fala_entrecortada"
    CHIADO = "chiado"
    TOSSE_COM_SANGUE = "tosse_com_sangue"
    CONTATO_OU_VIAGEM = "contato_ou_viagem"
    DIFICULDADE_BEBER = "dificuldade_beber"
    # --- derivados das aferições (E01-E07), nunca vêm do relato ---
    FEBRE_ATUAL = "febre_atual"                  # valor: temperatura medida
    HIPOXEMIA = "hipoxemia"                      # valor: saturação
    TAQUICARDIA = "taquicardia"                  # valor: frequência cardíaca
    TAQUIPNEIA = "taquipneia"                    # valor: frequência respiratória
    HIPOTENSAO = "hipotensao"                    # valor: pressão sistólica
    GLICEMIA_ALTERADA = "glicemia_alterada"      # valor: glicemia
    GLASGOW_REDUZIDO = "glasgow_reduzido"        # valor: escala de Glasgow


# Sinais calculados a partir das aferições do atendente.
SINAIS_MEDIDOS = frozenset({
    NomeSinal.FEBRE_ATUAL, NomeSinal.HIPOXEMIA, NomeSinal.TAQUICARDIA,
    NomeSinal.TAQUIPNEIA, NomeSinal.HIPOTENSAO, NomeSinal.GLICEMIA_ALTERADA,
    NomeSinal.GLASGOW_REDUZIDO,
})


class Status(str, Enum):
    """Só NEGADO conta como "não". Os estados de desconhecimento nunca contam
    como ausência do sinal."""

    PRESENTE = "presente"
    NEGADO = "negado"
    NAO_MENCIONADO = "nao_mencionado"  # ninguém perguntou / o relato não cita
    NAO_SABE = "nao_sabe"
    RECUSOU = "recusou"
    NAO_SE_APLICA = "nao_se_aplica"
    INCERTO = "incerto"                # extração em dúvida

    @property
    def desconhecido(self) -> bool:
        return self in DESCONHECIDOS


DESCONHECIDOS = frozenset({Status.NAO_SABE, Status.RECUSOU, Status.INCERTO})

# Marcadores que o atendente pode usar no lugar de uma resposta.
MARCADORES = {
    "nao_sabe": Status.NAO_SABE,
    "recusou": Status.RECUSOU,
    "nao_se_aplica": Status.NAO_SE_APLICA,
}


class Origem(str, Enum):
    RESPOSTA_DIRETA = "resposta_direta"
    EXTRAIDO_DO_RELATO = "extraido_do_relato"
    MEDIDO_PELO_ATENDENTE = "medido_pelo_atendente"
    NENHUMA = "nenhuma"  # sinal sem nenhuma fonte (nao_mencionado)


class Cor(str, Enum):
    """Ordem crescente de urgência (nomes inspirados em escalas de risco)."""

    AZUL = "azul"
    VERDE = "verde"
    AMARELO = "amarelo"
    LARANJA = "laranja"
    VERMELHO = "vermelho"

    @property
    def nivel(self) -> int:
        return list(Cor).index(self)


class Queixa(str, Enum):
    """Categorias que ativam módulos de perguntas. Só reconhecimento de texto."""

    DOR_TORACICA = "dor_toracica"
    DOR_ABDOMINAL = "dor_abdominal"
    RESPIRATORIO_FEBRE = "respiratorio_febre"
    OUTRA = "outra"
    INDEFINIDA = "indefinida"


class SexoBiologico(str, Enum):
    FEMININO = "feminino"
    MASCULINO = "masculino"
    INTERSEXO = "intersexo"
    AUSENTE = "ausente"  # não informado: perguntas condicionadas ao sexo continuam valendo
