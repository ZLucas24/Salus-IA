'use strict';
/* Interface do Salus IA. Tudo é montado com DOM seguro (sem innerHTML).
   O formulário nasce do /api/questionario; o resultado vem do fluxo real em /api/triagem. */

const ROTULOS = {
  de_repente: 'De repente', aos_poucos: 'Aos poucos', igual: 'Igual', melhorando: 'Melhorando',
  piorando: 'Piorando', queimacao: 'Queimação', aperto: 'Aperto', pontada: 'Pontada', colica: 'Cólica',
  outro: 'Outro', outra: 'Outra', medicamento: 'Medicamento', alimento: 'Alimento', contraste: 'Contraste',
  antitermico: 'Antitérmico', analgesico: 'Analgésico', diabetes: 'Diabetes', hipertensao: 'Hipertensão',
  cardiopatia: 'Coração', pneumopatia: 'Pulmão', renopatia: 'Rim', cirurgia: 'Cirurgia',
  internacao: 'Internação', transfusao: 'Transfusão', parte_superior: 'Parte de cima',
  parte_inferior_direita: 'Embaixo, à direita', parte_inferior_esquerda: 'Embaixo, à esquerda',
  ao_redor_do_umbigo: 'Ao redor do umbigo', toda_a_barriga: 'Toda a barriga', minutos: 'minutos',
  horas: 'horas', dias: 'dias', semanas: 'semanas', meses: 'meses', anos: 'anos',
  feminino: 'Feminino', masculino: 'Masculino', intersexo: 'Intersexo', ausente: 'Não informado',
  nao_sabe: 'Não sabe', recusou: 'Recusou', nao_se_aplica: 'Não se aplica',
};
const PARTES = {
  inicio: 'Como começou', duracao: 'Há quanto tempo', para_onde: 'Para onde vai', tipos: 'Tipo de alergia',
  texto: 'Quais (nomes)', anticoagulante: 'Usa remédio para afinar o sangue', insulina: 'Usa insulina',
  classes: 'Tipo de remédio', ha: 'Há quanto tempo tomou', gravida_possivel: 'Chance de estar grávida',
  amamentando: 'Está amamentando', menstruacao_atrasada: 'Menstruação atrasada', local: 'Onde dói',
  mudou_de_lugar: 'A dor mudou de lugar', vomitando: 'Está vomitando', episodios: 'Quantos episódios',
  sangue_vomito_ou_fezes: 'Sangue no vômito ou nas fezes', gases_e_evacuando: 'Solta gases e evacua',
  diarreia: 'Tem diarreia', febre: 'Sentiu febre', maior_temperatura: 'Maior temperatura medida (°C)',
  calafrios: 'Calafrios', chiado: 'Chiado no peito', tosse_com_sangue: 'Tosse com sangue',
  resposta: 'Resposta',
};
const SINAIS = {
  inicio_subito: 'Início súbito', piora_progressiva: 'Piora progressiva', dor_em_aperto: 'Dor em aperto',
  dor: 'Dor', irradiacao: 'Irradiação', alteracao_consciencia: 'Alteração de consciência',
  dispneia: 'Falta de ar', uso_anticoagulante: 'Usa anticoagulante', uso_insulina: 'Usa insulina',
  antitermico_recente: 'Antitérmico recente', doenca_cronica: 'Doença crônica',
  cirurgia_internacao_previa: 'Cirurgia ou internação prévia', gravidez_possivel: 'Gravidez possível',
  amamentando: 'Amamentando', suor_frio_enjoo_tontura: 'Suor frio, enjoo ou tontura',
  dor_piora_esforco_respirar: 'Dor piora ao esforço ou respirar', risco_tromboembolico: 'Risco tromboembólico',
  dor_abdominal: 'Dor abdominal', dor_migratoria: 'Dor migratória', vomito: 'Vômito',
  sangue_vomito_fezes: 'Sangue no vômito ou nas fezes', sem_gases_evacuacao: 'Sem gases ou evacuação',
  diarreia: 'Diarreia', abdome_rigido_distendido: 'Abdome rígido ou distendido',
  alteracao_urinaria: 'Alteração urinária', febre_referida: 'Febre referida', calafrios: 'Calafrios',
  fala_entrecortada: 'Fala entrecortada', chiado: 'Chiado no peito', tosse_com_sangue: 'Tosse com sangue',
  contato_ou_viagem: 'Contato com doente ou viagem', dificuldade_beber: 'Dificuldade para beber',
  febre_atual: 'Febre (aferida)', hipoxemia: 'Saturação baixa', taquicardia: 'Taquicardia',
  taquipneia: 'Taquipneia', hipotensao: 'Hipotensão', glicemia_alterada: 'Glicemia alterada',
  glasgow_reduzido: 'Glasgow reduzido',
};
const STATUS = {
  presente: 'Presente', negado: 'Negado', nao_mencionado: 'Não mencionado', nao_sabe: 'Não sabe',
  recusou: 'Recusou', nao_se_aplica: 'Não se aplica', incerto: 'Incerto',
};
const ORIGEM = {
  resposta_direta: 'Resposta direta', extraido_do_relato: 'Do relato',
  medido_pelo_atendente: 'Aferição', nenhuma: 'Sem fonte',
};
const ALERTAS = {
  sinal_de_alerta: ['Sinal de alerta', 'grave'], divergencia: ['Relato e resposta divergem', 'atencao'],
  extracao_falhou: ['Falha ao ler o relato', 'atencao'], extracao_avisos: ['Avisos da leitura do relato', 'info'],
  dado_incompleto: ['Resposta incompleta', 'atencao'], dado_desconhecido: ['Pergunta de segurança sem resposta', 'atencao'],
  duracao_divergente: ['Duração divergente', 'atencao'], alergia_divergente: ['Alergia divergente', 'atencao'],
  febre_mascarada: ['Febre possivelmente mascarada', 'atencao'], febre_nao_referida: ['Febre não referida', 'atencao'],
  limites_pediatricos: ['Limites pediátricos', 'info'], sem_modulo: ['Nenhum módulo identificado', 'info'],
  afericao_faltando: ['Aferição não registrada', 'info'],
};
const QUEIXAS = {
  dor_toracica: 'Dor no peito', dor_abdominal: 'Dor abdominal', respiratorio_febre: 'Respiratório ou febre',
  outra: 'Outra queixa', indefinida: 'Queixa indefinida',
};
const MARCADORES = ['nao_sabe', 'recusou', 'nao_se_aplica'];
const CADASTRO = [
  ['idade', 'Idade (anos)', 'inteiro', true], ['sexo_biologico', 'Sexo biológico', 'sexo'],
  ['temperatura', 'Temperatura (°C)', 'numero'], ['saturacao', 'Saturação (%)', 'numero'],
  ['pressao_sistolica', 'Pressão sistólica (mmHg)', 'numero'], ['pressao_diastolica', 'Pressão diastólica (mmHg)', 'numero'],
  ['frequencia_cardiaca', 'Freq. cardíaca (bpm)', 'numero'], ['frequencia_respiratoria', 'Freq. respiratória (irpm)', 'numero'],
  ['glicemia', 'Glicemia (mg/dL)', 'numero'], ['glasgow', 'Glasgow (3 a 15)', 'inteiro'],
];

// sessão expirada ou ausente: qualquer resposta 401 manda para a tela de login
const fetchOriginal = window.fetch.bind(window);
window.fetch = async (...args) => {
  const r = await fetchOriginal(...args);
  if (r.status === 401) window.location.href = '/login';
  return r;
};

const humanizar = (s) => { const t = String(s).replace(/_/g, ' '); return t.charAt(0).toUpperCase() + t.slice(1); };
const rotulo = (v) => ROTULOS[v] ?? humanizar(v);
const nomeSinal = (n) => SINAIS[n] ?? humanizar(n);

function h(tag, props = {}, ...filhos) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (v === undefined || v === null || v === false) continue;
    if (k === 'class') el.className = v;
    else if (k === 'texto') el.textContent = v;
    else if (k.startsWith('on')) el.addEventListener(k.slice(2), v);
    // estilo pelo CSSOM: a CSP (style-src 'self') bloqueia o atributo style="" e a barra ficava cheia
    else if (k === 'style') el.style.cssText = v;
    else el.setAttribute(k, v === true ? '' : v);
  }
  for (const f of filhos.flat()) if (f !== null && f !== undefined && f !== false) el.append(f);
  return el;
}
const $ = (s) => document.querySelector(s);

/* ---------------------------------------------------------------- widgets */
// Cada widget: { el, get(), set(v) }. `mudou()` avisa a página que algo foi digitado.

function numeroOuUndefined(texto, inteiro) {
  if (texto === '' || texto == null) return undefined;
  const n = Number(texto.replace(',', '.'));
  if (Number.isNaN(n)) return undefined;
  return inteiro ? Math.trunc(n) : n;
}

function wSimNao(mudou) {
  const alvos = [[true, 'Sim'], [false, 'Não'], ['nao_sabe', 'Não sabe'], ['recusou', 'Recusou']];
  let valor;
  const botoes = alvos.map(([v, t]) => h('button', {
    type: 'button', class: 'opcao' + (typeof v === 'string' ? ' marcador' : ''), 'aria-pressed': 'false', texto: t,
    onclick() { valor = valor === v ? undefined : v; pintar(); mudou(); },
  }));
  const pintar = () => botoes.forEach((b, i) => b.setAttribute('aria-pressed', String(alvos[i][0] === valor)));
  return { el: h('div', { class: 'opcoes', role: 'group' }, botoes), get: () => valor, set(v) { valor = v ?? undefined; pintar(); } };
}

function wNumero(parte, mudou, inteiro) {
  const input = h('input', { type: 'number', step: inteiro ? '1' : 'any', min: parte.minimo, max: parte.maximo, oninput: mudou });
  return {
    el: input, get: () => numeroOuUndefined(input.value, inteiro),
    set(v) { input.value = typeof v === 'number' ? String(v) : ''; },
  };
}

function wOpcao(parte, mudou) {
  const sel = h('select', { onchange: mudou }, h('option', { value: '', texto: 'Escolher…' }),
    parte.opcoes.map((o) => h('option', { value: o, texto: rotulo(o) })));
  return { el: sel, get: () => sel.value || undefined, set(v) { sel.value = parte.opcoes.includes(v) ? v : ''; } };
}

function wMultiplas(parte, mudou) {
  let escolhidos = new Set(), nenhuma = false;
  const pintar = () => {
    botoes.forEach((b, i) => b.setAttribute('aria-pressed', String(escolhidos.has(parte.opcoes[i]))));
    btnNenhuma.setAttribute('aria-pressed', String(nenhuma));
  };
  const botoes = parte.opcoes.map((o) => h('button', {
    type: 'button', class: 'opcao', 'aria-pressed': 'false', texto: rotulo(o),
    onclick() { nenhuma = false; escolhidos.has(o) ? escolhidos.delete(o) : escolhidos.add(o); pintar(); mudou(); },
  }));
  const btnNenhuma = h('button', {
    type: 'button', class: 'opcao', 'aria-pressed': 'false', texto: 'Nenhuma',
    onclick() { nenhuma = !nenhuma; escolhidos = new Set(); pintar(); mudou(); },
  });
  return {
    el: h('div', { class: 'opcoes', role: 'group' }, botoes, btnNenhuma),
    get: () => (nenhuma ? [] : escolhidos.size ? parte.opcoes.filter((o) => escolhidos.has(o)) : undefined),
    set(v) { escolhidos = new Set(Array.isArray(v) ? v : []); nenhuma = Array.isArray(v) && v.length === 0; pintar(); },
  };
}

function wTexto(parte, mudou) {
  const input = h('input', { type: 'text', maxlength: parte.max_caracteres ?? 200, oninput: mudou, autocomplete: 'off' });
  return { el: input, get: () => input.value.trim() || undefined, set(v) { input.value = typeof v === 'string' ? v : ''; } };
}

function wNumeroUnidade(parte, mudou) {
  const num = h('input', { type: 'number', step: 'any', min: '0', oninput: mudou, 'aria-label': 'Valor' });
  const sel = h('select', { onchange: mudou, 'aria-label': 'Unidade' }, parte.unidades.map((u) => h('option', { value: u, texto: u })));
  return {
    el: h('div', { class: 'duplo' }, num, sel),
    get() { const v = numeroOuUndefined(num.value, false); return v === undefined ? undefined : { valor: v, unidade: sel.value }; },
    set(v) { num.value = v && typeof v === 'object' ? String(v.valor) : ''; sel.value = v && v.unidade ? v.unidade : parte.unidades[0]; },
  };
}

function criarWidget(parte, mudou) {
  switch (parte.forma) {
    case 'sim_nao': return wSimNao(mudou);
    case 'escala': return wNumero(parte, mudou, true);
    case 'numero': return wNumero(parte, mudou, false);
    case 'opcao': return wOpcao(parte, mudou);
    case 'multiplas': return wMultiplas(parte, mudou);
    case 'numero_unidade': return wNumeroUnidade(parte, mudou);
    default: return wTexto(parte, mudou);
  }
}

/* ---------------------------------------------------------------- pergunta */

function criarPergunta(p, mudou) {
  const simples = p.partes.length === 1 && p.partes[0].nome === 'resposta';
  let marcador;
  const itens = p.partes.map((parte) => {
    let bruto; // valor que o widget não sabe mostrar (ex.: marcador numa parte); mantido até o usuário mexer
    const w = criarWidget(parte, () => { bruto = undefined; mudou(); });
    const dep = parte.depende_de;
    const cont = h('div', { class: 'parte', 'data-parte': parte.nome },
      simples ? null : h('span', { class: 'rotulo', texto: (PARTES[parte.nome] ?? humanizar(parte.nome)) + (dep ? ` (só se "${PARTES[dep.parte] ?? dep.parte}" = ${dep.igual ? 'sim' : 'não'})` : '') }),
      w.el);
    return {
      parte, cont,
      get: () => (bruto !== undefined ? bruto : w.get()),
      set(v) {
        if (typeof v === 'string' && MARCADORES.includes(v) && parte.forma !== 'sim_nao') { bruto = v; w.set(undefined); } else { bruto = undefined; w.set(v); }
      },
    };
  });

  const marcadores = h('div', { class: 'marcadores' }, MARCADORES.map((m) => h('button', {
    type: 'button', class: 'opcao marcador', 'aria-pressed': 'false', texto: rotulo(m), 'data-marcador': m,
    onclick() { marcador = marcador === m ? undefined : m; pintar(); mudou(); },
  })));
  const selo = h('span', { class: 'selo-estado', hidden: true });
  const nota = h('p', { class: 'aviso-n-a', hidden: true, texto: 'Não se aplica a este paciente (pelo cadastro).' });
  const el = h('article', { class: 'pergunta', id: `pergunta-${p.id}` },
    h('header', {}, h('span', { class: 'id', texto: p.id }),
      h('div', {}, h('p', { class: 'texto', texto: p.texto }), h('p', { class: 'finalidade', texto: p.finalidade })), selo),
    nota, h('div', { class: 'partes' }, itens.map((i) => i.cont)), marcadores);

  function pintar() {
    el.classList.toggle('com-marcador', marcador !== undefined);
    marcadores.querySelectorAll('button').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.marcador === marcador)));
  }
  return {
    id: p.id, el, selo, nota, simples,
    partes: Object.fromEntries(itens.map((i) => [i.parte.nome, i])),
    temMarcador: () => marcador !== undefined,
    get() {
      if (marcador) return marcador;
      if (simples) return itens[0].get();
      const o = {};
      for (const i of itens) { const v = i.get(); if (v !== undefined) o[i.parte.nome] = v; }
      return Object.keys(o).length ? o : undefined;
    },
    set(v) {
      marcador = typeof v === 'string' && MARCADORES.includes(v) ? v : undefined;
      if (marcador) itens.forEach((i) => i.set(undefined));
      else if (simples) itens[0].set(v);
      else itens.forEach((i) => i.set(v && typeof v === 'object' ? v[i.parte.nome] : undefined));
      pintar();
    },
  };
}

/* ---------------------------------------------------------------- estado da página */
// A triagem tem 3 passos: 1) preencher a ficha, 2) analisar (cor, alertas, histórico) e
// 3) colocar na fila. A cor e a pontuação só aparecem no passo 2; o botão da fila, só depois dele.

const estado = {
  dados: null, exemplos: [], campos: {}, perguntas: {}, modulos: {}, seq: 0, seqAnalise: 0, timer: null,
  saida: null, erros: null, analisando: false, enviando: false, passo: 'ficha', rolagemFicha: 0, pedeIdade: false, reclassificando: null,
  historico: { prontuario: '', dados: null, padroes: null, situacao: 'vazio', seq: 0, timer: null },
};

function construirCadastro() {
  const campos = CADASTRO.map(([nome, texto, tipo, obrig]) => {
    let w;
    if (tipo === 'sexo') {
      const sel = h('select', { onchange: agendar }, h('option', { value: '', texto: 'Não informado' }),
        ['feminino', 'masculino', 'intersexo', 'ausente'].map((o) => h('option', { value: o, texto: rotulo(o) })));
      w = { el: sel, get: () => sel.value || undefined, set(v) { sel.value = v || ''; } };
    } else {
      w = wNumero({ minimo: 0 }, agendar, tipo === 'inteiro');
    }
    estado.campos[nome] = w;
    const dica = nome === 'idade' ? null : h('small', { texto: 'em branco = não aferido' });
    return h('label', { class: 'campo' }, h('span', { class: obrig ? 'obrig' : '', texto: texto }), w.el, nome === 'sexo_biologico' ? h('small', { texto: 'decide a pergunta de gravidez' }) : dica);
  });
  const blocos = [h('h2', { texto: 'Cadastro e aferições' })];
  if (estado.dados.historico.ligado) {
    // o prontuário não entra na ficha: serve só para consultar o histórico
    const input = h('input', { type: 'text', id: 'prontuario', inputmode: 'numeric', maxlength: '12', autocomplete: 'off', placeholder: 'só números', oninput: prontuarioDigitado });
    input.addEventListener('keydown', (ev) => { if (ev.key === 'Enter') { ev.preventDefault(); buscarHistorico(); } });
    blocos.push(h('div', { class: 'linha-prontuario' },
      h('label', { class: 'campo' }, h('span', { texto: 'Prontuário (opcional)' }), input),
      h('button', { type: 'button', class: 'pilula secundaria', texto: 'Buscar histórico', onclick: () => buscarHistorico() }),
      h('a', { class: 'dica', id: 'prontuario-situacao', href: '#historico' })));
  }
  blocos.push(h('p', { class: 'dica', texto: 'Só a idade é obrigatória. Aferição não feita fica em branco e nunca vale como normal.' }),
    h('div', { class: 'grade' }, campos));
  $('#cadastro').replaceChildren(h('section', { class: 'cartao' }, blocos));
}

function construirPerguntas(q) {
  const por = (ob) => q.perguntas.filter((p) => p.obrigatoriedade === ob);
  const criar = (p) => { const c = criarPergunta(p, agendar); estado.perguntas[p.id] = c; return c.el; };
  const grupo = (titulo, lista) => h('section', { class: 'grupo' }, h('h3', { texto: titulo }), lista.map(criar));
  const nucleo = por('N');
  const secoes = [
    grupo('Relato', nucleo.filter((p) => p.id === 'Q01')),
    grupo('Segurança (nunca pular por suposição)', por('S')),
    grupo('Núcleo', nucleo.filter((p) => p.id !== 'Q01')),
  ];
  for (const [chave, nome] of Object.entries(q.modulos)) {
    const lista = por('M').filter((p) => p.modulo === chave);
    const ativo = h('span', { class: 'chip', hidden: true, texto: 'ativo' });
    const det = h('details', { class: 'modulo' }, h('summary', {}, `Módulo: ${nome}`, ativo, h('span', { class: 'chip neutro', texto: `${lista.length} perguntas` })),
      h('div', { class: 'corpo' }, lista.map(criar)));
    estado.modulos[chave] = { det, ativo };
    secoes.push(det);
  }
  const comp = por('C');
  secoes.push(h('details', { class: 'modulo' }, h('summary', {}, 'Complementares', h('span', { class: 'chip neutro', texto: 'para o médico, não entram na pontuação' })),
    h('div', { class: 'corpo' }, comp.map(criar))));
  $('#perguntas').replaceChildren(...secoes);
}

function lerFicha() {
  const dados = {};
  for (const [nome, w] of Object.entries(estado.campos)) { const v = w.get(); if (v !== undefined) dados[nome] = v; }
  const respostas = {};
  for (const [id, c] of Object.entries(estado.perguntas)) { const v = c.get(); if (v !== undefined) respostas[id] = v; }
  return { dados_atendente: dados, respostas };
}

function preencher(ficha) {
  const d = (ficha && ficha.dados_atendente) || {}, r = (ficha && ficha.respostas) || {};
  for (const [nome, w] of Object.entries(estado.campos)) w.set(d[nome]);
  for (const [id, c] of Object.entries(estado.perguntas)) c.set(r[id]);
}

/* ---------------------------------------------------------------- histórico do paciente */
// O prontuário vai à parte da ficha, só para consultar o histórico; não é guardado na fila nem
// na base de treino. O cruzamento é feito no servidor, por regra em código: informa a equipe,
// não é diagnóstico e não muda a cor nem a pontuação.

const PADROES = {
  retorno_precoce: 'Retorno em pouco tempo', retorno_frequente: 'Vindas repetidas',
  queixa_repetida: 'Mesma queixa de antes', alergia_no_historico: 'Alergia registrada',
  historico_diverge_da_ficha: 'Histórico e ficha divergem',
};
const dataBR = (iso) => String(iso).split('-').reverse().join('/');
const haDias = (d) => (d === 0 ? 'hoje' : d === 1 ? 'ontem' : `há ${d} dias`);

function prontuarioDigitado() {
  const hst = estado.historico;
  clearTimeout(hst.timer);
  const valor = $('#prontuario').value.trim();
  if (valor === '') { limparHistorico(); return; }
  if (valor === hst.prontuario && hst.dados) return;
  hst.timer = setTimeout(() => buscarHistorico(), 600); // busca sozinho quando a digitação para
}

function limparHistorico() {
  const hst = estado.historico;
  clearTimeout(hst.timer);
  hst.seq += 1; // descarta uma busca em andamento
  Object.assign(hst, { prontuario: '', dados: null, padroes: null, situacao: 'vazio' });
  const campo = $('#prontuario');
  if (campo) campo.value = '';
  renderHistorico();
}

// `cruzar`: depois de achar o histórico, recalcula para cruzar com a ficha (só no passo 1;
// no "Analisar" quem cruza é a própria análise).
async function buscarHistorico(cruzar = true) {
  const hst = estado.historico;
  const campo = $('#prontuario');
  if (!campo) return;
  clearTimeout(hst.timer);
  const valor = campo.value.trim();
  if (valor === '') { limparHistorico(); return; }
  const minha = ++hst.seq;
  Object.assign(hst, { prontuario: '', dados: null, padroes: null, situacao: 'buscando' });
  if (!/^[0-9]{4,12}$/.test(valor)) { hst.situacao = 'invalido'; renderHistorico(); return; }
  renderHistorico();
  let situacao = 'erro', dados = null;
  try {
    const { status, corpo } = await postar('/api/historico', { prontuario: valor });
    if (status === 200) { situacao = 'ok'; dados = corpo; }
    else if (status === 404) situacao = 'nao_encontrado';
    else if (status === 400) situacao = 'invalido';
  } catch (e) { /* fica como 'erro': a triagem segue sem histórico */ }
  if (minha !== hst.seq) return;
  Object.assign(hst, { prontuario: dados ? valor : '', dados, padroes: null, situacao });
  renderHistorico();
  if (dados && cruzar !== false && estado.passo === 'ficha') calcular(); // cruza já com o que estiver preenchido
}

function listaDePadroes(padroes) {
  return h('ul', { class: 'alertas' }, padroes.map((p) => h('li', { class: `alerta ${p.nivel}` },
    h('span', { class: 'cod', texto: PADROES[p.codigo] ?? humanizar(p.codigo) }), h('span', { texto: p.mensagem }))));
}

function corpoDoHistorico(hst) {
  const d = hst.dados, filhos = [];
  const quem = [`Prontuário ${d.prontuario}`];
  if (typeof d.idade === 'number') quem.push(`${d.idade} anos`);
  if (d.sexo_biologico) quem.push(rotulo(d.sexo_biologico).toLowerCase());
  filhos.push(h('p', { class: 'hist-quem', texto: quem.join(' · ') }));
  const idadeFicha = estado.campos.idade.get();
  if (idadeFicha !== undefined && typeof d.idade === 'number' && Math.abs(idadeFicha - d.idade) > 1) {
    filhos.push(h('p', { class: 'alerta atencao', texto: `A idade da ficha (${idadeFicha}) é diferente da registrada no histórico (${d.idade}). Confira se o prontuário é deste paciente.` }));
  }
  filhos.push(h('p', { class: 'rotulo-secao', texto: 'Cruzamento com a ficha de hoje' }));
  if (hst.padroes === null) filhos.push(h('p', { class: 'dica', texto: 'Preencha a idade para cruzar o histórico com a ficha.' }));
  else if (!hst.padroes.length) filhos.push(h('p', { class: 'dica', texto: 'Nenhum padrão com a ficha de hoje até agora.' }));
  else filhos.push(listaDePadroes(hst.padroes));
  const fato = (titulo, itens, classe) => h('div', { class: 'hist-fato' }, h('span', { class: 'rotulo', texto: titulo }),
    itens.length ? h('div', { class: 'chips' }, itens.map((i) => h('span', { class: `chip ${classe}`, texto: i })))
      : h('span', { class: 'dica', texto: 'nenhum registro' }));
  filhos.push(fato('Alergias registradas', d.alergias, 'perigo'), fato('Condições', d.condicoes, 'neutro'), fato('Remédios em uso', d.medicamentos, 'neutro'));
  filhos.push(h('p', { class: 'rotulo-secao', texto: `Atendimentos anteriores (${d.atendimentos.length})` }));
  filhos.push(d.atendimentos.length
    ? h('ul', { class: 'hist-lista' }, d.atendimentos.map((a) => h('li', {},
      h('div', { class: 'hist-linha' }, h('span', { class: `cor-chip cor-${a.cor}`, texto: CORES[a.cor] ?? a.cor }),
        h('strong', { texto: a.descricao }), h('span', { class: 'dica', texto: `${dataBR(a.data)} · ${haDias(a.ha_dias)}` })),
      (a.diagnostico || a.desfecho) ? h('p', { class: 'dica', texto: [a.diagnostico ? `Diagnóstico registrado: ${a.diagnostico}` : null, a.desfecho ? `Desfecho: ${a.desfecho}` : null].filter(Boolean).join(' · ') }) : null)))
    : h('p', { class: 'dica', texto: 'Nenhum atendimento anterior registrado.' }));
  filhos.push(h('p', { class: 'dica', texto: 'O histórico informa a equipe. Não é diagnóstico e não muda a cor nem a pontuação.' }));
  return filhos;
}

function renderHistorico() {
  const caixa = $('#historico');
  if (!caixa || !estado.dados) return;
  if (!estado.dados.historico.ligado) { caixa.hidden = true; return; }
  caixa.hidden = false;
  const hst = estado.historico;
  const filhos = [h('div', { class: 'controles entre' }, h('h2', { id: 'titulo-historico', texto: 'Histórico do paciente' }),
    hst.dados && hst.dados.simulado ? h('span', { class: 'selo', texto: 'dados simulados' }) : null)];
  let resumo = '';
  if (hst.situacao === 'ok') {
    filhos.push(...corpoDoHistorico(hst));
    const n = hst.dados.atendimentos.length, avisos = hst.padroes ? hst.padroes.length : 0;
    resumo = `${n === 1 ? '1 atendimento anterior' : `${n} atendimentos anteriores`}${avisos ? ` · ${avisos === 1 ? '1 aviso' : `${avisos} avisos`}` : ''} · ver histórico`;
  } else if (hst.situacao === 'buscando') {
    filhos.push(h('p', { class: 'dica', texto: 'Buscando o histórico…' }));
    resumo = 'Buscando…';
  } else if (hst.situacao === 'invalido') {
    filhos.push(h('p', { class: 'alerta atencao', texto: 'Prontuário inválido: use de 4 a 12 dígitos, só números.' }));
    resumo = 'Prontuário inválido';
  } else if (hst.situacao === 'nao_encontrado') {
    filhos.push(h('p', { class: 'alerta info', texto: 'Prontuário não encontrado. A triagem segue normalmente, sem histórico.' }));
    resumo = 'Prontuário não encontrado';
  } else if (hst.situacao === 'erro') {
    filhos.push(h('p', { class: 'alerta atencao', texto: 'Não foi possível consultar o histórico agora. A triagem segue normalmente.' }));
    resumo = 'Histórico indisponível';
  } else {
    filhos.push(h('p', { class: 'dica', texto: 'Opcional. Digite o prontuário no cadastro: a Salus mostra os atendimentos anteriores e avisa quando a ficha de hoje repete um padrão.' }));
    const exemplos = estado.dados.historico.exemplos;
    if (exemplos.length) {
      filhos.push(h('div', { class: 'chips' }, h('span', { class: 'dica', texto: 'Para demonstrar:' }),
        exemplos.map((p) => h('button', { type: 'button', class: 'chip', texto: p, onclick() { $('#prontuario').value = p; buscarHistorico(); } }))));
    }
  }
  if (hst.situacao !== 'vazio') {
    filhos.push(h('div', { class: 'controles' }, h('button', { type: 'button', class: 'pilula discreta', texto: 'Tirar o histórico', onclick: limparHistorico })));
  }
  const situacao = $('#prontuario-situacao');
  if (situacao) situacao.textContent = resumo;
  caixa.replaceChildren(...filhos);
}

/* ---------------------------------------------------------------- chamada ao servidor */

function agendar() {
  clearTimeout(estado.timer);
  estado.timer = setTimeout(calcular, 250);
}

// Roda o fluxo real no servidor e guarda o resultado em `estado`. Enquanto a ficha é preenchida
// (passo 1) a leitura do relato é sempre a de palavras-chave, que é instantânea: ela guia as
// pendências e os alertas imediatos. O leitor escolhido (ex.: modelo local) só roda no "Analisar".
async function calcular(extrator = 'mock') {
  const ficha = lerFicha();
  const hst = estado.historico;
  const minha = ++estado.seq;
  if (ficha.dados_atendente.idade === undefined) {
    estado.saida = null; estado.erros = null; hst.padroes = null;
    limparMarcas();
    renderTudo();
    return false;
  }
  estado.pedeIdade = false;
  const envio = { ficha, extrator };
  if (hst.dados) envio.prontuario = hst.prontuario;
  try {
    const { status, corpo } = await postar('/api/triagem', envio);
    if (minha !== estado.seq) return false;
    if (status === 200) {
      estado.saida = corpo.saida; estado.erros = null;
      // só aceita o cruzamento se o prontuário ainda for o mesmo de quando o pedido saiu
      if (hst.dados && hst.prontuario === envio.prontuario) hst.padroes = corpo.historico ? corpo.historico.padroes : null;
      marcarPerguntas(corpo.saida);
    } else {
      estado.erros = corpo.erros || ['erro desconhecido'];
    }
  } catch (e) {
    if (minha !== estado.seq) return false;
    estado.erros = [`Não foi possível falar com o servidor local (${e.message}). Ele ainda está rodando?`];
  }
  renderTudo();
  return estado.erros === null;
}

function renderTudo() {
  renderImediato();
  renderVoz();
  renderResumo();
  renderHistorico();
  if (estado.passo === 'analise') renderAnalise();
}

/* ---------------------------------------------------------------- passos */

// Encerra a gravação em andamento. `ocupado` já fica ligado aqui, para um segundo toque seguido
// não abrir outra gravação antes de a primeira ser tratada.
function pararGravacao() {
  if (voz.gravador && voz.gravador.state === 'recording') {
    voz.ocupado = true;
    voz.gravador.stop();
    renderVoz();
  }
}

function atualizarMini() {
  $('#mini').hidden = estado.passo !== 'ficha' || $('#tela-triagem').hidden;
}

function irParaPasso(passo, manterRolagem = false) {
  const antes = estado.passo;
  if (antes === 'ficha' && passo !== 'ficha') estado.rolagemFicha = window.scrollY;
  estado.passo = passo;
  const analise = passo === 'analise';
  $('#passo-ficha').hidden = analise;
  $('#passo-analise').hidden = !analise;
  $('#passo-1').setAttribute('aria-current', analise ? 'false' : 'step');
  $('#passo-1').classList.toggle('feito', analise);
  $('#passo-2').setAttribute('aria-current', analise ? 'step' : 'false');
  atualizarMini();
  renderTudo();
  if (analise) window.scrollTo({ top: 0 });
  else if (antes === 'analise' && !manterRolagem) window.scrollTo({ top: estado.rolagemFicha });
}

async function analisar() {
  if (estado.campos.idade.get() === undefined) {
    if (estado.passo !== 'ficha') irParaPasso('ficha', true);
    estado.pedeIdade = true;
    renderResumo();
    const campo = estado.campos.idade.el;
    campo.scrollIntoView({ block: 'center' });
    campo.focus({ preventScroll: true });
    return;
  }
  pararGravacao();
  clearTimeout(estado.timer);
  const minha = ++estado.seqAnalise;
  estado.analisando = true;
  irParaPasso('analise');
  // prontuário digitado e ainda não buscado (ou busca em andamento): resolve antes, para a
  // análise já sair cruzada com o histórico certo
  const hst = estado.historico, campo = $('#prontuario');
  if (campo && (campo.value.trim() !== hst.prontuario || hst.situacao === 'buscando')) await buscarHistorico(false);
  if (minha !== estado.seqAnalise) return;
  await calcular($('#extrator').value);
  if (minha !== estado.seqAnalise) return; // houve outra análise depois desta
  estado.analisando = false;
  renderAnalise();
}

function voltarParaFicha() {
  if (estado.enviando) return; // a ficha está indo para a fila: espera a resposta
  estado.seqAnalise += 1; // uma análise em andamento deixa de valer
  estado.analisando = false;
  irParaPasso('ficha');
}

/* ---------------------------------------------------------------- passo 1: avisos ao lado da ficha */

function limparMarcas() {
  for (const c of Object.values(estado.perguntas)) {
    c.el.classList.remove('pendente', 'proxima', 'inativa'); c.selo.hidden = true; c.nota.hidden = true;
  }
  for (const m of Object.values(estado.modulos)) m.ativo.hidden = true;
}

function irParaPergunta(id) {
  const c = estado.perguntas[id];
  if (!c) return;
  if (estado.enviando) return;
  if (estado.passo !== 'ficha') voltarParaFichaSemRolar();
  const det = c.el.closest('details');
  if (det) det.open = true;
  c.el.scrollIntoView({ behavior: 'smooth', block: 'center' });
  const foco = c.el.querySelector('input, select, button');
  if (foco) foco.focus({ preventScroll: true });
}

function voltarParaFichaSemRolar() {
  estado.seqAnalise += 1;
  estado.analisando = false;
  irParaPasso('ficha', true);
}

function marcarPerguntas(s) {
  limparMarcas();
  const pend = new Set(s.perguntas_pendentes);
  const status = Object.fromEntries(s.sinais.map((x) => [x.nome, x.status]));
  for (const [id, c] of Object.entries(estado.perguntas)) {
    const pergunta = estado.dados.perguntas.find((p) => p.id === id);
    const nomes = (pergunta.sinais || []).map((x) => x.nome);
    if (nomes.length && nomes.every((n) => status[n] === 'nao_se_aplica')) { c.el.classList.add('inativa'); c.nota.hidden = false; }
    if (pend.has(id)) {
      c.el.classList.add('pendente');
      c.selo.hidden = false; c.selo.className = 'selo-estado pend'; c.selo.textContent = 'pendente';
    }
    if (id === s.proxima_pergunta) { c.el.classList.add('proxima'); c.selo.className = 'selo-estado prox'; c.selo.textContent = 'próxima'; }
  }
  for (const [chave, m] of Object.entries(estado.modulos)) {
    const ativo = s.modulos_ativos.includes(chave);
    m.ativo.hidden = !ativo; m.ativo.textContent = 'ativo';
    if (ativo) m.det.open = true;
  }
}

// Sinal de alerta aparece na hora, ainda no passo 1: é aviso de segurança, não a cor.
function renderImediato() {
  const caixa = $('#alerta-imediato');
  const graves = estado.passo === 'ficha' && estado.saida && estado.campos.idade.get() !== undefined
    ? estado.saida.alertas.filter((a) => a.codigo === 'sinal_de_alerta') : [];
  const texto = graves.map((a) => a.mensagem).join('\n');
  caixa.hidden = !graves.length;
  if (caixa.dataset.texto === texto) return; // não repete o anúncio para o leitor de tela
  caixa.dataset.texto = texto;
  caixa.replaceChildren(...(graves.length ? [h('div', { class: 'alerta grave' },
    h('span', { class: 'cod', texto: 'Sinal de alerta' }), graves.map((a) => h('span', { texto: a.mensagem })),
    h('span', { class: 'dica', texto: 'Aviso imediato. A cor sugerida aparece na análise.' }))] : []));
}

function chipsDePendentes(ids) {
  return h('div', { class: 'chips' }, ids.map((id) => h('button', { type: 'button', class: 'chip alerta-chip', title: 'Ir para a pergunta', onclick: () => irParaPergunta(id), texto: id })));
}

function renderResumo() {
  const caixa = $('#resumo-ficha');
  if (!caixa || !estado.dados) return;
  const filhos = [h('h2', { texto: 'Pronto para analisar?' })];
  if (estado.campos.idade.get() === undefined) {
    filhos.push(h('p', { class: estado.pedeIdade ? 'alerta atencao' : 'dica', texto: 'Preencha a idade no cadastro para começar.' }));
  } else if (estado.erros) {
    filhos.push(h('div', { class: 'alerta grave', role: 'alert' }, h('span', { class: 'cod', texto: 'Corrija na ficha' }),
      h('ul', { class: 'lista-erros' }, estado.erros.map((e) => h('li', { texto: e })))));
  } else if (estado.saida) {
    const s = estado.saida, pend = s.perguntas_pendentes;
    if (pend.length) {
      filhos.push(h('p', {}, h('strong', { texto: pend.length === 1 ? '1 pergunta pendente' : `${pend.length} perguntas pendentes` })), chipsDePendentes(pend));
    } else {
      filhos.push(h('p', { class: 'tudo-certo', texto: 'Nenhuma pergunta pendente.' }));
    }
    if (s.afericoes_faltando.length) filhos.push(h('p', { class: 'dica', texto: `Aferições não registradas: ${s.afericoes_faltando.join(', ')} (valem como “não aferidas”).` }));
  }
  filhos.push(h('button', { type: 'button', class: 'pilula enorme', texto: estado.reclassificando ? 'Analisar de novo' : 'Analisar', onclick: analisar }),
    h('p', { class: 'dica', texto: 'A cor e a pontuação aparecem na análise. Só depois dela o paciente pode ir para a fila.' }));
  caixa.replaceChildren(...filhos);
}

/* ---------------------------------------------------------------- passo 2: análise */

function secao(titulo, ...filhos) { return h('section', { class: 'cartao' }, h('h3', { texto: titulo }), ...filhos); }

function linhaSinal(x) {
  const extras = [];
  if (x.valor !== null && x.valor !== undefined) extras.push(`valor: ${x.valor}`);
  if (x.itens && x.itens.length) extras.push(x.itens.join(', '));
  if (x.status_no_relato) extras.push(`o relato dizia: ${(STATUS[x.status_no_relato] ?? x.status_no_relato).toLowerCase()}`);
  if (x.trecho) extras.push(`trecho: “${x.trecho}”`);
  return h('li', {}, h('span', { class: 'nome', texto: nomeSinal(x.nome) }),
    h('span', { class: 'chip neutro', texto: ORIGEM[x.origem] ?? x.origem }),
    extras.length ? h('span', { class: 'detalhe', texto: extras.join(' · ') }) : null);
}

function botaoVoltar(texto = '← Voltar à ficha') {
  return h('button', { type: 'button', class: 'pilula secundaria', texto, onclick: voltarParaFicha });
}

function cartaoDoHistoricoNaAnalise() {
  const hst = estado.historico;
  if (!estado.dados.historico.ligado) return null;
  if (!hst.dados) {
    const motivo = { nao_encontrado: 'Prontuário não encontrado', invalido: 'Prontuário inválido', erro: 'Histórico indisponível agora' }[hst.situacao]
      ?? 'Nenhum prontuário informado';
    return secao('Histórico do paciente', h('p', { class: 'dica', texto: `${motivo}: a análise não considerou atendimentos anteriores.` }));
  }
  const padroes = hst.padroes || [];
  const n = hst.dados.atendimentos.length;
  return secao(`Histórico do paciente: ${padroes.length === 1 ? '1 padrão' : `${padroes.length} padrões`}`,
    h('p', { class: 'dica', texto: `Prontuário ${hst.dados.prontuario} · ${n === 1 ? '1 atendimento anterior' : `${n} atendimentos anteriores`}${hst.dados.simulado ? ' · dados simulados' : ''}` }),
    padroes.length ? listaDePadroes(padroes) : h('p', { class: 'dica', texto: 'Nenhum padrão entre o histórico e a ficha de hoje.' }),
    h('p', { class: 'dica', texto: 'Aviso para a equipe: não é diagnóstico e não muda a cor nem a pontuação.' }));
}

function renderAnalise() {
  const painel = $('#painel');
  if (estado.analisando) {
    painel.replaceChildren(h('section', { class: 'cartao vazio', role: 'status' },
      h('p', { class: 'analisando', texto: $('#extrator').value === 'mock' ? 'Analisando…' : 'Analisando o relato com o modelo local. Pode levar de 10 a 120 segundos…' }),
      h('div', { class: 'controles centro' }, botaoVoltar('Cancelar e voltar à ficha'))));
    return;
  }
  if (estado.erros || !estado.saida) {
    const erros = estado.erros || ['Preencha a idade para analisar.'];
    painel.replaceChildren(h('section', { class: 'cartao erro-cartao', role: 'alert' },
      h('h3', { texto: 'Não foi possível analisar' }), h('p', { texto: 'Corrija o que está abaixo e analise de novo:' }),
      h('ul', {}, erros.map((e) => h('li', { texto: e }))),
      h('div', { class: 'controles' }, botaoVoltar(), h('button', { type: 'button', class: 'pilula', texto: 'Analisar de novo', onclick: analisar }))));
    return;
  }
  const s = estado.saida, c = s.classificacao;
  const topo = h('section', { class: 'cartao cor-cartao' },
    h('div', { class: 'cor-linha' },
      h('span', { class: `cor-selo cor-${c.cor}`, texto: `Cor sugerida: ${c.cor}` }),
      h('span', { class: 'nota' }, String(c.pontuacao), h('small', { texto: ' / 100 dentro da cor' }))),
    h('div', { class: `medidor cor-${c.cor}`, role: 'img', 'aria-label': `Pontuação ${c.pontuacao} de 100` }, h('span', { style: `width:${c.pontuacao}%` })),
    h('p', { class: 'provisoria', texto: `Sugestão provisória. ${c.regras_validadas ? '' : 'As regras ainda não foram validadas por profissional de saúde. '}A decisão final é do profissional.` }),
    estado.reclassificando
      ? h('div', { class: 'controles' },
        h('button', { type: 'button', class: 'pilula enorme', texto: `Atualizar classificação do ${numeroFila(estado.reclassificando.numero)}`, onclick: (ev) => atualizarReclassificacao(ev.target, false) }),
        botaoVoltar(),
        h('span', { class: 'dica', texto: `Cor atual na fila: ${CORES[estado.reclassificando.cor] ?? estado.reclassificando.cor}. Mantém número, QR e hora de chegada.` }))
      : h('div', { class: 'controles' },
        h('button', { type: 'button', class: 'pilula enorme', texto: 'Colocar na fila', onclick: colocarNaFila }),
        botaoVoltar(),
        h('span', { class: 'dica', texto: 'Gera o número de atendimento e o QR do paciente.' })));

  const cartoes = [];
  if (s.alertas.length) {
    const ordem = { grave: 0, atencao: 1, info: 2 };
    const nivel = (a) => (ALERTAS[a.codigo] || [null, 'info'])[1];
    const lista = [...s.alertas].sort((a, b) => ordem[nivel(a)] - ordem[nivel(b)]);
    cartoes.push(secao(`Alertas (${s.alertas.length})`, h('ul', { class: 'alertas' }, lista.map((a) => {
      const [nome, niv] = ALERTAS[a.codigo] || [humanizar(a.codigo), 'info'];
      return h('li', { class: `alerta ${niv}` }, h('span', { class: 'cod', texto: nome }), h('span', { texto: a.mensagem }));
    }))));
  }
  const historico = cartaoDoHistoricoNaAnalise();
  if (historico) cartoes.push(historico);

  const pend = s.perguntas_pendentes;
  cartoes.push(secao(`Perguntas pendentes (${pend.length})`,
    pend.length ? chipsDePendentes(pend) : h('p', { class: 'dica', texto: 'Nenhuma pergunta pendente.' }),
    pend.length ? h('p', { class: 'dica', texto: 'Tocar numa pergunta volta à ficha, já no lugar dela.' }) : null,
    s.afericoes_faltando.length ? h('p', { class: 'dica', texto: `Aferições não registradas: ${s.afericoes_faltando.join(', ')} (valem como “não aferidas”).` }) : null));

  const al = s.alergias;
  cartoes.push(secao('Alergias', h('p', {}, h('strong', { texto: STATUS[al.status] ?? al.status }),
    al.itens.length ? ` — ${al.itens.join(', ')}` : '', al.tipos.length ? ` (${al.tipos.map(rotulo).join(', ')})` : ''),
  h('p', { class: 'dica', texto: 'Informação de segurança para a equipe; não entra na pontuação.' })));

  const ext = [];
  if (s.queixa_principal) ext.push(h('p', {}, h('strong', { texto: 'Queixa: ' }), s.queixa_principal));
  if (s.queixas.length) ext.push(h('div', { class: 'chips' }, s.queixas.map((q) => h('span', { class: 'chip', texto: QUEIXAS[q] ?? humanizar(q) }))));
  if (s.duracao) ext.push(h('p', {}, h('strong', { texto: 'Duração: ' }), `${s.duracao.valor} ${s.duracao.unidade}`));
  ext.push(h('p', { class: 'dica', texto: `Leitura do relato: ${s.extrator}` }));
  cartoes.push(secao('Relato e duração', ...ext));

  const presentes = s.sinais.filter((x) => x.status === 'presente');
  const negados = s.sinais.filter((x) => x.status === 'negado');
  const desconhecidos = s.sinais.filter((x) => ['nao_sabe', 'recusou', 'incerto'].includes(x.status));
  cartoes.push(secao(`Sinais presentes (${presentes.length})`,
    presentes.length ? h('ul', { class: 'lista-sinais' }, presentes.map(linhaSinal)) : h('p', { class: 'dica', texto: 'Nenhum sinal presente até agora.' }),
    desconhecidos.length ? h('div', {}, h('p', { class: 'rotulo-secao', texto: 'Sem resposta definitiva (não valem como “não”)' }),
      h('ul', { class: 'lista-sinais' }, desconhecidos.map((x) => { const li = linhaSinal(x); li.prepend(h('span', { class: 'chip alerta-chip', texto: STATUS[x.status] ?? x.status })); return li; }))) : null,
    negados.length ? h('div', {}, h('p', { class: 'rotulo-secao', texto: 'Negados' }),
      h('div', { class: 'chips' }, negados.map((x) => h('span', { class: 'chip neutro', texto: nomeSinal(x.nome) })))) : null));

  const regras = c.regras_aplicadas;
  cartoes.push(h('section', { class: 'cartao' }, h('details', { class: 'sub' }, h('summary', { texto: `Por que esta cor e esta pontuação? (${regras.length})` }),
    regras.length ? h('ol', { class: 'regras' }, regras.map((r) => h('li', {}, h('strong', { texto: r.id }), ` — ${r.descricao}: ${r.efeito}`)))
      : h('p', { class: 'dica', texto: 'Nenhuma regra acionada: cor base, zero pontos.' }))));

  const json = JSON.stringify(s, null, 2);
  cartoes.push(h('section', { class: 'cartao' }, h('details', { class: 'sub' }, h('summary', { texto: 'JSON completo' }),
    h('div', { class: 'controles' }, h('button', { type: 'button', class: 'pilula secundaria', texto: 'Copiar JSON',
      onclick(ev) { navigator.clipboard.writeText(json).then(() => { ev.target.textContent = 'Copiado'; }, () => { ev.target.textContent = 'Não foi possível copiar'; }); } })),
    h('pre', { texto: json }))));

  painel.replaceChildren(topo, h('div', { class: 'analise-cartoes' }, cartoes));
}

/* ---------------------------------------------------------------- entrevista por voz */
// O enfermeiro fala; o servidor transcreve na máquina e interpreta por código. Nada entra na
// ficha sem o enfermeiro confirmar (Enter, botão ou toque direto na resposta).
// Ordem: segurança -> relato -> pendências. A gravação para sozinha quando a fala termina.

// `geracao` muda a cada ficha nova: o que foi gravado para um paciente nunca aparece na ficha do próximo
const voz = { pulados: new Set(), chave: null, gravador: null, pedacos: [], ocupado: false, resultado: null, limite: null, seguir: true, soltar: null, abrindo: false, geracao: 0 };
const FASES = ['Segurança', 'Relato', 'Complementares'];

function partesPendentes(id) {
  const c = estado.perguntas[id];
  if (!c || c.temMarcador()) return [];
  return Object.values(c.partes).filter(({ parte, get }) => {
    const dep = parte.depende_de;
    if (dep && c.partes[dep.parte].get() !== dep.igual) return false;
    return get() === undefined;
  }).map((i) => i.parte.nome);
}

function passosPendentes() {
  const q = estado.dados;
  const fases = [
    q.perguntas.filter((p) => p.obrigatoriedade === 'S').map((p) => p.id),
    ['Q01'],
    estado.saida ? estado.saida.perguntas_pendentes : [],
  ];
  const passos = [], vistos = new Set();
  for (const [fase, ids] of fases.entries()) {
    for (const id of ids) {
      if (estado.perguntas[id].el.classList.contains('inativa')) continue; // não se aplica ao paciente
      for (const parte of partesPendentes(id)) {
        const chave = `${id}.${parte}`;
        if (voz.pulados.has(chave) || vistos.has(chave)) continue;
        vistos.add(chave);
        passos.push({ fase, id, parte });
      }
    }
  }
  return passos;
}

function dicaDaParte(parte) {
  switch (parte.forma) {
    case 'sim_nao': return 'Diga "sim", "não", "não sabe" ou "recusou".';
    case 'escala': return 'Diga um número de 0 a 10.';
    case 'numero': return 'Diga o número.';
    case 'opcao': return `Opções: ${parte.opcoes.map(rotulo).join(', ')}.`;
    case 'multiplas': return `Opções: ${parte.opcoes.map(rotulo).join(', ')} (ou "nenhuma").`;
    case 'numero_unidade': return 'Diga o número e a unidade, por exemplo "2 horas".';
    default: return 'Dite o texto. Você pode corrigir antes de confirmar.';
  }
}

function textoDoValor(v) {
  if (v === true) return 'Sim';
  if (v === false) return 'Não';
  if (Array.isArray(v)) return v.length ? v.map(rotulo).join(', ') : 'Nenhuma';
  if (v && typeof v === 'object') return `${v.valor} ${rotulo(v.unidade)}`;
  if (typeof v === 'string') return rotulo(v);
  return String(v);
}

function aplicarValor(id, nomeParte, v) {
  const c = estado.perguntas[id];
  if (c.simples || v === 'nao_se_aplica') c.set(v); // marcador vale para a pergunta inteira
  else c.partes[nomeParte].set(v);
}

// Para a gravação sozinha: depois que alguém falou, `espera` ms de silêncio encerram.
// "Silêncio" é relativo: o limiar acompanha o ruído do ambiente (o piso desce na hora e sobe
// devagar, então segue o barulho da sala) e o volume da própria fala (uma fração do pico recente).
// Se não der para medir, nada quebra: o botão "Parar" e o tempo máximo continuam valendo.
function pararEsta(rec) {
  if (rec === voz.gravador) pararGravacao(); else if (rec.state === 'recording') rec.stop();
}

function vigiarSilencio(fluxo, rec, espera) {
  let ctx;
  try { ctx = new AudioContext(); } catch (e) { return () => {}; }
  if (ctx.state === 'suspended') ctx.resume().catch(() => {});
  const analisador = ctx.createAnalyser();
  analisador.fftSize = 1024;
  ctx.createMediaStreamSource(fluxo).connect(analisador);
  const amostras = new Uint8Array(analisador.fftSize);
  const inicio = performance.now();
  let piso = Infinity, pico = 0, falou = false, ultimoSom = inicio;
  const id = setInterval(() => {
    analisador.getByteTimeDomainData(amostras);
    let soma = 0;
    for (const a of amostras) { const x = (a - 128) / 128; soma += x * x; }
    const volume = Math.sqrt(soma / amostras.length);
    const agora = performance.now();
    piso = Math.min(volume, piso * 1.02);
    pico = Math.max(pico * 0.985, volume);
    const limiar = Math.max(0.02, Math.min(piso, 0.08) * 2.5, pico * 0.15);
    const barra = document.querySelector('#voz-nivel span');
    if (barra) barra.style.width = `${Math.min(100, Math.round(volume * 500))}%`;
    if (volume > limiar) { falou = true; ultimoSom = agora; }
    else if (falou && agora - ultimoSom > espera && rec.state === 'recording') pararEsta(rec);
  }, 60);
  return () => { clearInterval(id); ctx.close().catch(() => {}); };
}

async function alternarGravacao() {
  if (voz.gravador && voz.gravador.state === 'recording') { pararGravacao(); return; }
  if (voz.ocupado || voz.abrindo || !voz.passo) return; // `abrindo`: dois toques seguidos não abrem dois microfones
  const geracao = voz.geracao;
  let fluxo;
  voz.abrindo = true;
  try {
    fluxo = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, channelCount: 1 } });
  } catch (e) {
    voz.resultado = { erro: `Não foi possível usar o microfone (${e.message}). Autorize o microfone no navegador.` };
    renderVoz();
    return;
  } finally {
    voz.abrindo = false;
  }
  const soltarMicrofone = () => fluxo.getTracks().forEach((t) => t.stop());
  const passo = voz.passo;
  // enquanto o navegador pedia o microfone, a ficha ou a tela mudou: não grava
  if (!passo || geracao !== voz.geracao || estado.passo !== 'ficha' || $('#tela-triagem').hidden) { soltarMicrofone(); return; }
  const parte = estado.perguntas[passo.id].partes[passo.parte].parte;
  const longa = parte.forma === 'texto';
  let rec;
  try {
    rec = new MediaRecorder(fluxo, { audioBitsPerSecond: 32000 });
  } catch (e) {
    soltarMicrofone();
    voz.resultado = { erro: `Este navegador não conseguiu gravar (${e.message}). Responda tocando ou na ficha.` };
    renderVoz();
    return;
  }
  voz.pedacos = [];
  rec.ondataavailable = (ev) => { if (ev.data.size) voz.pedacos.push(ev.data); };
  rec.onstop = () => {
    soltarMicrofone();
    clearTimeout(voz.limite);
    if (voz.soltar) { voz.soltar(); voz.soltar = null; }
    const blob = new Blob(voz.pedacos, { type: rec.mimeType || 'audio/webm' });
    voz.pedacos = [];
    if (geracao !== voz.geracao) { voz.ocupado = false; renderVoz(); return; } // a ficha mudou: o áudio é descartado aqui mesmo
    if (!blob.size) { voz.ocupado = false; voz.resultado = { erro: 'Nada foi gravado. Toque em "Falar" e responda.' }; renderVoz(); return; }
    enviarAudio(passo, blob, geracao);
  };
  voz.gravador = rec;
  voz.resultado = null;
  rec.start();
  voz.soltar = vigiarSilencio(fluxo, rec, longa ? 2500 : 800);
  voz.limite = setTimeout(() => pararEsta(rec), longa ? 90000 : 15000);
  renderVoz();
}

async function enviarAudio(passo, blob, geracao) {
  voz.ocupado = true;
  renderVoz();
  let resultado;
  try {
    const r = await fetch(`/api/voz?pergunta=${encodeURIComponent(passo.id)}&parte=${encodeURIComponent(passo.parte)}`,
      { method: 'POST', headers: { 'Content-Type': blob.type || 'audio/webm' }, body: blob });
    const corpo = await r.json();
    resultado = r.status === 200 ? { ...corpo, passo } : { erro: (corpo.erros || ['erro desconhecido']).join('; ') };
  } catch (e) {
    resultado = { erro: `Não foi possível falar com o servidor local (${e.message}).` };
  }
  voz.ocupado = false;
  if (geracao === voz.geracao) voz.resultado = resultado; // resposta de uma ficha que já foi trocada é ignorada
  renderVoz();
}

async function confirmarVoz(valor) {
  if (!voz.resultado || !voz.resultado.passo) return; // dois cliques seguidos em "Confirmar"
  const { passo } = voz.resultado;
  aplicarValor(passo.id, passo.parte, valor);
  voz.resultado = null;
  await calcular(); // recalcula na hora: alerta de sinal grave aparece já
  renderVoz();
  if (voz.seguir && voz.passo && estado.passo === 'ficha' && !$('#tela-triagem').hidden) alternarGravacao(); // já ouve a próxima pergunta
}

// toque direto na resposta, sem passar pelo microfone
async function responderRapido(passo, valor) {
  if (voz.gravador && voz.gravador.state === 'recording') return;
  aplicarValor(passo.id, passo.parte, valor);
  voz.resultado = null;
  await calcular();
  renderVoz();
}

function atalhosDaParte(passo, parte) {
  const b = (texto, v, classe = '') => h('button', { type: 'button', class: `opcao ${classe}`.trim(), texto, onclick: () => responderRapido(passo, v) });
  const duvida = [b('Não sabe', 'nao_sabe', 'marcador'), b('Recusou', 'recusou', 'marcador')];
  switch (parte.forma) {
    case 'sim_nao': return [b('Sim', true), b('Não', false), ...duvida];
    case 'escala': return [...Array.from({ length: 11 }, (_, i) => b(String(i), i, 'num')), ...duvida];
    case 'opcao': return [...parte.opcoes.map((o) => b(rotulo(o), o)), ...duvida];
    default: return duvida;
  }
}

function resultadoPendente() {
  const r = voz.resultado;
  return r && !r.erro && r.passo && `${r.passo.id}.${r.passo.parte}` === voz.chave ? r : null;
}

function teclaDeVoz(ev) {
  if (ev.ctrlKey || ev.altKey || ev.metaKey || ev.repeat) return;
  if ($('#tela-triagem').hidden || estado.passo !== 'ficha' || $('#janela-qr').open || !estado.dados || !estado.dados.voz || !voz.passo) return;
  if (ev.target.closest && ev.target.closest('input, textarea, select, button, summary, a')) return;
  if (ev.code === 'Space') { ev.preventDefault(); alternarGravacao(); }
  else if (ev.key === 'Enter') {
    const r = resultadoPendente();
    const forma = estado.perguntas[voz.passo.id].partes[voz.passo.parte].parte.forma;
    if (r && r.entendido && forma !== 'texto') { ev.preventDefault(); confirmarVoz(r.valor); } // o relato é revisado na caixa de texto
  }
}

function renderVoz() {
  const caixa = $('#voz');
  if (!caixa || !estado.dados) return;
  const titulo = h('h2', { id: 'titulo-voz', texto: 'Entrevista por voz' });
  if (!estado.dados.voz) {
    caixa.replaceChildren(titulo, h('p', { class: 'dica', texto: 'Voz desligada neste computador. Para ligar: pip install -r requirements-voz.txt e reinicie a interface.' }));
    return;
  }
  if (estado.campos.idade.get() === undefined) {
    voz.passo = null;
    caixa.replaceChildren(titulo, h('p', { class: 'dica', texto: 'Preencha a idade no cadastro abaixo para começar. Depois a entrevista segue por voz: segurança, relato e perguntas complementares.' }));
    return;
  }
  const passos = passosPendentes();
  const passo = passos[0] || null;
  const chave = passo ? `${passo.id}.${passo.parte}` : null;
  if (chave !== voz.chave) { voz.chave = chave; if (voz.resultado && voz.resultado.erro) voz.resultado = null; }
  voz.passo = passo;
  const faseAtual = passo ? passo.fase : FASES.length;
  const filhos = [h('div', { class: 'voz-topo' }, titulo,
    h('ol', { class: 'etapas', 'aria-label': 'Etapas da entrevista' }, FASES.map((nome, i) => h('li', {
      class: i < faseAtual ? 'feita' : i === faseAtual ? 'atual' : '', 'aria-current': i === faseAtual ? 'step' : null, texto: nome,
    }))),
    passo ? h('span', { class: 'chip neutro', texto: passos.length === 1 ? 'falta 1 resposta' : `faltam ${passos.length} respostas` }) : null)];
  if (!passo) {
    filhos.push(h('p', { class: 'voz-fim', texto: 'Entrevista concluída. Clique em "Analisar" para ver a cor, os alertas e o histórico.' }));
    if (voz.pulados.size) filhos.push(h('div', { class: 'controles' }, h('button', { type: 'button', class: 'pilula secundaria', texto: `Voltar às ${voz.pulados.size} pulada(s)`, onclick() { voz.pulados.clear(); renderVoz(); } })));
    caixa.replaceChildren(...filhos);
    return;
  }
  const p = estado.dados.perguntas.find((x) => x.id === passo.id);
  const parte = p.partes.find((x) => x.nome === passo.parte);
  const gravando = Boolean(voz.gravador && voz.gravador.state === 'recording');
  filhos.push(
    h('div', { class: 'voz-pergunta' }, h('span', { class: 'id', texto: p.id }),
      h('div', {}, h('p', { class: 'texto', texto: p.texto }),
        p.partes.length > 1 && parte.nome !== 'resposta' ? h('p', { class: 'parte-voz', texto: `Agora: ${PARTES[parte.nome] ?? humanizar(parte.nome)}` }) : null,
        h('p', { class: 'dica', texto: dicaDaParte(parte) }))),
    h('div', { class: 'voz-acao' },
      h('button', { type: 'button', class: 'pilula gravar', 'aria-pressed': String(gravando), disabled: voz.ocupado,
        texto: gravando ? '■ Parar' : voz.ocupado ? 'Transcrevendo…' : '● Falar', onclick: alternarGravacao }),
      gravando
        ? h('div', { class: 'voz-estado' }, h('p', { class: 'gravando', texto: 'Ouvindo… paro sozinho quando você terminar de falar.' }),
          h('div', { class: 'nivel', id: 'voz-nivel', 'aria-hidden': 'true' }, h('span', {})))
        : h('p', { class: 'dica voz-estado', texto: voz.ocupado ? 'Transcrevendo nesta máquina…' : 'Atalhos: Espaço fala ou para · Enter confirma.' })));
  const r = voz.resultado;
  if (r && r.erro) filhos.push(h('p', { class: 'alerta atencao', texto: r.erro }));
  else if (resultadoPendente()) {
    const ouvi = h('p', { class: 'ouvi' }, h('strong', { texto: 'Ouvi: ' }), `“${r.transcricao || '(nada)'}”`);
    if (r.entendido && parte.forma === 'texto') {
      const area = h('textarea', { rows: '4', maxlength: String(parte.max_caracteres ?? 1000), 'aria-label': 'Texto transcrito' });
      area.value = r.valor;
      area.addEventListener('input', () => { r.valor = area.value; }); // a correção sobrevive a um redesenho do painel
      filhos.push(h('div', { class: 'voz-resultado' }, ouvi, area,
        h('div', { class: 'controles' }, h('button', { type: 'button', class: 'pilula', texto: 'Confirmar', onclick: () => confirmarVoz(area.value.trim()) }),
          h('button', { type: 'button', class: 'pilula secundaria', texto: 'Falar de novo', onclick: alternarGravacao }))));
    } else if (r.entendido) {
      filhos.push(h('div', { class: 'voz-resultado entendido' }, ouvi, h('p', { class: 'entendi' }, h('strong', { texto: 'Entendi: ' }), textoDoValor(r.valor)),
        h('div', { class: 'controles' }, h('button', { type: 'button', class: 'pilula', texto: 'Confirmar (Enter)', onclick: () => confirmarVoz(r.valor) }),
          h('button', { type: 'button', class: 'pilula secundaria', texto: 'Falar de novo', onclick: alternarGravacao }))));
    } else {
      filhos.push(h('div', { class: 'voz-resultado' }, ouvi,
        h('p', { class: 'alerta atencao', texto: `Não entendi (${r.motivo}). Fale de novo ou toque na resposta abaixo.` })));
    }
  }
  const seguir = h('input', { type: 'checkbox', onchange(ev) { voz.seguir = ev.target.checked; } });
  seguir.checked = voz.seguir;
  filhos.push(
    h('div', { class: 'voz-atalhos' }, h('span', { class: 'rotulo-secao', texto: 'Ou toque na resposta' }),
      h('div', { class: 'opcoes' }, atalhosDaParte(passo, parte))),
    h('div', { class: 'controles voz-rodape' },
      h('button', { type: 'button', class: 'pilula secundaria', texto: 'Pular', disabled: gravando || voz.ocupado,
        onclick() { voz.pulados.add(chave); voz.resultado = null; renderVoz(); } }),
      h('button', { type: 'button', class: 'pilula secundaria', texto: 'Ver na ficha', onclick: () => irParaPergunta(p.id) }),
      h('label', { class: 'check' }, seguir, ' Ouvir a próxima pergunta logo depois de confirmar')));
  caixa.replaceChildren(...filhos);
}

/* ---------------------------------------------------------------- fila e QR */

const CORES = { vermelho: 'Vermelho', laranja: 'Laranja', amarelo: 'Amarelo', verde: 'Verde', azul: 'Azul' };
const numeroFila = (n) => String(n).padStart(3, '0');

async function postar(url, corpo) {
  const r = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(corpo) });
  let dados = {};
  try { dados = await r.json(); } catch (e) { /* resposta sem JSON (ex.: servidor reiniciando) */ }
  return { status: r.status, corpo: dados };
}

function falhaNaAnalise(erros) {
  estado.erros = erros;
  renderTudo();
}

// Passo 3: só existe depois da análise (o botão fica no cartão da cor).
async function colocarNaFila(ev) {
  const botao = ev.target;
  if (estado.analisando || estado.enviando || estado.passo !== 'analise') return;
  botao.disabled = true;
  estado.enviando = true;
  try {
    // o servidor processa a ficha de novo: a cor nunca sai do navegador
    const { status, corpo } = await postar('/api/fila', { ficha: lerFicha(), extrator: $('#extrator').value });
    if (status !== 200) { falhaNaAnalise(corpo.erros || ['erro desconhecido']); return; }
    novaFicha(); // a ficha deste paciente terminou: evita colocar a mesma pessoa duas vezes
    mostrarQR(corpo, true);
    carregarFila();
  } catch (e) {
    falhaNaAnalise([`Não foi possível falar com o servidor local (${e.message}).`]);
  } finally {
    estado.enviando = false;
    botao.disabled = false;
  }
}

function mostrarQR(r, nova) {
  $('#titulo-qr').textContent = nova ? 'Paciente na fila' : 'QR do paciente';
  $('#qr-numero').textContent = numeroFila(r.numero);
  const img = $('#qr-imagem');
  img.hidden = !r.qr;
  if (r.qr) img.src = r.qr; else img.removeAttribute('src');
  $('#qr-texto').textContent = r.url
    ? 'O paciente aponta a câmera do celular (no Wi-Fi da unidade) para ver a cor, o motivo e a faixa da fila.'
    : 'A página do paciente está desligada (--sem-paciente); informe só o número de atendimento.';
  $('#qr-url').textContent = r.url || '';
  $('#qr-fechar').textContent = nova ? 'Ver a fila' : 'Fechar';
  $('#qr-fechar').dataset.destino = nova ? 'fila' : '';
  $('#qr-nova').hidden = !nova;
  $('#janela-qr').showModal();
}

/* reclassificação: a ficha guardada volta para o passo 1; o paciente mantém número e QR */

function novaFicha() {
  estado.reclassificando = null;
  estado.seqAnalise += 1;
  estado.analisando = false;
  estado.pedeIdade = false;
  renderModo();
  voz.geracao += 1; // o que estiver sendo gravado ou transcrito era da ficha anterior
  pararGravacao();
  voz.pulados.clear(); voz.resultado = null;
  clearTimeout(estado.timer);
  preencher({}); $('#exemplo').value = '';
  limparHistorico();
  irParaPasso('ficha', true);
  calcular();
}

function renderModo() {
  const caixa = $('#modo-reclass');
  const r = estado.reclassificando;
  caixa.hidden = !r;
  // durante a reclassificação não dá para carregar um exemplo por cima da ficha do paciente
  $('#exemplo').disabled = Boolean(r);
  $('#titulo-entrevista').textContent = r ? `Reclassificação do ${numeroFila(r.numero)}` : 'Nova triagem';
  if (!r) { caixa.replaceChildren(); return; }
  caixa.replaceChildren(
    h('span', {}, h('strong', { texto: `Reclassificando o paciente ${numeroFila(r.numero)}` }),
      ` · cor atual na fila: ${CORES[r.cor] ?? r.cor}. Ajuste a ficha, clique em "Analisar de novo" e depois em "Atualizar classificação".`),
    h('button', { type: 'button', class: 'pilula secundaria', texto: 'Cancelar', onclick: novaFicha }));
}

async function iniciarReclassificacao(numero) {
  let resposta;
  try {
    resposta = await postar('/api/fila/ficha', { numero });
  } catch (e) { carregarFila(); return; }
  const { status, corpo } = resposta;
  if (status !== 200) { carregarFila(); return; }
  if (!corpo.ficha) {
    window.alert('Este paciente entrou na fila antes da reclassificação existir: a ficha não foi guardada. Faça uma nova triagem.');
    return;
  }
  const atual = lerFicha();
  const emAndamento = !estado.reclassificando && (Object.keys(atual.dados_atendente).length || Object.keys(atual.respostas).length);
  if (emAndamento && !window.confirm(`Há uma ficha em preenchimento na aba Triagem.

Reclassificar o ${numeroFila(numero)} agora apaga o que foi digitado nela. Continuar?`)) return;
  novaFicha();
  estado.reclassificando = { numero, cor: corpo.cor };
  if (corpo.extrator && [...$('#extrator').options].some((o) => o.value === corpo.extrator)) { $('#extrator').value = corpo.extrator; textoExtrator(); }
  preencher(corpo.ficha);
  mostrarTela('triagem');
  renderModo();
  window.scrollTo({ top: 0 });
  calcular();
}

async function atualizarReclassificacao(botao, confirmar) {
  const r = estado.reclassificando;
  if (!r || estado.analisando || (estado.enviando && !confirmar)) return;
  botao.disabled = true;
  estado.enviando = true;
  try {
    const { status, corpo } = await postar('/api/fila/reclassificar',
      { numero: r.numero, ficha: lerFicha(), extrator: $('#extrator').value, confirmar_reducao: confirmar });
    if (status === 409) {
      const ok = window.confirm(`A cor do paciente ${numeroFila(r.numero)} baixaria de ${CORES[corpo.cor_antes]} para ${CORES[corpo.cor_depois]}.\n\nConfirma que o paciente melhorou e a prioridade deve baixar?`);
      if (ok) await atualizarReclassificacao(botao, true);
      return;
    }
    if (status !== 200) { falhaNaAnalise(corpo.erros || ['erro desconhecido']); return; }
    novaFicha();
    mostrarTela('fila');
    $('#titulo-qr').textContent = 'Classificação atualizada';
    $('#qr-numero').textContent = numeroFila(corpo.numero);
    $('#qr-imagem').hidden = true;
    $('#qr-texto').textContent = corpo.cor_antes === corpo.cor_depois
      ? `Cor mantida: ${CORES[corpo.cor_depois]} (pontuação ${corpo.pontuacao_antes} → ${corpo.pontuacao_depois}).`
      : `Cor: ${CORES[corpo.cor_antes]} → ${CORES[corpo.cor_depois]}. O QR do paciente já mostra a nova classificação.`;
    $('#qr-url').textContent = '';
    $('#qr-fechar').textContent = 'Fechar';
    $('#qr-fechar').dataset.destino = '';
    $('#qr-nova').hidden = true;
    $('#janela-qr').showModal();
  } catch (e) {
    falhaNaAnalise([`Não foi possível falar com o servidor local (${e.message}).`]);
  } finally {
    estado.enviando = false;
    botao.disabled = false;
  }
}

function mostrarTela(qual) {
  const fila = qual === 'fila';
  if (fila) pararGravacao();
  $('#tela-triagem').hidden = fila;
  $('#tela-fila').hidden = !fila;
  $('#aba-triagem').setAttribute('aria-pressed', String(!fila));
  $('#aba-fila').setAttribute('aria-pressed', String(fila));
  atualizarMini();
  if (fila) carregarFila();
}

async function acaoFila(rota, numero) {
  try {
    const { status, corpo } = await postar(rota, { numero });
    if (rota === '/api/fila/qr' && status === 200) mostrarQR(corpo, false);
  } catch (e) { /* sem rede: a lista abaixo mostra o erro */ }
  carregarFila();
}

const avisosVistos = new Set(); // ids já anunciados com som

function bipe() {
  try {
    const ctx = new AudioContext();
    [0, 0.25].forEach((t) => {
      const o = ctx.createOscillator(), g = ctx.createGain();
      o.frequency.value = 880; g.gain.value = 0.15;
      o.connect(g).connect(ctx.destination);
      o.start(ctx.currentTime + t); o.stop(ctx.currentTime + t + 0.15);
    });
  } catch (e) { /* sem som: o aviso visual continua */ }
}

function mostrarAvisos(avisos) {
  const caixa = $('#avisos-piora');
  caixa.hidden = !avisos.length;
  $('#aba-fila').classList.toggle('com-aviso', avisos.length > 0);
  if (avisos.some((a) => !avisosVistos.has(a.id))) bipe();
  avisos.forEach((a) => avisosVistos.add(a.id));
  caixa.replaceChildren(...avisos.map((a) => h('div', { class: 'aviso-piora' },
    h('span', { class: `cor-chip cor-${a.cor}`, texto: numeroFila(a.numero) }),
    h('span', {}, h('strong', { texto: 'Paciente avisou que piorou: ' }), `${a.motivo} · ${a.ha_min ? `há ${a.ha_min} min` : 'agora'}`),
    h('span', { class: 'acoes' },
      h('button', { type: 'button', class: 'pilula secundaria', texto: 'Ver na fila', onclick: () => mostrarTela('fila') }),
      h('button', { type: 'button', class: 'pilula', texto: 'Vi o aviso', onclick: () => acaoFila('/api/fila/aviso-visto', a.numero) })))));
}

const haMin = (m) => (m ? `há ${m} min` : 'agora');

async function chamarPaciente(numero) {
  // um clique: o paciente é chamado e já sai da fila como atendido (dá para desfazer por 10 min)
  await acaoFila('/api/fila/chamar', numero);
}

function retirarPaciente(numero) {
  if (window.confirm(`Retirar o paciente ${numeroFila(numero)} da fila SEM chamar (desistiu ou foi embora)?\n\nNão dá para desfazer e o QR dele deixa de valer.`)) {
    acaoFila('/api/fila/concluir', numero);
  }
}

function linhaFila(p) {
  const acoes = [];
  if (p.avisos_piora.length) acoes.push(h('button', { type: 'button', class: 'pilula', texto: 'Vi o aviso', onclick: () => acaoFila('/api/fila/aviso-visto', p.numero) }));
  acoes.push(h('button', { type: 'button', class: 'pilula', texto: 'Chamar', title: 'Chama e já marca como atendido', onclick: () => chamarPaciente(p.numero) }));
  acoes.push(h('button', { type: 'button', class: 'pilula secundaria', texto: 'Reclassificar', onclick: () => iniciarReclassificacao(p.numero) }));
  acoes.push(h('button', { type: 'button', class: 'pilula secundaria', texto: 'Ver QR', onclick: () => acaoFila('/api/fila/qr', p.numero) }));
  acoes.push(h('button', { type: 'button', class: 'pilula discreta', texto: 'Retirar', title: 'Retira da fila sem chamar', onclick: () => retirarPaciente(p.numero) }));
  return h('tr', { class: p.avisos_piora.length ? 'piorou' : '' },
    h('td', { class: 'num', texto: `${p.posicao}º` }),
    h('td', { class: 'num grande', texto: numeroFila(p.numero) }),
    h('td', {}, h('span', { class: `cor-chip cor-${p.cor}`, texto: CORES[p.cor] ?? p.cor })),
    h('td', { class: 'num', texto: String(p.pontuacao) }),
    h('td', { class: 'col-motivos' },
      p.avisos_piora.map((a) => h('p', { class: 'piorou-texto', texto: `Piorou: ${a.motivo} · ${haMin(a.ha_min)}` })),
      p.reclassificado_ha_min !== null ? h('p', { class: 'dica', texto: `Reclassificado ${haMin(p.reclassificado_ha_min)}` }) : null,
      h('ul', { class: 'motivos-fila' }, p.motivos.map((m) => h('li', { texto: m })))),
    h('td', { texto: `${p.espera_min} min` }),
    h('td', { class: 'col-acoes' }, h('div', { class: 'acoes' }, acoes)));
}

function resumoFila(pacientes) {
  const porCor = {};
  for (const p of pacientes) porCor[p.cor] = (porCor[p.cor] || 0) + 1;
  return Object.keys(CORES).filter((c) => porCor[c]).map((c) => h('span', { class: `cor-chip cor-${c}`, texto: `${CORES[c]} · ${porCor[c]}` }));
}

function cartaoProximo(p) {
  return h('div', { class: `proximo borda-${p.cor}` },
    h('div', { class: 'proximo-quem' },
      h('span', { class: 'rotulo-secao', texto: 'Próximo a chamar' }),
      h('span', { class: 'numero-grande', texto: numeroFila(p.numero) }),
      h('span', { class: `cor-chip cor-${p.cor}`, texto: CORES[p.cor] ?? p.cor }),
      h('span', { class: 'dica', texto: `esperando há ${p.espera_min} min` })),
    h('button', { type: 'button', class: 'pilula enorme', texto: `Chamar ${numeroFila(p.numero)}`, onclick: () => chamarPaciente(p.numero) }),
    h('p', { class: 'dica proximo-nota', texto: 'Ao chamar, o paciente já é marcado como atendido e sai da fila.' }));
}

function listaRecemChamados(lista) {
  if (!lista.length) return [];
  return [h('h3', { texto: 'Chamados há pouco' }),
    h('ul', { class: 'recem' }, lista.map((c) => h('li', {},
      h('span', { class: `cor-chip cor-${c.cor}`, texto: numeroFila(c.numero) }),
      h('span', { texto: `chamado ${haMin(c.ha_min)}${c.chamado_por ? ` por ${c.chamado_por}` : ''} · atendido` }),
      h('button', { type: 'button', class: 'pilula secundaria', texto: 'Desfazer', title: 'Volta para a fila, na mesma posição', onclick: () => acaoFila('/api/fila/devolver', c.numero) })))),
    h('p', { class: 'dica', texto: 'Clicou no paciente errado? "Desfazer" devolve para a fila com o mesmo número e QR. Vale por 10 minutos.' })];
}

// `automatico`: chamada feita pelo relógio da página. O servidor não conta como uso da sessão,
// para o login expirar se o computador ficar parado.
async function carregarFila(automatico = false) {
  let dados;
  try {
    dados = await (await fetch('/api/fila', automatico ? { headers: { 'X-Salus-Automatico': '1' } } : undefined)).json();
  } catch (e) {
    $('#lista-fila').replaceChildren(h('p', { class: 'dica', texto: `Não foi possível carregar a fila (${e.message}).` }));
    return;
  }
  mostrarAvisos(dados.avisos);
  const pacientes = dados.pacientes;
  $('#contador-fila').textContent = String(pacientes.length);
  $('#aviso-paciente').textContent = dados.pagina_paciente
    ? 'Página do paciente ligada: cada paciente recebe um QR para acompanhar a fila pelo celular, no Wi-Fi da unidade.'
    : 'Página do paciente desligada: a fila funciona, mas sem QR.';
  $('#resumo-fila').replaceChildren(h('span', { class: 'total-fila', texto: pacientes.length === 1 ? '1 pessoa aguardando' : `${pacientes.length} pessoas aguardando` }), ...resumoFila(pacientes));
  $('#proximo-fila').replaceChildren(...(pacientes.length ? [cartaoProximo(pacientes[0])] : []));
  $('#lista-fila').replaceChildren(pacientes.length
    ? h('table', { class: 'tabela-fila' },
      h('thead', {}, h('tr', {}, ['Posição', 'Número', 'Cor', 'Pontuação', 'Motivo', 'Espera', 'Ações'].map((t) => h('th', { texto: t })))),
      h('tbody', {}, pacientes.map(linhaFila)))
    : h('p', { class: 'vazio-fila', texto: 'Ninguém na fila. Depois da triagem, clique em "Colocar na fila".' }));
  $('#recem-chamados').replaceChildren(...listaRecemChamados(dados.recem_chamados || []));
}

/* ---------------------------------------------------------------- início */

function textoExtrator() {
  const e = $('#extrator').value;
  $('#dica-extrator').textContent = e === 'mock'
    ? 'Leitura do relato por palavras-chave, sem rede e na hora.'
    : 'Ao clicar em "Analisar", o relato é lido pelo modelo local (Ollama); pode levar de 10 a 120 segundos na primeira vez. Enquanto você preenche, as pendências usam a leitura por palavras-chave. Se o modelo estiver fora do ar, a análise sai só com as respostas diretas.';
}

async function iniciar() {
  try {
    const [rq, re] = await Promise.all([fetch('/api/questionario'), fetch('/api/exemplos')]);
    estado.dados = await rq.json();
    estado.exemplos = await re.json();
  } catch (e) {
    $('#painel').replaceChildren(h('div', { class: 'cartao erro-cartao' }, h('p', { texto: `Não foi possível carregar o questionário: ${e.message}` })));
    $('#passo-ficha').hidden = true;
    $('#passo-analise').hidden = false;
    return;
  }
  const q = estado.dados;
  if (!q.historico) q.historico = { ligado: false, exemplos: [] };
  try {
    const eu = await (await fetch('/api/eu')).json();
    if (eu && eu.login) { $('#usuario-nome').textContent = eu.nome; $('#usuario').hidden = false; }
  } catch (e) { /* sem login (modo de teste): nada a mostrar */ }
  $('#selo-regras').textContent = q.regras.validado ? 'regras validadas' : 'regras não validadas';
  $('#selo-versao').textContent = `questionário ${q.versao}`;
  $('#extrator').replaceChildren(...q.extratores.map((e) => h('option', { value: e, texto: e === 'mock' ? 'Palavras-chave (mock)' : 'Modelo local (Ollama)' })));
  $('#extrator').value = q.extrator_padrao;
  $('#exemplo').append(...estado.exemplos.map((x, i) => h('option', { value: String(i), texto: x.titulo + (x.falha_proposital ? ' (inválida de propósito)' : '') })));
  construirCadastro();
  construirPerguntas(q);
  textoExtrator();
  irParaPasso('ficha', true);

  $('#exemplo').addEventListener('change', (ev) => {
    if (ev.target.value === '') return;
    preencher(estado.exemplos[Number(ev.target.value)].ficha);
    calcular();
  });
  $('#limpar').addEventListener('click', () => { novaFicha(); window.scrollTo({ top: 0 }); });
  $('#mini').addEventListener('click', analisar);
  $('#passo-1').addEventListener('click', () => { if (estado.passo !== 'ficha') voltarParaFicha(); });
  $('#passo-2').addEventListener('click', () => { if (estado.passo !== 'analise') analisar(); });
  $('#extrator').addEventListener('change', textoExtrator);

  document.addEventListener('keydown', teclaDeVoz);
  $('#aba-triagem').addEventListener('click', () => mostrarTela('triagem'));
  $('#aba-fila').addEventListener('click', () => mostrarTela('fila'));
  $('#qr-fechar').addEventListener('click', (ev) => {
    const destino = ev.target.dataset.destino;
    $('#janela-qr').close();
    if (destino === 'fila') mostrarTela('fila');
  });
  $('#qr-nova').addEventListener('click', () => {
    $('#janela-qr').close();
    mostrarTela('triagem');
    window.scrollTo({ top: 0 });
  });
  carregarFila();
  setInterval(() => { if (!document.hidden) carregarFila(true); }, 5000);
}

iniciar();
