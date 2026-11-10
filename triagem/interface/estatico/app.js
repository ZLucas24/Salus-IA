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

const estado = { dados: null, exemplos: [], campos: {}, perguntas: {}, modulos: {}, seq: 0, timer: null, saida: null, reclassificando: null };

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
  $('#cadastro').replaceChildren(h('section', { class: 'cartao' }, h('h2', { texto: 'Cadastro e aferições' }),
    h('p', { class: 'dica', texto: 'Só a idade é obrigatória. Aferição não feita fica em branco e nunca vale como normal.' }),
    h('div', { class: 'grade' }, campos)));
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

/* ---------------------------------------------------------------- chamada ao servidor */

function agendar() {
  const painel = $('#painel');
  const auto = $('#auto').checked && $('#extrator').value === 'mock';
  clearTimeout(estado.timer);
  if (auto) { estado.timer = setTimeout(calcular, 250); return; }
  if (painel.querySelector('.cor-cartao')) painel.dataset.desatualizado = '1';
  atualizarAviso();
}

function atualizarAviso() {
  const painel = $('#painel');
  const antigo = painel.querySelector('.desatualizado');
  if (antigo) antigo.remove();
  if (painel.dataset.desatualizado === '1') {
    painel.prepend(h('p', { class: 'provisoria desatualizado', texto: 'Há alterações ainda não analisadas. Clique em "Analisar".' }));
  }
}

async function calcular() {
  const ficha = lerFicha();
  const painel = $('#painel');
  const minha = ++estado.seq;
  if (ficha.dados_atendente.idade === undefined) {
    estado.saida = null;
    renderVoz();
    painel.dataset.desatualizado = '';
    painel.replaceChildren(h('div', { class: 'cartao vazio' }, h('p', { texto: 'Preencha a idade para ver a triagem.' })));
    limparMarcas();
    atualizarMini(null);
    return;
  }
  painel.classList.add('carregando');
  try {
    const r = await fetch('/api/triagem', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ficha, extrator: $('#extrator').value }),
    });
    const corpo = await r.json();
    if (minha !== estado.seq) return;
    painel.dataset.desatualizado = '';
    if (r.status === 200) mostrarSaida(corpo.saida); else mostrarErros(corpo.erros || ['erro desconhecido']);
  } catch (e) {
    if (minha === estado.seq) mostrarErros([`Não foi possível falar com o servidor local (${e.message}). Ele ainda está rodando?`]);
  } finally {
    if (minha === estado.seq) painel.classList.remove('carregando');
  }
}

/* ---------------------------------------------------------------- resultado */

function limparMarcas() {
  for (const c of Object.values(estado.perguntas)) {
    c.el.classList.remove('pendente', 'proxima', 'inativa'); c.selo.hidden = true; c.nota.hidden = true;
  }
  for (const m of Object.values(estado.modulos)) m.ativo.hidden = true;
}

function irParaPergunta(id) {
  const c = estado.perguntas[id];
  if (!c) return;
  const det = c.el.closest('details');
  if (det) det.open = true;
  c.el.scrollIntoView({ behavior: 'smooth', block: 'center' });
  const foco = c.el.querySelector('input, select, button');
  if (foco) foco.focus({ preventScroll: true });
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

function secao(titulo, ...filhos) { return h('section', { class: 'cartao' }, h('h3', { texto: titulo }), ...filhos); }

function mostrarErros(erros) {
  limparMarcas();
  atualizarMini(null);
  $('#painel').replaceChildren(h('section', { class: 'cartao erro-cartao', role: 'alert' },
    h('h3', { texto: 'Ficha inválida' }), h('p', { texto: 'Corrija o que está abaixo para ver a triagem:' }),
    h('ul', {}, erros.map((e) => h('li', { texto: e })))));
}

function linhaSinal(x) {
  const extras = [];
  if (x.valor !== null && x.valor !== undefined) extras.push(`valor: ${x.valor}`);
  if (x.itens && x.itens.length) extras.push(x.itens.join(', '));
  if (x.status_no_relato) extras.push(`o relato dizia: ${STATUS[x.status_no_relato].toLowerCase()}`);
  if (x.trecho) extras.push(`trecho: “${x.trecho}”`);
  return h('li', {}, h('span', { class: 'nome', texto: nomeSinal(x.nome) }),
    h('span', { class: 'chip neutro', texto: ORIGEM[x.origem] ?? x.origem }),
    extras.length ? h('span', { class: 'detalhe', texto: extras.join(' · ') }) : null);
}

function atualizarMini(c) {
  const mini = $('#mini');
  if (!c) { mini.hidden = true; return; }
  mini.hidden = false;
  mini.className = `mini cor-${c.cor}`;
  mini.textContent = `${c.cor.toUpperCase()} · ${c.pontuacao}/100 · ver resultado`;
}

function mostrarSaida(s) {
  estado.saida = s;
  marcarPerguntas(s);
  const c = s.classificacao;
  atualizarMini(c);
  const painel = $('#painel');
  const cartoes = [];

  cartoes.push(h('section', { class: 'cartao cor-cartao' },
    h('div', { class: 'cor-linha' },
      h('span', { class: `cor-selo cor-${c.cor}`, texto: `Cor sugerida: ${c.cor}` }),
      h('span', { class: 'nota' }, String(c.pontuacao), h('small', { texto: ' / 100 dentro da cor' }))),
    h('div', { class: `medidor cor-${c.cor}`, role: 'img', 'aria-label': `Pontuação ${c.pontuacao} de 100` }, h('span', { style: `width:${c.pontuacao}%` })),
    h('p', { class: 'provisoria', texto: `Sugestão provisória. ${c.regras_validadas ? '' : 'As regras ainda não foram validadas por profissional de saúde. '}A decisão final é do profissional.` }),
    estado.reclassificando
      ? h('div', { class: 'controles' },
        h('button', { type: 'button', class: 'pilula', texto: `Atualizar classificação do ${numeroFila(estado.reclassificando.numero)}`, onclick: (ev) => atualizarReclassificacao(ev.target, false) }),
        h('span', { class: 'dica', texto: `Cor atual na fila: ${CORES[estado.reclassificando.cor] ?? estado.reclassificando.cor}. Mantém número, QR e hora de chegada.` }))
      : h('div', { class: 'controles' }, h('button', { type: 'button', class: 'pilula', texto: 'Colocar na fila', onclick: colocarNaFila }),
        h('span', { class: 'dica', texto: 'Gera o número de atendimento e o QR do paciente.' }))));

  if (s.proxima_pergunta) {
    const p = estado.dados.perguntas.find((x) => x.id === s.proxima_pergunta);
    cartoes.push(h('div', { class: 'proxima-pergunta' }, h('strong', { texto: 'Próxima pergunta:' }),
      h('button', { type: 'button', onclick: () => irParaPergunta(p.id), texto: `${p.id} · ${p.texto}` })));
  }

  if (s.alertas.length) {
    const ordem = { grave: 0, atencao: 1, info: 2 };
    const lista = [...s.alertas].sort((a, b) => ordem[(ALERTAS[a.codigo] || [, 'info'])[1]] - ordem[(ALERTAS[b.codigo] || [, 'info'])[1]]);
    cartoes.push(secao(`Alertas (${s.alertas.length})`, h('ul', { class: 'alertas' }, lista.map((a) => {
      const [nome, nivel] = ALERTAS[a.codigo] || [humanizar(a.codigo), 'info'];
      return h('li', { class: `alerta ${nivel}` }, h('span', { class: 'cod', texto: nome }), h('span', { texto: a.mensagem }));
    }))));
  }

  const pend = s.perguntas_pendentes;
  cartoes.push(secao(`Perguntas pendentes (${pend.length})`,
    pend.length ? h('div', { class: 'chips' }, pend.map((id) => h('button', { type: 'button', class: 'chip alerta-chip', onclick: () => irParaPergunta(id), texto: id })))
      : h('p', { class: 'dica', texto: 'Nenhuma pergunta pendente.' }),
    s.afericoes_faltando.length ? h('p', { class: 'dica', texto: `Aferições não registradas: ${s.afericoes_faltando.join(', ')} (valem como “não aferidas”).` }) : null));

  const al = s.alergias;
  cartoes.push(secao('Alergias', h('p', {}, h('strong', { texto: STATUS[al.status] }),
    al.itens.length ? ` — ${al.itens.join(', ')}` : '', al.tipos.length ? ` (${al.tipos.map(rotulo).join(', ')})` : ''),
  h('p', { class: 'dica', texto: 'Informação de segurança para a equipe; não entra na pontuação.' })));

  const ext = [];
  if (s.queixa_principal) ext.push(h('p', {}, h('strong', { texto: 'Queixa: ' }), s.queixa_principal));
  if (s.queixas.length) ext.push(h('div', { class: 'chips' }, s.queixas.map((q) => h('span', { class: 'chip', texto: humanizar(q) }))));
  if (s.duracao) ext.push(h('p', {}, h('strong', { texto: 'Duração: ' }), `${s.duracao.valor} ${s.duracao.unidade}`));
  ext.push(h('p', { class: 'dica', texto: `Leitura do relato: ${s.extrator}` }));
  cartoes.push(secao('Relato e duração', ...ext));

  const presentes = s.sinais.filter((x) => x.status === 'presente');
  const negados = s.sinais.filter((x) => x.status === 'negado');
  const desconhecidos = s.sinais.filter((x) => ['nao_sabe', 'recusou', 'incerto'].includes(x.status));
  cartoes.push(secao(`Sinais presentes (${presentes.length})`,
    presentes.length ? h('ul', { class: 'lista-sinais' }, presentes.map(linhaSinal)) : h('p', { class: 'dica', texto: 'Nenhum sinal presente até agora.' }),
    desconhecidos.length ? h('div', {}, h('p', { class: 'rotulo-secao', texto: 'Sem resposta definitiva (não valem como “não”)' }),
      h('ul', { class: 'lista-sinais' }, desconhecidos.map((x) => { const li = linhaSinal(x); li.prepend(h('span', { class: 'chip alerta-chip', texto: STATUS[x.status] })); return li; }))) : null,
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

  painel.replaceChildren(...cartoes);
  renderVoz();
}

/* ---------------------------------------------------------------- entrevista por voz */
// O enfermeiro fala; o servidor transcreve na máquina e interpreta por código. Nada entra na
// ficha sem o enfermeiro clicar em "Confirmar". Ordem: segurança -> relato -> pendências.

const voz = { pulados: new Set(), chave: null, gravador: null, pedacos: [], ocupado: false, resultado: null, limite: null };
const FASES = ['Perguntas de segurança', 'Relato do paciente', 'Perguntas complementares'];

function partesPendentes(id) {
  const c = estado.perguntas[id];
  if (!c || c.temMarcador()) return [];
  return Object.values(c.partes).filter(({ parte, get }) => {
    const dep = parte.depende_de;
    if (dep && c.partes[dep.parte].get() !== dep.igual) return false;
    return get() === undefined;
  }).map((i) => i.parte.nome);
}

function proximoPasso() {
  const q = estado.dados;
  const fases = [
    q.perguntas.filter((p) => p.obrigatoriedade === 'S').map((p) => p.id),
    ['Q01'],
    estado.saida ? estado.saida.perguntas_pendentes : [],
  ];
  for (const [fase, ids] of fases.entries()) {
    for (const id of ids) {
      if (estado.perguntas[id].el.classList.contains('inativa')) continue; // não se aplica ao paciente
      for (const parte of partesPendentes(id)) {
        if (!voz.pulados.has(`${id}.${parte}`)) return { fase, id, parte };
      }
    }
  }
  return null;
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

async function alternarGravacao() {
  if (voz.gravador && voz.gravador.state === 'recording') { voz.gravador.stop(); return; }
  let fluxo;
  try {
    fluxo = await navigator.mediaDevices.getUserMedia({ audio: true });
  } catch (e) {
    voz.resultado = { erro: `Não foi possível usar o microfone (${e.message}). Autorize o microfone no navegador.` };
    renderVoz();
    return;
  }
  const passo = voz.passo;
  const rec = new MediaRecorder(fluxo);
  voz.pedacos = [];
  rec.ondataavailable = (ev) => { if (ev.data.size) voz.pedacos.push(ev.data); };
  rec.onstop = () => {
    fluxo.getTracks().forEach((t) => t.stop());
    clearTimeout(voz.limite);
    const blob = new Blob(voz.pedacos, { type: rec.mimeType || 'audio/webm' });
    voz.pedacos = [];
    enviarAudio(passo, blob);
  };
  voz.gravador = rec;
  voz.resultado = null;
  rec.start();
  const parte = estado.perguntas[passo.id].partes[passo.parte].parte;
  voz.limite = setTimeout(() => { if (rec.state === 'recording') rec.stop(); }, parte.forma === 'texto' ? 90000 : 20000);
  renderVoz();
}

async function enviarAudio(passo, blob) {
  voz.ocupado = true;
  renderVoz();
  try {
    const r = await fetch(`/api/voz?pergunta=${encodeURIComponent(passo.id)}&parte=${encodeURIComponent(passo.parte)}`,
      { method: 'POST', headers: { 'Content-Type': blob.type || 'audio/webm' }, body: blob });
    const corpo = await r.json();
    voz.resultado = r.status === 200 ? { ...corpo, passo } : { erro: (corpo.erros || ['erro desconhecido']).join('; ') };
  } catch (e) {
    voz.resultado = { erro: `Não foi possível falar com o servidor local (${e.message}).` };
  } finally {
    voz.ocupado = false;
    renderVoz();
  }
}

async function confirmarVoz(valor) {
  const { passo } = voz.resultado;
  aplicarValor(passo.id, passo.parte, valor);
  voz.resultado = null;
  await calcular(); // recalcula na hora: alerta de sinal grave aparece já
  renderVoz();
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
    caixa.replaceChildren(titulo, h('p', { class: 'dica', texto: 'Preencha a idade e as aferições no cadastro abaixo para começar. Depois, a entrevista segue por voz: segurança, relato e perguntas complementares.' }));
    return;
  }
  const filhos = [titulo];
  const graves = (estado.saida ? estado.saida.alertas : []).filter((a) => a.codigo === 'sinal_de_alerta');
  if (graves.length) {
    filhos.push(h('div', { class: 'alerta grave', role: 'alert' }, h('span', { class: 'cod', texto: 'Sinal de alerta' }),
      graves.map((a) => h('span', { texto: a.mensagem }))));
  }
  const passo = proximoPasso();
  const chave = passo ? `${passo.id}.${passo.parte}` : null;
  if (chave !== voz.chave) { voz.chave = chave; if (voz.resultado && voz.resultado.erro) voz.resultado = null; }
  voz.passo = passo;
  if (!passo) {
    filhos.push(h('p', { texto: 'Entrevista por voz concluída. Revise a ficha e clique em "Colocar na fila".' }));
    if (voz.pulados.size) filhos.push(h('button', { type: 'button', class: 'pilula secundaria', texto: `Voltar às ${voz.pulados.size} pulada(s)`, onclick() { voz.pulados.clear(); renderVoz(); } }));
    caixa.replaceChildren(...filhos);
    return;
  }
  const p = estado.dados.perguntas.find((x) => x.id === passo.id);
  const parte = p.partes.find((x) => x.nome === passo.parte);
  const gravando = voz.gravador && voz.gravador.state === 'recording';
  filhos.push(
    h('p', { class: 'rotulo-secao', texto: `Etapa ${passo.fase + 1} de 3 · ${FASES[passo.fase]}` }),
    h('div', { class: 'voz-pergunta' }, h('span', { class: 'id', texto: p.id }),
      h('div', {}, h('p', { class: 'texto', texto: p.texto }),
        p.partes.length > 1 ? h('p', { class: 'parte-voz', texto: `Agora: ${PARTES[parte.nome] ?? humanizar(parte.nome)}` }) : null,
        h('p', { class: 'dica', texto: dicaDaParte(parte) }))),
    h('div', { class: 'controles' },
      h('button', { type: 'button', class: 'pilula gravar', 'aria-pressed': String(gravando), disabled: voz.ocupado,
        texto: gravando ? '■ Parar e transcrever' : '● Gravar resposta', onclick: alternarGravacao }),
      h('button', { type: 'button', class: 'pilula secundaria', texto: 'Pular', disabled: gravando || voz.ocupado,
        onclick() { voz.pulados.add(chave); voz.resultado = null; renderVoz(); } }),
      h('button', { type: 'button', class: 'pilula secundaria', texto: 'Responder na ficha', onclick: () => irParaPergunta(p.id) })));
  if (gravando) filhos.push(h('p', { class: 'gravando', texto: 'Gravando… fale a resposta e clique em "Parar".' }));
  if (voz.ocupado) filhos.push(h('p', { class: 'dica', texto: 'Transcrevendo nesta máquina…' }));
  const r = voz.resultado;
  if (r && r.erro) filhos.push(h('p', { class: 'alerta atencao', texto: r.erro }));
  else if (r && r.passo && `${r.passo.id}.${r.passo.parte}` === chave) {
    const ouvi = h('p', {}, h('strong', { texto: 'Ouvi: ' }), `“${r.transcricao || '(nada)'}”`);
    if (r.entendido && parte.forma === 'texto') {
      const area = h('textarea', { rows: '4', maxlength: String(parte.max_caracteres ?? 1000), 'aria-label': 'Texto transcrito' });
      area.value = r.valor;
      filhos.push(h('div', { class: 'voz-resultado' }, ouvi, area,
        h('div', { class: 'controles' }, h('button', { type: 'button', class: 'pilula', texto: 'Confirmar', onclick: () => confirmarVoz(area.value.trim()) }),
          h('button', { type: 'button', class: 'pilula secundaria', texto: 'Gravar de novo', onclick: alternarGravacao }))));
    } else if (r.entendido) {
      filhos.push(h('div', { class: 'voz-resultado' }, ouvi, h('p', { class: 'entendi' }, h('strong', { texto: 'Entendi: ' }), textoDoValor(r.valor)),
        h('div', { class: 'controles' }, h('button', { type: 'button', class: 'pilula', texto: 'Confirmar', onclick: () => confirmarVoz(r.valor) }),
          h('button', { type: 'button', class: 'pilula secundaria', texto: 'Gravar de novo', onclick: alternarGravacao }))));
    } else {
      filhos.push(h('div', { class: 'voz-resultado' }, ouvi,
        h('p', { class: 'alerta atencao', texto: `Não entendi (${r.motivo}). Grave de novo ou responda na ficha.` })));
    }
  }
  caixa.replaceChildren(...filhos);
}

/* ---------------------------------------------------------------- fila e QR */

const CORES = { vermelho: 'Vermelho', laranja: 'Laranja', amarelo: 'Amarelo', verde: 'Verde', azul: 'Azul' };
const numeroFila = (n) => String(n).padStart(3, '0');

async function postar(url, corpo) {
  const r = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(corpo) });
  return { status: r.status, corpo: await r.json() };
}

async function colocarNaFila(ev) {
  const botao = ev.target;
  botao.disabled = true;
  try {
    // o servidor processa a ficha de novo: a cor nunca sai do navegador
    const { status, corpo } = await postar('/api/fila', { ficha: lerFicha(), extrator: $('#extrator').value });
    if (status !== 200) { mostrarErros(corpo.erros || ['erro desconhecido']); return; }
    mostrarQR(corpo, true);
    carregarFila();
  } catch (e) {
    mostrarErros([`Não foi possível falar com o servidor local (${e.message}).`]);
  } finally {
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
  $('#qr-nova').hidden = !nova;
  $('#janela-qr').showModal();
}

/* reclassificação: a ficha guardada volta para a aba Triagem; o paciente mantém número e QR */

function novaFicha() {
  estado.reclassificando = null;
  renderModo();
  voz.pulados.clear(); voz.resultado = null;
  preencher({}); $('#exemplo').value = ''; $('#painel').dataset.desatualizado = ''; calcular();
}

function renderModo() {
  const caixa = $('#modo-reclass');
  const r = estado.reclassificando;
  caixa.hidden = !r;
  if (!r) { caixa.replaceChildren(); return; }
  caixa.replaceChildren(
    h('span', {}, h('strong', { texto: `Reclassificando o paciente ${numeroFila(r.numero)}` }),
      ` · cor atual na fila: ${CORES[r.cor] ?? r.cor}. Ajuste a ficha e clique em "Atualizar classificação".`),
    h('button', { type: 'button', class: 'pilula secundaria', texto: 'Cancelar', onclick: novaFicha }));
}

async function iniciarReclassificacao(numero) {
  const { status, corpo } = await postar('/api/fila/ficha', { numero });
  if (status !== 200) { carregarFila(); return; }
  if (!corpo.ficha) {
    window.alert('Este paciente entrou na fila antes da reclassificação existir: a ficha não foi guardada. Faça uma nova triagem.');
    return;
  }
  estado.reclassificando = { numero, cor: corpo.cor };
  voz.pulados.clear(); voz.resultado = null;
  $('#exemplo').value = '';
  if (corpo.extrator && [...$('#extrator').options].some((o) => o.value === corpo.extrator)) { $('#extrator').value = corpo.extrator; textoExtrator(); }
  preencher(corpo.ficha);
  mostrarTela('triagem');
  renderModo();
  window.scrollTo({ top: 0 });
  calcular();
}

async function atualizarReclassificacao(botao, confirmar) {
  const r = estado.reclassificando;
  botao.disabled = true;
  try {
    const { status, corpo } = await postar('/api/fila/reclassificar',
      { numero: r.numero, ficha: lerFicha(), extrator: $('#extrator').value, confirmar_reducao: confirmar });
    if (status === 409) {
      const ok = window.confirm(`A cor do paciente ${numeroFila(r.numero)} baixaria de ${CORES[corpo.cor_antes]} para ${CORES[corpo.cor_depois]}.\n\nConfirma que o paciente melhorou e a prioridade deve baixar?`);
      if (ok) await atualizarReclassificacao(botao, true);
      return;
    }
    if (status !== 200) { mostrarErros(corpo.erros || ['erro desconhecido']); return; }
    $('#titulo-qr').textContent = 'Classificação atualizada';
    $('#qr-numero').textContent = numeroFila(corpo.numero);
    $('#qr-imagem').hidden = true;
    $('#qr-texto').textContent = corpo.cor_antes === corpo.cor_depois
      ? `Cor mantida: ${CORES[corpo.cor_depois]} (pontuação ${corpo.pontuacao_antes} → ${corpo.pontuacao_depois}).`
      : `Cor: ${CORES[corpo.cor_antes]} → ${CORES[corpo.cor_depois]}. O QR do paciente já mostra a nova classificação.`;
    $('#qr-url').textContent = '';
    $('#qr-nova').hidden = true;
    $('#janela-qr').showModal();
    novaFicha();
    mostrarTela('fila');
  } catch (e) {
    mostrarErros([`Não foi possível falar com o servidor local (${e.message}).`]);
  } finally {
    botao.disabled = false;
  }
}

function mostrarTela(qual) {
  const fila = qual === 'fila';
  $('#tela-triagem').hidden = fila;
  $('#tela-fila').hidden = !fila;
  $('#aba-triagem').setAttribute('aria-pressed', String(!fila));
  $('#aba-fila').setAttribute('aria-pressed', String(fila));
  if (fila) carregarFila();
}

async function acaoFila(rota, numero) {
  try {
    const { status, corpo } = await postar(rota, { numero });
    if (rota === '/api/fila/qr' && status === 200) mostrarQR(corpo, false);
  } finally {
    carregarFila();
  }
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

function linhaFila(p) {
  const acoes = [];
  if (p.avisos_piora.length) acoes.push(h('button', { type: 'button', class: 'pilula', texto: 'Vi o aviso', onclick: () => acaoFila('/api/fila/aviso-visto', p.numero) }));
  if (p.estado === 'aguardando') acoes.push(h('button', { type: 'button', class: 'pilula', texto: 'Chamar', onclick: () => acaoFila('/api/fila/chamar', p.numero) }));
  acoes.push(h('button', { type: 'button', class: 'pilula secundaria', texto: 'Reclassificar', onclick: () => iniciarReclassificacao(p.numero) }));
  acoes.push(h('button', { type: 'button', class: 'pilula secundaria', texto: 'Atendido', onclick: () => acaoFila('/api/fila/concluir', p.numero) }));
  acoes.push(h('button', { type: 'button', class: 'pilula secundaria', texto: 'Ver QR', onclick: () => acaoFila('/api/fila/qr', p.numero) }));
  return h('tr', { class: [p.estado === 'chamado' ? 'chamado' : '', p.avisos_piora.length ? 'piorou' : ''].join(' ').trim() },
    h('td', { class: 'num', texto: p.posicao ? `${p.posicao}º` : 'chamado' }),
    h('td', { class: 'num', texto: numeroFila(p.numero) }),
    h('td', {}, h('span', { class: `cor-chip cor-${p.cor}`, texto: CORES[p.cor] ?? p.cor })),
    h('td', { class: 'num', texto: String(p.pontuacao) }),
    h('td', { class: 'col-motivos' },
      p.avisos_piora.map((a) => h('p', { class: 'piorou-texto', texto: `Piorou: ${a.motivo} · ${a.ha_min ? `há ${a.ha_min} min` : 'agora'}` })),
      p.reclassificado_ha_min !== null ? h('p', { class: 'dica', texto: `Reclassificado ${p.reclassificado_ha_min ? `há ${p.reclassificado_ha_min} min` : 'agora'}` }) : null,
      h('ul', { class: 'motivos-fila' }, p.motivos.map((m) => h('li', { texto: m })))),
    h('td', { texto: `${p.espera_min} min` }),
    h('td', { class: 'col-acoes' }, h('div', { class: 'acoes' }, acoes)));
}

async function carregarFila() {
  let dados;
  try {
    dados = await (await fetch('/api/fila')).json();
  } catch (e) {
    $('#lista-fila').replaceChildren(h('p', { class: 'dica', texto: `Não foi possível carregar a fila (${e.message}).` }));
    return;
  }
  mostrarAvisos(dados.avisos);
  const aguardando = dados.pacientes.filter((p) => p.estado === 'aguardando').length;
  $('#contador-fila').textContent = String(aguardando);
  $('#aviso-paciente').textContent = dados.pagina_paciente
    ? 'Página do paciente ligada: cada paciente recebe um QR para acompanhar a fila pelo celular, no Wi-Fi da unidade.'
    : 'Página do paciente desligada: a fila funciona, mas sem QR.';
  $('#lista-fila').replaceChildren(dados.pacientes.length
    ? h('table', { class: 'tabela-fila' },
      h('thead', {}, h('tr', {}, ['Posição', 'Número', 'Cor', 'Pontuação', 'Motivo', 'Espera', 'Ações'].map((t) => h('th', { texto: t })))),
      h('tbody', {}, dados.pacientes.map(linhaFila)))
    : h('p', { class: 'dica', texto: 'Ninguém na fila. Depois da triagem, clique em "Colocar na fila".' }));
}

/* ---------------------------------------------------------------- início */

function textoExtrator() {
  const e = $('#extrator').value;
  $('#dica-extrator').textContent = e === 'mock'
    ? 'Leitura por palavras-chave, sem rede. Atualiza enquanto você digita.'
    : 'Usa o modelo local (Ollama). Pode levar de 10 a 120 segundos na primeira vez; clique em "Analisar". Se o modelo estiver fora do ar, a ficha sai só com as respostas diretas.';
  $('#auto').disabled = e !== 'mock';
}

async function iniciar() {
  try {
    const [rq, re] = await Promise.all([fetch('/api/questionario'), fetch('/api/exemplos')]);
    estado.dados = await rq.json();
    estado.exemplos = await re.json();
  } catch (e) {
    $('#painel').replaceChildren(h('div', { class: 'cartao erro-cartao' }, h('p', { texto: `Não foi possível carregar o questionário: ${e.message}` })));
    return;
  }
  const q = estado.dados;
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
  renderVoz();

  $('#exemplo').addEventListener('change', (ev) => {
    if (ev.target.value === '') return;
    preencher(estado.exemplos[Number(ev.target.value)].ficha);
    calcular();
  });
  $('#limpar').addEventListener('click', novaFicha);
  $('#analisar').addEventListener('click', () => { clearTimeout(estado.timer); calcular(); });
  $('#extrator').addEventListener('change', () => { textoExtrator(); agendar(); });
  $('#auto').addEventListener('change', agendar);

  $('#aba-triagem').addEventListener('click', () => mostrarTela('triagem'));
  $('#aba-fila').addEventListener('click', () => mostrarTela('fila'));
  $('#qr-fechar').addEventListener('click', () => $('#janela-qr').close());
  $('#qr-nova').addEventListener('click', () => {
    $('#janela-qr').close();
    novaFicha();
    window.scrollTo({ top: 0 });
  });
  carregarFila();
  setInterval(() => { if (!document.hidden) carregarFila(); }, 5000);
}

iniciar();
