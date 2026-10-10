"""Vocabulário fechado de sinais, derivado do questionário (P02-P12).

Alergia medicamentosa (P13) fica de fora: não entra na pontuação de risco.
Duração (P02) é um campo próprio do schema, não um sinal.
"""

from enum import Enum


class NomeSinal(str, Enum):
    INICIO_SUBITO = "inicio_subito"                # P03
    DOR = "dor"                                    # P04 (valor: 0-10)
    LOCAL_DOR = "local_dor"                        # P05 (valor: opção)
    DISPNEIA = "dispneia"                          # P06
    SANGRAMENTO = "sangramento"                    # P07 (valor: "ativo_agora")
    ALTERACAO_CONSCIENCIA = "alteracao_consciencia"  # P08 (desmaio/confusão)
    CONVULSAO = "convulsao"                        # P08
    FEBRE = "febre"                                # P09 (valor: °C)
    VOMITO_PERSISTENTE = "vomito_persistente"      # P10
    TRAUMA = "trauma"                              # P11
    GRAVIDEZ = "gravidez"                          # P12
    DOENCA_CRONICA = "doenca_cronica"              # P12 (valor: doenças)


class Status(str, Enum):
    PRESENTE = "presente"
    NEGADO = "negado"
    NAO_MENCIONADO = "nao_mencionado"


class Origem(str, Enum):
    RESPOSTA_DIRETA = "resposta_direta"      # pergunta fechada; prevalece em divergência
    EXTRAIDO_DO_RELATO = "extraido_do_relato"  # texto breve da P01
