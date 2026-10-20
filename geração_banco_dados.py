import sqlite3
import random

# Semente para reprodutibilidade dos dados simulados
random.seed(42)

# 1. Criação do arquivo de banco de dados SQLite (.db)
conn = sqlite3.connect("salus_treinamento.db")
cursor = conn.cursor()

# 2. Criando a tabela com colunas dedicadas para CADA pergunta do banco
cursor.execute("""
CREATE TABLE IF NOT EXISTS casos_treinamento (
    id_caso INTEGER PRIMARY KEY,
    queixa_principal TEXT,
    relato_livre TEXT,
    
    -- Núcleo (Q01 a Q15)
    Q01 TEXT, Q02 TEXT, Q03 TEXT, Q04 TEXT, Q05 INTEGER,
    Q06 TEXT, Q07 TEXT, Q08 TEXT, Q09 TEXT, Q10 TEXT,
    Q11 TEXT, Q12 TEXT, Q13 TEXT, Q14 TEXT, Q15 TEXT,
    
    -- Aferições (E01 a E07)
    E01_temperatura REAL,
    E02_saturacao REAL,
    E03_pressao TEXT,
    E04_f_cardiaca INTEGER,
    E05_f_respiratoria INTEGER,
    E06_glicemia INTEGER,
    E07_glasgow INTEGER,
    
    -- Módulo Dor no Peito (T01 a T03)
    T01 TEXT, T02 TEXT, T03 TEXT,
    
    -- Módulo Dor Abdominal (A01 a A05)
    A01 TEXT, A02 TEXT, A03 TEXT, A04 TEXT, A05 TEXT,
    
    -- Módulo Febre e Respiratório (R01 a R05)
    R01 TEXT, R02 TEXT, R03 TEXT, R04 TEXT, R05 TEXT,
    
    -- Complementares (C01 a C04)
    C01 TEXT, C02 TEXT, C03 TEXT, C04 TEXT,
    
    -- Metadados de Alvo e Validação
    pontuacao_alvo INTEGER,
    validado_por_clinico BOOLEAN
)
""")

queixas_possiveis = ["dor_toracica", "dor_abdominal", "respiratorio_febre", "indefinida"]

relatos_base = {
    "dor_toracica": [
        "Senti uma dor forte em aperto no peito que começou de repente há 30 minutos.",
        "Dor tipo queimação no peito irradiando para o pescoço e braço esquerdo com muito suor frio.",
        "Desconforto torácico leve ao respirar fundo, começou aos poucos hoje.",
        "Sinto como se tivesse um peso enorme no peito, falta ar e estou muito tonto.",
        "Uma pontada aguda no lado esquerdo do peito que vai e volta desde ontem à tarde.",
        "Aperto forte no peito que começou logo depois que subi as escadas, acompanhado de enjoo."
    ],
    "dor_abdominal": [
        "Minha barriga começou a doer embaixo do lado direito, com náuseas desde cedo.",
        "Dor tipo cólica intensa no abdômen inteiro, com episódios repetidos de vômito.",
        "Abdômen dolorido, duro e inchado, sem conseguir evacuar há dois dias.",
        "Sinto uma dor pontual na boca do estômago que queima e piora muito logo após comer.",
        "Dor forte na parte inferior da barriga que começou fraca e foi espalhando, agora está insuportável."
    ],
    "respiratorio_febre": [
        "Estou com febre alta, calafrios e muita dificuldade para respirar e falar frases inteiras.",
        "Tosse seca com chiado no peito e febre moderada que começou ontem à noite.",
        "Gripe forte, dor de garganta e febre alta, mas consigo respirar bem quando fico sentado.",
        "Febre alta, dores no corpo inteiro e falta de ar leve ao caminhar pela casa.",
        "Estou tossindo muito, com catarro com sangue, febre e calafrios há três dias."
    ],
    "indefinida": [
        "Estou me sentindo muito fraco, tonto e sem forças desde de manhã, sem dor específica.",
        "Mal-estar geral repentino, tontura ao levantar da cama e visão escurecida.",
        "Sensação de desmaio iminente, suor frio e confusão leve ao tentar caminhar."
    ]
}

# 3. Laço para gerar os 100 casos distintos preenchendo as colunas de forma segura via dicionário
for i in range(1, 101):
    q = random.choice(queixas_possiveis)
    relato = random.choice(relatos_base[q])
    
    # Inicializando módulos como None (NULL no banco)
    t01 = t02 = t03 = None
    a01 = a02 = a03 = a04 = a05 = None
    r01 = r02 = r03 = r04 = r05 = None
    
    if q == "dor_toracica":
        t01, t02, t03 = random.choice(["Sim", "Não"]), random.choice(["Sim", "Não"]), random.choice(["Sim", "Não"])
    elif q == "dor_abdominal":
        a01, a02, a03, a04, a05 = "Quadrante inferior direito", random.choice(["Sim", "Não"]), random.choice(["Sim", "Não"]), random.choice(["Sim", "Não"]), random.choice(["Sim", "Não"])
    elif q == "respiratorio_febre":
        r01, r02, r03, r04, r05 = "Sim, febre", random.choice(["Sim", "Não"]), random.choice(["Sim", "Não"]), random.choice(["Sim", "Não"]), random.choice(["Sim", "Não"])

    # Montando o dicionário do caso
    caso_dados = {
        "id_caso": i,
        "queixa_principal": q,
        "relato_livre": relato,
        "Q01": f"Queixa principal de {q}",
        "Q02": random.choice(["De repente", "Aos poucos", "Há poucas horas"]),
        "Q03": random.choice(["Melhorando", "Piorando", "Igual"]),
        "Q04": random.choice(["Aperto", "Queimação", "Pontada", "Cólica"]),
        "Q05": random.randint(0, 10),
        "Q06": random.choice(["Não", "Sim, irradia"]),
        "Q07": random.choice(["Não sabe", "Piora ao deitar", "Melhora em repouso"]),
        "Q08": random.choice(["Não", "Sim", "Incerto"]),
        "Q09": "Sim" if q == "respiratorio_febre" else random.choice(["Não", "Sim"]),
        "Q10": random.choice(["Não", "Sim"]),
        "Q11": random.choice(["Nenhum", "AAS", "Insulina", "Anti-hipertensivo"]),
        "Q12": random.choice(["Não", "Dipirona", "Paracetamol"]),
        "Q13": random.choice(["Nenhuma", "Hipertensão", "Diabetes", "Asma"]),
        "Q14": random.choice(["Não", "Sim"]),
        "Q15": random.choice(["Não se aplica", "Não", "Sim"]),
        "E01_temperatura": round(random.uniform(35.5, 40.0), 1),
        "E02_saturacao": random.choice([90.0, 93.0, 96.0, 98.0, 99.0, None]),
        "E03_pressao": f"{random.randint(90, 170)}x{random.randint(60, 110)}",
        "E04_f_cardiaca": random.randint(55, 130),
        "E05_f_respiratoria": random.randint(12, 28),
        "E06_glicemia": random.randint(70, 220) if random.random() > 0.4 else None,
        "E07_glasgow": random.choice([15, 15, 15, 14, 12]),
        "T01": t01, "T02": t02, "T03": t03,
        "A01": a01, "A02": a02, "A03": a03, "A04": a04, "A05": a05,
        "R01": r01, "R02": r02, "R03": r03, "R04": r04, "R05": r05,
        "C01": random.choice(["Nenhum", "Histórico familiar de infarto", "Hipertensão na família"]),
        "C02": random.choice(["Não fuma", "Fagista ocasional", "Ex-fumante"]),
        "C03": random.choice(["Normal", "Estressado", "Dormindo mal"]),
        "C04": random.choice(["Normal", "Alteração recente"]),
        "pontuacao_alvo": random.randint(15, 95),
        "validado_por_clinico": False
    }

    # Inserção dinâmica segura baseada nas chaves do dicionário
    colunas = ", ".join(caso_dados.keys())
    placeholders = ", ".join([":" + k for k in caso_dados.keys()])
    cursor.execute(f"INSERT INTO casos_treinamento ({colunas}) VALUES ({placeholders})", caso_dados)

conn.commit()
conn.close()

print("Sucesso! Arquivo 'salus_treinamento.db' gerado perfeitamente com 100 casos.")