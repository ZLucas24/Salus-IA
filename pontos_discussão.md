### *Pontos de que devemos discutir sobre a infra do projeto:*

1. No Readme .md temos uma referêcia a uma mock de extratos porém ele já existe (extrator_ollama.py)

2. Ainda no Readme temos a seguinte frase: "É necessário que utilizemos o agente para além disso, devemos expandir a tecnologia para todo e qualquer hospital.", tenho receio de interpretarem mal está frase como algo ruim de estarmos tendo retirar os empregos dos humanos,sabe? (revisar) 

3. Atenção ao uso do Supabase, eu observei que hoje nenhum arquivo hoje em dia importa essa ferramenta, mas devemos nos atentar ao que iremos enviar temos que segir a LGPD. 

4. A LGPD considera sexo biológico um dados sensível mas saber qual auxilia o modelo a intuir quais devem ser as próximas perguntas, então minhas sugestão seria: colocar no dados_atendente a variável sexo biológico podendo ser qualificado como: Feminino, masculino, intersexo e ausente. Assim, no caso da variável estar como "ausente" a pergunta sobre gravidez, por exemplo, continua obrigatória. (obs: essa pode ser uma questão a ser debatida com um profissional da saúde, pq o jeito que está também funciona porém não sei se é o jeito ótimo)

5. Na questão 6 do roterio "Está vomitando sem parar?" talvez não seja a pergunta exata mas sim "Teve vomito?" e pudessemos marcar a quantidade ou a intensidade.

6. Outra preocupação é com perguntas com  saídas excluivas com sim ou não, pois, deviamos criar uma possível "não se aplica" (por exemplo para homem em relação a gravidez) e código ignora as perguntas com essa resposta. Mas para além disso, vale distinguir um "recusou se responder" ou "não soube" de um "não" para segurança clínica.

7. Existe um problema estrutural os dados de entrada da ficha: idade, temperatura,  frequência cardiáca pressão arterial e saturação não podem ser "esquecidos" devem ser verificados como irregulares ou não pois podem nos revelar informações também , além de que dependendo da idade é prioritário.

8. Problemas em relção a mensuração da febre.
    A temperatura pode ser registrada em dois lugares diferentes da ficha, por pessoas diferentes, em momentos diferentes:

    Na P09 (febre): o atendente pergunta ao paciente “Teve febre? Mediu quanto?”. O paciente responde algo como “tive, medi 39 em casa”. Esse número é o que o paciente diz que mediu, antes de chegar.

    Em dados_atendente.temperatura: o atendente coloca o termômetro no paciente na hora e anota o que ele mesmo mediu na UPA.

    Tem um problema de lógica esquecendo de condicionar outros fatores além de não relacionar o estado atual do paciente como o mais importante: 

    *O estado atual manda*. O termômetro é objetivo e reflete o paciente neste momento. É o que deve ancorar a pontuação.
    *O histórico ajusta, não substitui.* Febre de 39 °C há 3 horas e 36,5 °C agora, com antitérmico tomado há 1 hora, é um paciente que provavelmente está mais doente do que o número atual mostra. O remédio mascara a febre, mas a causa continua lá.
    *Evita o erro mais perigoso:* o paciente dizer “não tive febre” e o aparelho marcar 39,2. Aí vale a medição.
    
    Três campos novos, todos de resposta simples:
    Temperatura atual (já existe em dados_atendente), passando a ser a fonte do sinal de febre ativa.
    Febre referida: sim/não, com a temperatura mais alta que ele mediu, se mediu.
    Antitérmico: sim/não, qual e há quanto tempo (mesmo formato de número + unidade da P02). Mais “há quanto tempo começou a febre”.

    A regra, em linguagem simples: a pontuação parte da temperatura atual; se houver febre referida e antitérmico recente, a pontuação não cai como se o paciente estivesse bem, e o sistema destaca para o enfermeiro “febre mascarada por antitérmico”.

    Pontos de atenção
    Antitérmico tem janela de efeito. Dipirona e paracetamol agem por poucas horas. Quanto mais recente a dose, mais a temperatura atual subestima o quadro. A janela exata (por exemplo, “menos de 6 horas”) é decisão do revisor clínico.
    Fila não pode premiar o remédio. Se o paciente toma antitérmico e a nota cai, o sistema piora justamente os mais doentes. Por isso o histórico só pode manter ou elevar, nunca reduzir, o que combina com a regra “nada reduz a pontuação” do pitch.
    Não é só febre. O mesmo raciocínio vale para dor (analgésico) e pressão (medicação anti-hipertensiva). Se fizer isso para a febre, vale decidir se vira um padrão: “o que tomou e quando”.
    Recusa e dúvida. Muitos pacientes não sabem a temperatura que tiveram nem quando tomaram o remédio. O campo precisa aceitar “não sei” sem travar a ficha.
    Sistema não decide sozinho. Qualquer limite (o que é febre, quantas horas contam) vem do enfermeiro ou médico que revisar as regras, e o enfermeiro continua com a palavra
    (texto IA)

9. As variáveis numéricas devem ser float e não int (saturação).

10. Validação cruzada:
    O estado atual manda. O termômetro é objetivo e reflete o paciente neste momento. É o que deve ancorar a pontuação.
    O histórico ajusta, não substitui. Febre de 39 °C há 3 horas e 36,5 °C agora, com antitérmico tomado há 1 hora, é um paciente que provavelmente está mais doente do que o número atual mostra. O remédio mascara a febre, mas a causa continua lá.
    Evita o erro mais perigoso: o paciente dizer “não tive febre” e o aparelho marcar 39,2. Aí vale a medição.
    Como eu estruturaria

    Três campos novos, todos de resposta simples:

    Temperatura atual (já existe em dados_atendente), passando a ser a fonte do sinal de febre ativa.
    Febre referida: sim/não, com a temperatura mais alta que ele mediu, se mediu.
    Antitérmico: sim/não, qual e há quanto tempo (mesmo formato de número + unidade da P02). Mais “há quanto tempo começou a febre”.

    A regra, em linguagem simples: a pontuação parte da temperatura atual; se houver febre referida e antitérmico recente, a pontuação não cai como se o paciente estivesse bem, e o sistema destaca para o enfermeiro “febre mascarada por antitérmico”.

    Pontos de atenção
    Antitérmico tem janela de efeito. Dipirona e paracetamol agem por poucas horas. Quanto mais recente a dose, mais a temperatura atual subestima o quadro. A janela exata (por exemplo, “menos de 6 horas”) é decisão do revisor clínico.
    Fila não pode premiar o remédio. Se o paciente toma antitérmico e a nota cai, o sistema piora justamente os mais doentes. Por isso o histórico só pode manter ou elevar, nunca reduzir, o que combina com a regra “nada reduz a pontuação” do pitch.
    Não é só febre. O mesmo raciocínio vale para dor (analgésico) e pressão (medicação anti-hipertensiva). Se fizer isso para a febre, vale decidir se vira um padrão: “o que tomou e quando”.
    Recusa e dúvida. Muitos pacientes não sabem a temperatura que tiveram nem quando tomaram o remédio. O campo precisa aceitar “não sei” sem travar a ficha.
    Sistema não decide sozinho. Qualquer limite (o que é febre, quantas horas contam) vem do enfermeiro ou médico que revisar as regras, e o enfermeiro continua com a palavra. 
    (gerado por IA)

11. Tenho uma questionamento em relação a qualificação da febre: 
    Pesquisa Web: a partir de 37,8°C em adultos e de 37,5°C em crianças
    No momento de qualificar se uma pessoa está com febre colocar um valor fixo talvez não seja a melhor opção,pois devemos observar a idade e a intensidade. (obs: só soltei a bomba não bem como resolver, porém acho que qualificar com febre ou sem por idade e colocar uma possibilidade de quantificicar a intensidade para colocar como parâmetro)
    Podiamos debater isso com um  profissional da saúde também.

12. Uma duração só para tudo. A P02 vale para a queixa inteira. Se o paciente tem tosse há 1 mês e febre há 2 dias, não há como registrar.

13. A P05 aceita uma opção, mas há dor em mais de um lugar.

14. Na P13, o nome do medicamento é livre e separado por vírgula ou ponto e vírgula, sem normalização (“dipirona” e “Novalgina” são o mesmo).(sugestão da IA porém creio que o enfermeiro que não souber isso mds). Texto gerado por IA

15. Não há id do atendimento, horário de chegada nem id do atendente e ccombinamos em considerar isso como um fator para colocar as pessoas na fila.

16. O roteiro manda o atendente perguntar: “Há sangramento? Está sangrando agora?” São duas perguntas em uma:

    Há sangramento? (ha_sangramento)
    Está sangrando agora? (sangrando_agora)

    A segunda só faz sentido se a primeira for “sim”.

    Os três cenários

    Cenário A: o atendente pergunta as duas e o paciente diz que há sangramento, mas já parou:

    json
    "P07": {"ha_sangramento": true, "sangrando_agora": false}

    Cenário B: o paciente está sangrando agora, hemorragia ativa:

    json
    "P07": {"ha_sangramento": true, "sangrando_agora": true}

    Cenário C: o atendente perguntou só a primeira parte e esqueceu a segunda:

    json
    "P07": {"ha_sangramento": true}
    O que o código faz com cada um

    Está nesta linha do questionario.py:

    python
    agora = _bool(d["sangrando_agora"], "sangrando_agora") if "sangrando_agora" in d else False

    Em português: “se o campo sangrando_agora existir, use o valor dele; se não existir, assuma False”.

    E depois o sinal é montado assim: se agora for verdadeiro, o valor é "ativo_agora"; senão, o valor fica vazio (None).

    Resultado:

    Cenário	O que aconteceu na vida real	Saída do sistema
    A	Perguntou, e não está sangrando agora	sangramento = presente, valor None
    B	Perguntou, e está sangrando agora	sangramento = presente, valor "ativo_agora"
    C	Esqueceu de perguntar	sangramento = presente, valor None

    Os cenários A e C saem idênticos. O sistema não consegue distinguir “o paciente disse que não” de “ninguém perguntou”.

    Por que isso é perigoso

    Sangramento ativo é uma das situações mais urgentes na triagem. No cenário C, o paciente pode estar sangrando agora, mas como o atendente não registrou nada, o sistema trata como se tivesse sido confirmado que não está.

    Além disso, o sistema tem um mecanismo de segurança para esquecimentos: a lista perguntas_pendentes, que avisa o atendente “volte e pergunte isto”. Mas a P07 só entra nessa lista se ficar totalmente em branco ou se o sinal sangramento ficar nao_mencionado. No cenário C, o sinal está presente, então a P07 é considerada completa e o aviso nunca aparece. A falha fica silenciosa.

    Como corrigir

    O mais simples é seguir o que a P04 já faz com a escala: quando a resposta é “sim”, o campo extra passa a ser obrigatório.

    python
    if ha and "sangrando_agora" not in d:
        raise ErroResposta("informe 'sangrando_agora' quando há sangramento")

    Assim o cenário C é recusado com uma mensagem clara, e o atendente completa a ficha.

    A alternativa, mais flexível para uma triagem em que nem tudo dá tempo de perguntar, é aceitar o cenário C, mas marcá-lo como incompleto e manter a P07 em perguntas_pendentes. O valor do sinal teria então três opções (ativo_agora, nao_ativo_agora, nao_informado) em vez de dois.

17. Quando for corrigir o que descidirmos pode por favor para documentar as funções para facilitar meu trabalho :)

18. Hoje o agente não se adpta, ou seja, não gera por si só as perguntas (obs: isso é realmete complexo tendo em vista que ainda não temos um banco de dados) mas temos que trabalhar nas seguinte evoluções:  
    1. Adaptação por regras (aplica_se): o questionário ganha condições, como P05 só se P04 for sim, ou gravidez conforme o sexo biológico. Quem decide o caminho é código determinístico, não a IA. É o mais barato, é testável e combina com a regra do projeto de que a IA não decide gravidade.
    2. Sugestão de próxima pergunta: depois da P01, o sistema olha os sinais extraídos e destaca as perguntas mais relevantes (“citou dor no peito: confirmar início súbito, falta de ar, local”). Pode ser uma tabela queixa → perguntas prioritárias, escrita em código e revisada por um clínico, e a IA só reconhece a queixa. O atendente continua no controle.
    3. Perguntas geradas pela IA: o modelo escreve perguntas novas na hora. É o mais “agente”, mas o mais arriscado: não é auditável, pode inventar, e o seu documento já exige que a IA nunca decida sozinha. Eu não recomendo para o MVP.
    *prescisamos desenvolver o 1 e 2 pelo menos para o Hackathon*

19. Segurança e dados reais (LGPD) -> não importante para infra do hackton mas para o pitch
    Hoje o projeto usa só dados simulados. Para dados reais, a extração do relato roda em modelo local (Ollama), em infraestrutura em território nacional.
    Serviços externos (Supabase e Hugging Face) ficam desativados ou restritos a dados simulados.
    Isso reduz o risco, mas não substitui: base legal, minimização dos campos, controle de acesso, criptografia, retenção e eliminação dos dados, proteção dos logs e plano de resposta a incidentes (arts. 46 e 48).
    A receita vem da assinatura pelo serviço, nunca da venda ou do compartilhamento de dados de pacientes (art. 11, § 4º).
    A confirmar: o que o Ollama registra em disco, qual região o Supabase usa e o prazo atual de comunicação de incidentes à ANPD.

### Sinais.py:
1. Status: acrescentar NAO_SABE, RECUSOU e NAO_SE_APLICA. NAO_MENCIONADO passa a significar só “ninguém perguntou”. Regra para o motor: só NEGADO conta como “não”, e os estados desconhecidos nunca contam.
2. Origem: acrescentar NENHUMA e MEDIDO_PELO_ATENDENTE. O entrevista.py passa a usar NENHUMA nos sinais não mencionados, em vez de RESPOSTA_DIRETA, que hoje é falso. A temperatura e a saturação do atendente vão precisar da segunda.
3. Dividir FEBRE: FEBRE_REFERIDA (o que o paciente diz, vem da P09) e FEBRE_ATUAL (vem do termômetro do atendente). A temperatura medida passa a alimentar um sinal, e o caso “não tive febre” com 39,2 °C deixa de passar.
4. Acrescentar ANTITERMICO_RECENTE. Sem ele não dá para implementar a regra “febre mascarada”.
5. Acrescentar SANGRAMENTO_ATIVO como sinal próprio, tirando a string "ativo_agora" do valor de SANGRAMENTO. Assim o cenário C da P07 deixa de ser idêntico ao A.
6. Renomear VOMITO_PERSISTENTE para VOMITO, com o número de episódios como valor. Quem decide o que é persistente é o motor.
7. Um teste que cruze NomeSinal com o questionario.json e falhe se algum nome não bater. Também remover o & NOMES_SINAIS do entrevista.py, que esconde erros de digitação.

## Corrigir junto com o schema.py (mesma mudança)

8. Substituir o valor: float | str | None por campos tipados, com lista de verdade para doenças crônicas e locais da dor.
9. No extrator_ollama.py, descartar só o sinal inválido e registrar um aviso, em vez de derrubar a extração inteira.

## Esperar o revisor clínico

10. Separar ALTERACAO_CONSCIENCIA em desmaio e confusão.
11. Quais sinais novos as 3 queixas do MVP exigem (tosse, dor de garganta, formigamento etc.).
12. Agrupar os sinais por categoria (sintoma, risco, evento), o que só vale a pena quando o motor de regras estiver desenhado.

## Só texto
13. Atualizar os comentários com P03, P04 e o docstring “(P02-P12)”. O ideal é remover as referências a perguntas daqui, já que elas duplicam o questionário e ficam desatualizadas.

### Shema.py: 
1. Dado contraditório é descartado em silêncio. Estes casos passam sem erro:
        P04 {"resposta": false, "escala": 8}: a nota 8 some.
        P09 {"resposta": false, "valor": 39}: a temperatura some.
        P13 {"resposta": false, "texto": "dipirona"}: a alergia some.
    O mais provável é o atendente ter marcado “não” por engano, e a informação clínica se perde sem aviso. Deve ser erro ou, no mínimo, um alerta de inconsistência.
2. NaN e Infinity passam em _numero. O json.load do Python aceita esses valores, e as comparações com minimo e maximo dão falso para NaN, então ele não é barrado. Numa duração, o Pydantic provavelmente barra depois com uma exceção que o código não captura, e o resultado é um traceback. Em temperatura ou escala, o NaN pode chegar ao JSON de saída. Falta um math.isfinite.

3. Há exceções que escapam do tratamento. O entrevista.py só captura ErroResposta. Um nome de sinal errado no questionario.json (NomeSinal(...)), uma chave faltando ou um erro do Pydantic viram traceback, e a CLI promete códigos de saída 1 e 2. O próprio questionário também não é validado ao ser carregado (ids duplicados, chaves ausentes). Eu validaria o questionário uma vez na carga e falharia com mensagem clara.

4. Não há validação cruzada entre perguntas. Cada uma é validada isolada, então estes casos passam:
        P05 preenchida com P04 “não”;
        gravidez “sim” em paciente de 6 anos;
        “começou de repente” com duração de meses;
        a ficha_06 tem relato “há 2 horas” e P02 em 3 dias, sem nenhum aviso.
    Eu faria uma etapa separada de consistência que gera alertas, sem rejeitar a ficha.
5. P08, P12 e P13 rejeitam resposta parcial. O _dict exige todas as partes, então perguntar só o desmaio e esquecer a convulsão derruba a ficha inteira, ao contrário do roteiro (“em branco é melhor que chute”). O mesmo critério que defendi para P04, P07 e P09 vale aqui: aceitar e deixar a parte faltante pendente.
6. A P13 valida pouco o campo texto.
        Aceita lista (não documentada no README) e converte qualquer coisa com str(): o número 5 vira o medicamento “5”.
        Separa só por vírgula e ponto e vírgula, enquanto o extrator mock também separa por “e”. O mesmo relato gera listas diferentes conforme a origem.
        Não remove duplicatas nem limita o tamanho. Por ser texto livre, pode levar dado pessoal, o que pesa na LGPD.
7. Interpretacao só comporta sinais, duração e alergias. Os dados novos que discutimos (antitérmico, sexo biológico, vitais) não têm onde sair. A estrutura precisa de campos genéricos, e a mesclagem (duracao = r.duracao or duracao no entrevista.py) hoje deixa a última resposta vencer sem aviso.

8. Limites embutidos no código. A escala de dor vem do JSON, mas a temperatura 30 a 45 está fixa no .py. Os limites devem ficar todos no mesmo lugar, para o revisor clínico poder lê-los.
9. A escala de dor aceita decimais (7,5) e a duração não tem máximo (999999 anos).
10. Doenças duplicadas na P12 (["diabetes", "diabetes"]) passam.
11. O limite de 200 caracteres do relato é checado antes do strip, e o texto é guardado sem limpar.
12. BOM no Windows. O questionário é lido com utf-8, enquanto a CLI lê a ficha com utf-8-sig. Se alguém editar o JSON com BOM, ele quebra. O arquivo também é relido do disco a cada ficha, sem cache.
13. As mensagens de erro não mostram o valor recebido. “‘valor’ deve ser um número” ajuda menos que “recebi ‘abc’”.
14. A cadeia de if tipo == cresce a cada tipo novo. Uma tabela tipo → função facilitaria a extensão.
15. Lacunas de teste (o arquivo só é exercitado via processar_ficha). Não há teste para P07 com agora sem sangramento, P08 incompleta, escala 11, valor negativo, relato em branco ou P12 com duplicatas.

### entrevista.py:
1. A falha do extrator não é tratada. extrator.extrair(relato) está fora de qualquer try. Se o Ollama cair ou responder fora do formato, o ErroExtracao vira traceback, e a ficha inteira se perde, inclusive as respostas fechadas que já estavam válidas. O pitch promete “tentar de novo uma vez e, se falhar, mostrar erro claro”. A saída segura é degradar: manter os sinais diretos, registrar que a extração falhou e deixar a P01 pendente.
2. A divergência só vai para o log, e o log é só stderr. Quando o relato diz “falta de ar” e a resposta fechada diz “não”, prevalece o “não” e a única marca é uma linha de log.info, que não entra no JSON. O enfermeiro nunca vê o conflito, e este é o caso em que o relato pode estar certo e o atendente ter marcado errado. Eu manteria a regra de prevalência (pelo desenho do projeto), mas registraria a divergência na saída, como alerta visível. Hoje o único registro é o log.info.
3. A extração do relato não alimenta as pendentes. O sinal vindo do relato conta como “preenchido” para perguntas_pendentes, mas só a pergunta sem resposta direta entra. Em compensação, uma pergunta respondida com “não” continua fora da lista mesmo quando o relato a contradiz. As duas lógicas deveriam considerar divergência como motivo de revisão.
4. Sinais derivados do relato dependem de um único modelo local, sem fallback. Se a extração falhar, não há plano B. Isso conversa com o item 1.
5. A regra “extrator só informa o que o relato cita” é aplicada em dois lugares. O filtro != NAO_MENCIONADO em entrevista.py e o filtro de negação no extrator_ollama.py fazem partes do mesmo trabalho. Se um dos dois mudar, o outro pode esconder o problema.
6. A função faz tudo. São cerca de 100 linhas misturando validação, interpretação, extração, fusão e pendências. Dividir em etapas (validar, interpretar, extrair, mesclar, pendências) tornaria cada uma testável sozinha, e o motor de regras poderia entrar como mais uma etapa.
7. Erros acumulados, mas o extrator só roda se tudo passar. Isso é correto para economizar chamadas, mas significa que os problemas do relato (modelo fora do ar) só aparecem depois que o atendente corrige a ficha. Combinado com o item 1, o atendente pode corrigir tudo e ainda assim ver a ficha falhar.
8. A conversão _bruto_para_texto guarda o bruto de cada resposta como string JSON, e o Resposta ganha um campo que o motor não vai usar. Para auditoria é útil, mas hoje serve só para o texto do README.
9. relato = brutas.get("P01") or "" trata None, string vazia e False do mesmo jeito. Como a validação do tipo já rodou antes, o risco é pequeno, mas um relato de espaços em branco passou pela interpretação? Passa pelo .strip() na validação, então não. Fica só como detalhe de clareza.
10. Não há medida de tempo nem registro de cada etapa. Para o log de auditoria do pitch (entrada, regra, resultado), este é o lugar natural, e hoje só existe uma linha ao final.
11. pontuacao_provisoria=True fixo é definido aqui, enquanto o pontuar é quem sabe se o resultado é provisório. A decisão deveria morar junto da pontuação.
12. A ordem das pendentes segue o dicionário de perguntas. Quando houver prioridade clínica (sangramento antes de alergia), a ordem deveria ser explícita.
13. log com nome fixo "triagem": funciona, mas o padrão logging.getLogger(__name__) facilita filtrar por módulo.
14. Os testes cobrem o fluxo feliz e a divergência, mas não cobrem: falha do extrator, relato sem nenhuma resposta fechada com divergência de duração, nem a ordem das pendentes.

### extratores:
1. O Ollama pode inventar “sem alergia”. O filtro de negação só vale para os sinais. A alergia vinda do modelo passa sem filtro, inclusive com status = negado, e um dos exemplos do prompt reforça esse comportamento. Se a P13 não foi respondida, o enfermeiro vê “sem alergia a medicamento” sem que o paciente tenha dito isso. A alergia é o campo em que o roteiro manda insistir, então o erro mais perigoso é justamente o “negado” inventado. Eu aceitaria do relato só presente, e negado apenas da P13.
2. O mock lê “não tenho alergia a remédio” como alergia presente. Ele só reconhece sem alergia. Com “não tenho alergia a remédio”, a regex captura ["remedio"] e devolve presente. O mesmo vale para “sou alérgico a ela” (vira o medicamento “ela”) e para “alérgico a dipirona e tenho dor” (vira ["dipirona", "tenho dor"]). Como o mock é o extrator padrão, isso acontece em quem rodar sem --extrator.
3. No mock, a negação vence a presença em qualquer lugar do texto. “Dor no peito, sem dor nas costas” sai com dor = negado, porque o padrão de negação é testado primeiro e sobre o texto inteiro. O erro vai na direção que esconde um sintoma.
4. O mock lê “acidente vascular” (AVC) como trauma. O padrão acidente casa por substring. Também faltam palavras comuns: “doendo” e “dói” não geram dor (embora o próprio prompt do Ollama use “barriga doendo”), e “dispneia” ou “sufocando” não geram dispneia.
5. Os valores vindos do relato escapam das validações da P09. A febre direta é limitada a 30 a 45 °C, e a dor a 0 a 10. O extrator aceita qualquer número, então “39 graus” pode virar valor = 390 ou dor = 15, e a duração aceita 0. O motor de regras vai tratar esses campos como confiáveis. A solução é passar os valores extraídos pelas mesmas funções de validação, descartando o valor (não o sinal) quando for inválido.
6. O .env é ignorado pelo comando principal. Só o relato.py chama load_dotenv(). O cli.py e o avaliar.py não chamam. Assim, python -m triagem ficha.json --extrator ollama ignora TRIAGEM_MODELO e OLLAMA_HOST do .env, ao contrário do que o README e o CLAUDE.md afirmam.
7. Nada garante que o texto do paciente fica na máquina. O relato vai para OLLAMA_HOST, que pode apontar para um servidor remoto. O CLAUDE.md diz que o modelo é local, mas o código não verifica. Isso pesa na LGPD (a mesma conversa do Supabase). Eu falharia ou avisaria quando o host não for local.
8. Sinais conflitantes do modelo são resolvidos pela ordem. O dicionário do Ollama deixa o último vencer: se o modelo devolver dor = presente e depois dor = negado, o negado fica. O critério conservador é presente vencer sempre. O mock não tem esse problema, mas a regra deveria estar no contrato.
9. Os exemplos do prompt podem ficar desatualizados sem aviso. O prompt lista os nomes de sinais automaticamente, mas os três exemplos têm nomes escritos à mão. Depois de dividir febre ou renomear vomito_persistente, eles passam a ensinar nomes inválidos. Um teste que valide cada exemplo contra o _Resposta resolve.
10. Possível vazamento entre prompt e gabarito. O CLAUDE.md proíbe que os dados de teste entrem no treino, e os exemplos do prompt têm a mesma estrutura de casos do gabarito (falta de ar “desde ontem”, alergia a antibiótico). Eu conferiria que nenhum caso do relatos_simulados.json aparece nos EXEMPLOS e criaria um teste para isso.
11. O pitch promete uma segunda tentativa, e ela não existe. Não há retry. Combinado com o timeout de 120 s, o enfermeiro pode esperar dois minutos por uma falha. Eu usaria um timeout curto (algo como 15 a 30 s), uma nova tentativa e a degradação já proposta.
12. O modelo não está fixado. llama3.1:8b é uma tag, e o conteúdo por trás dela pode mudar. temperature: 0 reduz a variação, mas não a garante entre versões do servidor. Para auditoria, registrar o digest do modelo é mais confiável que o nome.
13. A queixa_principal do mock é só os 60 primeiros caracteres do relato, cortados no meio de palavras e incluindo frases que não são queixa (“sou alérgico a dipirona”, como aparece no README). Isso mostra no JSON um dado de baixa qualidade, e o ideal é a queixa ser opcional quando o extrator não consegue resumir.
14. A duração do mock só reconhece “há/faz N unidade”. Ficam de fora “desde ontem”, “há uma semana”, “há dois dias”, “há uns 20 minutos” e “há 2h”. Só pega a primeira ocorrência, e sem avisar quando há mais de uma.
15. O origem é definido em três lugares (mock, Ollama e entrevista.py, que sobrescreve). Se o contrato disser que o extrator nunca preenche a origem, um lugar basta.
16. Extracao.sinais aceita nao_mencionado, que o contrato diz que não deve aparecer. O entrevista.py filtra, mas o tipo poderia proibir.
17. O extrator não devolve a evidência. Para o enfermeiro verificar, e para o log de auditoria, seria útil o trecho do relato que justifica cada sinal. Hoje o “porquê” não existe.
18. A lista ["mock", "ollama"] está em três lugares (criar_extrator, cli.py e relato.py). Um registro único evita divergência quando entrar um terceiro extrator.
19. O import ollama fica dentro do __init__, e um pacote ausente vira ImportError, não ErroExtracao. O relato.py captura Exception, mas o fluxo da entrevista não.
20. O host or os.environ.get("OLLAMA_HOST") é redundante, porque a biblioteca do Ollama já lê essa variável sozinha.
211. O mock não é avaliado contra o gabarito. O avaliar.py só roda Ollama, e os testes do mock foram escritos em torno do que ele faz. É uma pequena validação circular. Rodar o gabarito também sobre o mock daria uma linha de base para comparar os modelos.

### cli.py:
1. configurar_io chama reconfigure sem proteção. Se o stdout for um objeto sem esse método (por exemplo, sob alguns testes, pipes especiais ou captura do pytest com substituição de stream), vira AttributeError antes de qualquer coisa. O ideal é hasattr ou try.
2. A saída é escrita aos poucos. json.dump grava direto no stdout. Se der erro no meio (valor não serializável, pipe fechado), o consumidor recebe um JSON truncado, e o código de saída pode ainda ser 0 em alguns caminhos. O seguro é gerar a string inteira primeiro (json.dumps) e só então escrever. Isso protege o contrato “stdout é só JSON válido”.
3. BrokenPipeError não é tratado. python -m triagem f.json | head gera traceback no stderr e código de saída instável. Em uso com pipes (o uso previsto: > saida.json), vale capturar e sair limpo.
4. Erros inesperados viram traceback com código 1. Qualquer exceção fora de FichaInvalida (inclusive as já listadas) termina com o código padrão do Python, que coincide com “ficha inválida”. Quem automatizar não distingue ficha ruim de bug do sistema. Eu reservaria um código próprio (por exemplo  para erro interno e um try/except final que registre uma mensagem limpa.
5. Os erros da ficha vão por print(..., file=sys.stderr) e não pelo log. O cabeçalho sai com [ERROR] e as linhas de detalhe saem sem formato, misturando dois estilos. Quem filtrar logs por nível perde os detalhes.
6. Os erros saem só em texto. Para o front ou para automação, um --formato-erro json (ou um JSON de erro no stderr) permitiria mostrar a pergunta que falhou sem interpretar texto. É opcional para o MVP.
7. Só aceita um arquivo, sem - para ler do stdin. Para integrar com outro processo (ou testar sem criar arquivo), ficha.json igual a - seria prático.
8. Não há opção de saída. O redirecionamento > saida.json funciona, mas em Windows com PowerShell antigo grava em UTF-16 e quebra os acentos. Um --saida arquivo que escreva em UTF-8 elimina o problema, e o README já ensina o redirecionamento.
9. Não há --versao, e a saída não registra a versão do programa, só a do schema. Para auditoria, saber qual build gerou o JSON é útil.
10. A ficha pode ser enorme ou maliciosa. Não há limite de tamanho do arquivo nem de profundidade. É baixo risco num protótipo local, mas o arquivo é lido inteiro antes de qualquer checagem.
11. O except OSError mistura casos. Arquivo inexistente, sem permissão e diretório recebem a mesma mensagem genérica com o texto do sistema, que no Windows pode vir em outra codificação.
12. A ficha é validada como dict só dentro do processar_ficha. Um arquivo com [] ou "texto" chega lá e gera um erro correto, mas o código de saída fica 1 (“ficha inválida”) e não 2 (“JSON inválido”), o que é uma escolha, mas não está documentada.
13. parse_args encerra com SystemExit(2) em erro de argumento, o que está documentado no README, mas dentro de main(argv) isso atrapalha quem chama a função em testes (a exceção escapa).
14. O log.info("ficha processada...") sai sempre, mesmo em uso automatizado. Um --silencioso ou -q evita ruído, e hoje o nível é fixo em INFO.
15. O nome prog="triagem" difere do comando real (python -m triagem), então a ajuda mostra um nome que não existe.
16. A importação de criar_extrator é feita antes de saber se o extrator é válido. Funciona, mas --extrator com choices duplica a lista (já citado), e a mensagem de erro do argparse não é a do projeto.
17. Lacunas de teste: não há teste para pipe fechado, stdout não serializável, arquivo com BOM, --extrator ollama sem servidor (só no test_relato.py), nem para o formato dos erros no stde.

### relato.py:
1. configurar_io chama reconfigure sem proteção. Se o stdout for um objeto sem esse método (por exemplo, sob alguns testes, pipes especiais ou captura do pytest com substituição de stream), vira AttributeError antes de qualquer coisa. O ideal é hasattr ou try.
2. A saída é escrita aos poucos. json.dump grava direto no stdout. Se der erro no meio (valor não serializável, pipe fechado), o consumidor recebe um JSON truncado, e o código de saída pode ainda ser 0 em alguns caminhos. O seguro é gerar a string inteira primeiro (json.dumps) e só então escrever. Isso protege o contrato “stdout é só JSON válido”.
3. BrokenPipeError não é tratado. python -m triagem f.json | head gera traceback no stderr e código de saída instável. Em uso com pipes (o uso previsto: > saida.json), vale capturar e sair limpo.
4. Erros inesperados viram traceback com código 1. Qualquer exceção fora de FichaInvalida (inclusive as já listadas) termina com o código padrão do Python, que coincide com “ficha inválida”. Quem automatizar não distingue ficha ruim de bug do sistema. Eu reservaria um código próprio (por exemplo 3. para erro interno e um try/except final que registre uma mensagem limpa.
4. Os erros da ficha vão por print(..., file=sys.stderr) e não pelo log. O cabeçalho sai com [ERROR] e as linhas de detalhe saem sem formato, misturando dois estilos. Quem filtrar logs por nível perde os detalhes.
4. A validação do relato difere da do pipeline. Aqui há strip e checagem de vazio e de tamanho, e no questionario.py a checagem de tamanho vem antes do strip. Um relato de 200 caracteres com espaços no fim passa num caminho e falha no outro. O ideal é uma função única de validação do relato.
5. O relato vai como argumento de linha de comando. Ele fica visível no histórico do shell e na lista de processos. Mesmo com dados simulados, o hábito é ruim para um sistema que vai lidar com dado de saúde. Aceitar stdin (ou -) é mais seguro e permite relatos com aspas e caracteres especiais sem escape.
6. Aspas e acentos no Windows. O argumento chega pela codificação do console, e no PowerShell e no cmd isso pode corromper acentos antes do Python ver. É comum quebrar a extração (“há” virando “h?”), e o teste atual só cobre o caso em que o terminal está bem configurado.
7. load_dotenv é importado dentro da função, só depois das validações. O efeito prático é que erros de relato aparecem sem carregar o .env, o que está certo, mas o import tardio esconde a dependência. Para um ImportError do dotenv (listado em requirements.txt, mas opcional?), a falha só ocorre depois de validar.
8. O comando não mostra qual modelo foi usado. extrator sai como "ollama", sem o nome do modelo (TRIAGEM_MODELO) nem o host. Para comparar execuções, essa informação é a mais útil, e ela já está disponível no objeto.
9. Não há tempo de resposta na saída. Para um laboratório de extratores, a duração da chamada é um dado importante (e já é medido no avaliar.py). Também ajudaria a ver o efeito do timeout de 120 s.
10. A saída inclui pontuacao, o que contradiz a ideia de o comando ser só de extração. Já foi dito que o valor é enganoso, e aqui o efeito é pior: o laboratório do relato mostra pontuação 0 ao lado de “dor no peito há 2 horas”.
11. O texto do relato é repetido na saída (relato_original) e ecoado de novo na queixa_principal pelo mock. Para dado pessoal digitado pelo paciente, cada cópia é uma superfície de vazamento a mais (o ponto da LGPD).
12. O prog e a descrição não mencionam o --extrator ollama exigir servidor, e o texto da ajuda diz “dados simulados” sem lembrar de não digitar dados reais.
13. Nome da função analisar_relato recebe o extrator como string, não o objeto, e o parâmetro tem o mesmo nome do módulo e do argumento, o que confunde.
14. Não há --json-compacto nem --detalhe. Para usar em scripts de comparação, uma saída em uma linha facilita, e é opcional.
15. O if __name__ == "__main__" existe, mas o __main__.py do pacote chama o cli. Quem rodar python -m triagem relato (sem o ponto) obtém a ficha, não o relato, e o erro de argumento não explica.
16. Lacunas de teste:
    não há teste para o .env sendo lido;
    o único teste de acento depende de o terminal estar certo;
    não há teste para o relato vindo de stdin;
    o teste do Ollama indisponível aceita os dois resultados (if r.returncode != 0), então nunca falha;
    não há teste com texto em branco depois do strip e acentos combinados.

### avaliar.py: 
1. Só mede o extrator, não o sistema. O pitch fala em “erros de cor e de faixa” registrados, e o avaliar.py não toca no processar_ficha nem na pontuação. Hoje a avaliação diz se o modelo leu o texto, não se o paciente foi bem priorizado. Quando o motor existir, é preciso uma segunda avaliação ponta a ponta (ficha, cor e nota esperadas), com o mesmo princípio de gabarito separado.
2. A métrica trata todos os erros como iguais. Omitir dor num relato de dor no peito pesa o mesmo que omitir trauma. Como o erro perigoso é o que esconde gravidade (omitir sinal grave, ou trocar presente por negado), o resultado precisa de um peso ou, no mínimo, de um relatório separado de “erros que subestimam o risco”. Sem isso, um modelo com 90% de acertos pode ser pior que um com 85%.
3. O gabarito é pequeno, escrito pela própria equipe e sem revisão. São 16 relatos, 1 a 2 por sinal, o que torna cada ponto percentual instável (um caso muda a taxa em cerca de 6%). Não há separação entre casos de desenvolvimento e de teste final, e o CLAUDE.md exige que a partição de teste nunca entre em treino (ou em prompt). É preciso dividir os casos, e o conjunto final só pode ser usado uma vez por versão do prompt.
4. Falhas do modelo são ignoradas no cálculo. Em avaliar_modelo, uma resposta inválida faz continue, então os sinais esperados daquele relato somem do denominador de erros (aparecem só em falhas). Um modelo que falha em metade dos casos pode exibir “acertos” altos. Falha deve contar como omissão de todos os sinais esperados.
5. O denominador é fixo e confuso. O esperados soma os sinais de todos os 16 casos, mas os acertos vêm só dos casos que não falharam. A linha sinais: X/esperados mistura bases diferentes quando há falha.
6. Não há precisão nem revocação. Só contagens. Sem proporção de acertos sobre o que o modelo disse (precisão) e sobre o que devia ter dito (revocação), não dá para comparar modelos de forma justa, e a negação perdida (o erro mais perigoso) fica diluída.
7. Cobertura do gabarito é desigual. Faltam:
    relatos longos (perto de 200 caracteres);
    erros de digitação e gírias (“tô com a barriga doendo”);
    negações duplas e frases ambíguas;
    vários sinais no mesmo relato;
    relato vazio ou sem informação clínica (existe só “vim só para renovar a receita”).
8. Há casos com expectativa discutível. Por exemplo:
    “desmaiei no ônibus e estou tonta” espera só alteracao_consciencia e dor negado;
    “caí da escada e bati a cabeça” não espera local_dor;
    “acordei com o braço dormente” espera dor negado e nenhum sinal para o formigamento, que o vocabulário não tem.
 Quem decide o que é o certo precisa ser o revisor clínico, não só quem escreveu o caso.
9. Não é determinístico. Cada rodada chama o modelo de novo, e temperature: 0 não garante o mesmo resultado entre rodadas ou versões. Com 16 casos, o ruído pode passar da diferença entre dois modelos. Rodar N vezes e mostrar média e variação, ou salvar a saída bruta, dá mais confiança.
10. Não guarda o resultado. Tudo vai para o terminal. Sem arquivo de resultados (modelo, digest, versão do prompt, data, saída por caso), não há comparação entre execuções nem rastro de auditoria. Um --saida resultados.json resolve.
11. O prompt não é parte da avaliação. O nome do modelo é o único parâmetro, mas o resultado depende igualmente de INSTRUCOES e EXEMPLOS. Mudar o prompt e rodar de novo não deixa registro do que mudou.
12. A métrica de duração mistura casos. O duracao_ok só vale para casos com duração esperada, e a duracao_inventada só para os outros, mas elas não são somadas nem mostradas como taxa única. Também não há tolerância (“1 dia” e “24 horas” são equivalentes, mas contam como erro).
13. A alergia só compara status. Se o gabarito espera presente, basta o modelo dizer presente, mesmo com o medicamento errado ou vazio. Para o campo que o roteiro manda insistir, precisa comparar a lista de medicamentos.
14. O valor dos sinais não é avaliado. Nota da dor, temperatura e local da dor (local_dor aparece só como sinal) não têm gabarito. Para o motor de regras isso importa tanto quanto o status.
15. O gabarito é carregado na importação do módulo (GABARITO = Path(...)), mas lido só no main. Se o arquivo faltar, o erro é um traceback sem mensagem. O caminho é relativo ao pacote, então o comando falha se o pacote for instalado fora do repositório.
16. --detalhe imprime só o que errou, o que é bom, mas não mostra o que o modelo respondeu. Para depurar um erro, é preciso rodar o relato.py à parte.
17. Os modelos rodam em série e sem aquecimento. O primeiro caso de cada modelo inclui o tempo de carregar o modelo na memória, o que distorce segundos e penaliza o primeiro modelo da lista.
18. time.time() em vez de time.perf_counter(), e o tempo é total, sem média ou pior caso por relato (o que mais importa para a fila).
19. O texto do relato é impresso no terminal com --detalhe. Com dados simulados é aceitável, mas se alguém apontar o comando para dados reais, vão para o log.
20. Sem testes. O próprio avaliador, a função avaliar_relato (pura e fácil de testar) e o cálculo dos totais não têm nenhum teste. É o código que decide qual modelo usar, e um erro de contagem passa sem ninguém notar.
21. logging.getLogger("httpx") é silenciado só aqui. Se o relato.py e o cli.py usarem o mesmo cliente, os logs do httpx aparecem neles.

### Estrutura proposta: 
tests/
    conftest.py                  # ExtratorFalso,                               ficha(), citado(), sinal(), rodar_cli()
unit/
    test_schema.py
    test_vocabulario.py        # cruza NomeSinal x questionario.json
    test_questionario.py       # interpretar(), um bloco parametrizado por tipo
    test_mesclagem.py          # _mesclar_sinais (pura)
    test_pendentes.py          # _calcular_pendentes (pura)
    test_entrevista.py         # só orquestração de processar_ficha
    test_extrator_mock.py
    test_extrator_ollama.py    # com cliente falso
    test_pontuacao.py          # regras e propriedade "nunca reduz"
    test_avaliar.py
cli/
    test_cli.py                # contrato: stdout só JSON, códigos de saída
    test_relato_cli.py
exemplos/
    test_fichas_exemplo.py     # percorre exemplos/*.json
integracao/
    test_ollama_real.py        # @pytest.mark.ollama, pulado por padrão