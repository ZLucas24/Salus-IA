# SalUS.ai — Resumo do projeto e pontos de atenção

Oct 7, 2026 · @Ryan

## Resumo do projeto

SalUS.ai é um agente de IA que atua como copiloto do profissional de triagem em UPAs e prontos-socorros do SUS. A equipe o inscreveu no AKCIT Camp 2026 (região Sudeste); o hackathon presencial é em São Paulo, em 07/11/2026, e o prazo da inscrição é 31/10/2026.

**Problema.** A classificação de risco, que define quem é atendido primeiro, recai sobre poucos enfermeiros sobrecarregados, com perguntas repetidas e registro manual. O paciente de baixa renda não tem alternativa à rede pública, fica sem previsão de atendimento e sem canal para avisar que piorou.

**Solução.**

- Durante a entrevista, o agente estrutura o relato do paciente em português e sugere perguntas e sinais de alerta.
- Calcula uma pontuação de 0 a 100 dentro de cada cor, com regras clínicas explícitas baseadas no Protocolo de Manchester, para ordenar a fila entre pacientes da mesma classificação. Ao chegar a 100, o paciente sobe de cor.
- O paciente recebe um QR code com sua posição e uma previsão de espera em faixa, e pode avisar que piorou por um mini-questionário. Sinais graves alertam a enfermagem na hora.
- A decisão final é do profissional, e a IA nunca reduz a pontuação.
- Por que agente e não formulário fixo: entende relato livre, adapta as perguntas à queixa, coordena várias etapas e acompanha o paciente durante toda a espera.

**Estágio de validação.** Acesso à UPA da universidade e a médicos conhecidos da equipe. Pretendem entrevistar enfermeiros e médicos, levantar dados agregados de tempo de espera e usar dados simulados e bases públicas, sem dados de pacientes.

**Lacunas declaradas.**

- Técnico: cobrir as queixas do protocolo com regras revisadas clinicamente, extrair sintomas de relatos em português e medir a qualidade do agente.
- Validação: dados reais de triagem são escassos e sensíveis (LGPD).
- Negócio: definir quem paga (organizações sociais, hospitais filantrópicos, secretarias de saúde), preço, caminho de compra pública e enquadramento regulatório.

**Papel do AKCIT Camp.** Cursos e workshops (RAG, orquestração, avaliação e segurança de agentes, LGPD), mentoria para modelo de negócio e caminho regulatório, e rede de parceiros e investidores para chegar a um piloto.

**Histórico da equipe.** Lucas criou e vendeu um site de pedidos para uma loja de delivery. Larissa iniciou uma pesquisa sobre a queda da vacinação infantil, não concluída. Anna construiu um coletor diário de cotações de café, trocando Selenium e OCR por requisições diretas.

## Pontos negativos: a ideia

Os riscos mais fortes estão na base clínica da pontuação e na forma de validar o sistema.

1. **A pontuação 0–100 é invenção da equipe.** O Protocolo de Manchester classifica por fluxogramas e discriminadores, sem escala numérica dentro de cada cor. Um avaliador clínico vai perguntar de onde vêm os pesos, como "ao chegar a 100, sobe de cor" se justifica clinicamente e quem validou. Preparem uma resposta objetiva.
2. **Validação circular.** Dados simulados criados pela equipe a partir das mesmas regras que o sistema aplica tendem a confirmar o próprio sistema. Isso mede se o código segue as regras, não se as regras são boas. A revisão por profissionais é o que dá peso real.
3. **Direitos sobre o protocolo.** Pelo que sei, o Manchester tem material com direitos autorais e licenciamento no Brasil. Vale confirmar se e como é possível implementá-lo sem problema.
4. **Previsão de tempo e QR code.** Uma faixa de espera errada gera expectativa, conflito com a equipe e possível responsabilização. O mini-questionário de "piorei" pode dar falsa sensação de segurança, e o público de baixa renda pode ter acesso limitado a smartphone e letramento digital. Considerem alternativas, como totem ou painel.
5. **"A IA nunca reduz a pontuação" tem efeito colateral.** É bom para segurança, mas tende a inflar prioridades. Se muitos pacientes sobem de cor, a fila perde o sentido. Será preciso medir isso.

## Pontos de atenção: equipe, regulação e ética

A equipe não tem perfil clínico, e o produto toca em regulação de saúde e em dados sensíveis.

**Equipe**

- Ninguém tem perfil clínico, e os médicos "conhecidos" são um acesso informal. Um aliado formal (enfermeiro de triagem ou professor da área da saúde) como conselheiro fortaleceria muito a proposta.
- Nenhum projeto citado envolve agentes de IA nem saúde. Um avaliador pode duvidar da viabilidade técnica, e a melhor resposta é mostrar um protótipo, mesmo simples.

**Regulação e ética**

- Software que sugere prioridade clínica provavelmente se enquadra como software como dispositivo médico (SaMD) na Anvisa. Confirmem, porque isso afeta prazos e o caminho de venda.
- Entrevistar profissionais e usar dados da UPA da universidade pode exigir passar por comitê de ética (CEP), mesmo com dados agregados. Descubram antes de começar.
- Dados de saúde são sensíveis pela LGPD. Mesmo no protótipo, definam desde já o que o agente coleta, onde fica armazenado e por quanto tempo.

## Atenções para o hackathon e para a inscrição enviada

**Hackathon**

- Não tentem demonstrar tudo. Um recorte funcional (uma ou duas queixas, a pontuação e a fila) convence mais do que o sistema inteiro apresentado só em slides.
- O caminho de compra pública é lento. Tenham uma resposta curta e realista: um piloto em uma unidade como primeiro passo.
