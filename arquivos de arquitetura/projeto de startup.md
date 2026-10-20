### **SalUS.ia  — Projeto da startup**
10 de out. de 2026 

## **Visão geral**
SalUS.ai é uma startup em estágio inicial que cria um copiloto de IA para a triagem de risco em UPAs e pronto-socorros do SUS: ajuda o enfermeiro a classificar, ordena a fila entre pacientes da mesma cor e dá ao paciente um canal para avisar que piorou.

• Estágio: ideia estruturada e em validação, com protótipo em construção para o AKCIT Camp 2026 (hackathon Sudeste em 07/11/2026, em São Paulo).
• Base: Rio Paranaíba (MG), três estudantes de Ciência de Dados e Inteligência Artificial.
• Princípio central: a decisão final é sempre do profissional de saúde, e a IA nunca reduz uma pontuação.

## **Problema**
Nas urgências do SUS, a classificação de risco decide quem é atendido primeiro, e esse gargalo recai sobre poucos enfermeiros, em ambiente de sobrecarga, com perguntas repetidas e registro manual.
• Paciente de baixa renda: não tem alternativa à rede pública, fica sem previsão de atendimento e sem canal para avisar que piorou durante a espera.
• Profissional de triagem: perde tempo em tarefas repetitivas em vez de avaliar os casos mais complexos.
• Relevância: a Justiça já reconhece, em esperas por consultas, exames e cirurgias, que a demora excessiva no SUS viola o direito à saúde (TJDFT e Enunciado 93 do CNJ); na urgência, o critério é a classificação de risco, e é nela que está o gargalo.
A equipe conhece o problema por quem frequenta e trabalha nesses serviços, mas ainda não tem evidência própria medida. Reunir essa evidência é a prioridade da fase de validação.

# Solução e produto

Um agente de IA atua como copiloto do profissional de triagem, da entrevista até o acompanhamento do paciente na espera.
1. Entrevista guiada. O agente estrutura o relato livre do paciente em português, sugere as próximas perguntas e destaca sinais de alerta.
2. Pontuação. Regras clínicas explícitas, baseadas no Protocolo de Manchester, geram uma pontuação de 0 a 100 dentro de cada cor, que ordena a fila entre pacientes da mesma classificação. Ao chegar a 100, o paciente sobe de cor.
3. Fila e transparência. O paciente recebe um QR code com sua posição e uma previsão de espera em faixa, nunca um horário exato.
4. Alerta de piora. O paciente avisa por um mini-questionário; sinais graves alertam a enfermagem na hora.

## Escopo do MVP para o hackathon.
Núcleo: agente com 3 queixas comuns, motor de regras com testes, fila ordenada e avaliação com casos simulados. QR code, previsão de espera, botão de piora e senha impressa entram como extras, podendo aparecer só no vídeo de demonstração.
# Por que agente de IA e como garantir segurança?
Precisa ser um agente, e não um formulário fixo, porque entende o relato livre em português, adapta as perguntas à queixa, coordena várias etapas (extração, pontuação, fila, alertas) e acompanha o paciente durante toda a espera.
# A segurança clínica vem da arquitetura, não só do modelo:
• A pontuação vem de regras explícitas e testáveis, e nunca do modelo de linguagem. A IA interpreta o relato; o motor de regras decide o número.
• A IA nunca reduz uma pontuação. Um teste automático com muitas sequências aleatórias confirma isso a cada alteração do código.
• A decisão final é do profissional, e a tela mostra qual regra gerou cada resultado.
• Log de auditoria de cada decisão (entrada, regra aplicada, resultado).
• Tratamento de erro: se a resposta do modelo vier inválida, o sistema tenta de novo uma vez e, se falhar, mostra um erro claro em vez de adivinhar.
• Avaliação contínua: o agente roda sobre casos simulados e os erros de cor e de faixa ficam registrados.

# Mercado, clientes e modelo de negócio: 
O modelo de negócio ainda é hipótese: quem paga, o preço e o caminho de compra precisam ser validados antes de qualquer afirmação de mercado. Nenhum número de tamanho de mercado foi levantado até agora.

# Elemento

Como validar
Usuários
Enfermeiros de triagem e pacientes em UPAs e pronto-socorros
Entrevistas com enfermeiros e médicos
Quem paga
Organizações sociais de saúde, hospitais filantrópicos e secretarias de saúde
Conversas com gestores de unidades
Cobrança
Assinatura por unidade de saúde, valor ainda a definir
Comparar com custo atual de software hospitalar
Caminho de venda
Piloto em uma unidade e, depois, compra pública/particular
Entender as regras de contratação do setor público

# Diferencial
Pontuação auditável dentro de cada cor, canal de piora para o paciente e decisão sempre humana
Comparar com sistemas de triagem já usados
Primeiro passo realista: um piloto em uma unidade, com a UPA da universidade como candidata natural.

# Validação e dados: 
A fase atual valida o problema e as regras com quem trabalha na triagem, antes de qualquer teste com pacientes.
• Acesso: a equipe tem acesso à UPA da universidade e a médicos conhecidos.
• Entrevistas: duas conversas de cerca de 30 minutos, com um enfermeiro de triagem e um médico, sobre como a triagem funciona hoje, o que se repete e o que seria perigoso automatizar.
• Dados: nenhum dado de paciente. O protótipo usa casos simulados, criados pela equipe a partir das regras, e bases públicas só para testar a linguagem. Dados agregados de tempo de espera serão pedidos à UPA, se ela autorizar.
• Revisão clínica: as regras de cada queixa serão revisadas por um enfermeiro ou médico, e cada linha da tabela fica marcada como validada ou não validada.
• LGPD: dados de saúde são sensíveis; mesmo no protótipo, a equipe vai definir o que o agente coleta, onde fica armazenado e por quanto tempo.

# Limite conhecido:
casos simulados a partir das mesmas regras que o sistema aplica tendem a confirmar o próprio sistema. Por isso, a revisão por profissionais é o que dá peso real à validação.

# Riscos, regulação e ética:
Os riscos mais fortes estão na base clínica da pontuação e no enquadramento regulatório. Itens marcados com "confirmar" são pontos que a equipe ainda precisa checar com fontes oficiais.

| Risco | Por que importa | O que fazer |
| :--- | :--- | :--- |
| **Pontuação 0 a 100 própria da equipe** | O Protocolo de Manchester classifica por fluxogramas e discriminadores, sem escala numérica dentro de cada cor | Documentar a origem dos pesos e validar com revisor clínico |
| **Direitos sobre o protocolo** | O material do Manchester tem direitos autorais e licenciamento (confirmar) | Não copiar fluxogramas; confirmar com o revisor qual base a UPA usa |
| **Enquadramento na Anvisa** | Software que sugere prioridade clínica provavelmente é software como dispositivo médico (confirmar) | Levantar o caminho regulatório antes de vender |
| **Comitê de ética (CEP)** | Entrevistas com profissionais e uso de dados da UPA podem exigir aprovação (confirmar) | Perguntar à coordenação do curso antes de começar |
| **Previsão de espera errada** | Gera expectativa, conflito com a equipe e possível responsabilização | Usar faixas largas, com parâmetros marcados como hipótese |
| **Inflação de prioridades** | Como a IA nunca reduz a nota, muitos pacientes podem subir de cor e a fila perde o sentido | Medir a frequência de promoções na avaliação |
| **Acesso ao celular** | Parte do público pode ter smartphone limitado ou pouco letramento digital | Oferecer senha impressa ou painel na sala de espera |
| **Falsa segurança no aviso de piora** | O paciente pode confiar no questionário em vez de chamar a equipe | Deixar claro na página que o aviso não substitui chamar a equipe |

# Legislação e conformidade:
Esta seção reúne as normas que mais afetam o projeto. Não substitui parecer jurídico. Itens marcados com "confirmar" dependem de checagem em fonte oficial ou com a coordenação do curso.

**1. Entrevistas e ética em pesquisa (urgente)**
• Perguntar ao CEP ou à coordenação do curso se as entrevistas com o enfermeiro e o médico precisam de submissão (Resolução CNS 466/2012). A resolução manda aguardar a decisão do CEP antes de iniciar (item XI.2.a).
• Pedir a resposta por escrito e não começar as entrevistas antes dela. Se houver submissão, replanejar o cronograma (as entrevistas estão previstas até 18/10).
• Preparar o Termo de Consentimento Livre e Esclarecido (TCLE) para os profissionais, em duas vias, com os itens do IV.3. Atenção ao vínculo do entrevistado com a UPA (IV.6.b): ele precisa poder recusar sem consequência no trabalho.
• Não há TCLE de paciente nesta fase. Só haveria se houver piloto com pacientes ou conversas com eles.
• Confirmar se a Resolução CNS 510/2016 (ciências humanas e sociais) se aplica às entrevistas.

**2. Dados da UPA**
• Pedir apenas dados agregados e anonimizados de tempo de espera (LGPD, art. 12). Confirmar com a UPA como a anonimização é feita.
• Obter autorização formal da UPA e um termo de ciência e responsabilidade assinado pelo orientador ou coordenador.
• Conduzir essa etapa como atividade da universidade, separada da parte comercial do projeto. A orientação da ANPD sobre pesquisa (texto para discussão de 2022, preliminar) indica que a flexibilização acadêmica não cobre atividade comercial (confirmar se há orientação mais recente).

**3. LGPD e segurança**
• Hoje o projeto usa só dados simulados. Com dados reais, a extração do relato roda em modelo local (Ollama), em infraestrutura em território nacional. Supabase e Hugging Face ficam desativados ou restritos a dados simulados.
• Isso reduz o risco, mas não substitui: base legal, minimização dos campos da ficha, controle de acesso por perfil, criptografia, retenção e eliminação dos dados, proteção dos logs e plano de resposta a incidentes (arts. 46 e 48).
• Em uso real, a unidade de saúde seria a controladora e a startup a operadora, formalizado em contrato (arts. 5º e 39). A base natural seria a tutela da saúde (arts. 7º, VIII e 11, II, f).
• A decisão final do profissional é princípio de produto. A LGPD não garante revisão humana expressa de decisões automatizadas (art. 20), então isso não deve ser apresentado como obrigação legal.
• Confirmar: o que o Ollama registra em disco, qual região o Supabase usa e o prazo atual de comunicação de incidentes à ANPD.

**4. Modelo de negócio**
• A receita vem da assinatura pelo serviço, nunca da venda ou do compartilhamento de dados de pacientes (art. 11, § 4º da LGPD veda o uso compartilhado de dados de saúde com objetivo de vantagem econômica, com exceções).
• Qualquer uso secundário dos dados, como treino de modelos ou indicadores para terceiros, só após validação jurídica e com anonimização real.

**5. Regulação do produto**
• Anvisa: software que sugere prioridade clínica provavelmente é software como dispositivo médico (RDC 657/2022 e 751/2022; a 657 está em revisão). Levantar o caminho regulatório antes de oferecer o produto a uma unidade.
• Resolução CFM 2.454/2026: a responsabilidade final é sempre do médico. Alinhar a linguagem do pitch.
• Resolução Cofen 423/2012, sobre classificação de risco pelo enfermeiro (confirmar o texto).
• PL 2.338/2023 (marco legal da IA) ainda tramita na Câmara. Acompanhar.

**6. Protocolo de Manchester**
• Não copiar fluxogramas nem discriminadores. Usar regras próprias, validadas pelo revisor clínico, com a origem de cada peso documentada.

# O plano detalhado de tarefas por pessoa está no documento "SalUS.ai — Plano de atividades até o hackathon (07/11)". Em resumo:
1. Semana de 05/10 (em andamento): inscrição enviada, repositório, primeiro agente rodando e entrevistas pedidas.
2. Até 18/10: duas entrevistas feitas, agente com 1 queixa e segundo relatório quinzenal do programa.
3. Até 25/10: motor de regras com testes, regras das 3 queixas enviadas a um revisor clínico e 30 casos simulados.
4. Até 01/11: fluxo ponta a ponta em demo gravada, avaliação do agente, BMC com hipótese de preço e terceiro relatório quinzenal.
5. Até 06/11: versão congelada, documentação do fluxo, pitch ensaiado e viagem confirmada.
6. 07/11: hackathon Sudeste em São Paulo; congelamento das entregas no GitHub às 15h30. Só a equipe vencedora de cada região vai à final.
7. 28/11: final nacional no Cubo Itaú, em São Paulo, se vencerem a etapa regional.
Depois do programa: fechar o piloto em uma unidade de saúde, confirmar o enquadramento regulatório e definir preço e comprador com base nas entrevistas.