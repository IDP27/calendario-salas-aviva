import { TYPES, clone, uid, isEmpty, validateData, validateValue, displayValue, queryRecords, toCSV } from './model.js';
import { repository } from './storage.js';

const $ = selector => document.querySelector(selector);
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const paths = {
  grid: '<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
  report: '<path d="M4 3v18h17M9 16v-5m5 5V7m5 9v-3"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  search: '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',
  columns: '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M9 4v16m6-16v16"/>',
  filter: '<path d="M4 7h16M7 12h10m-7 5h4"/>',
  download: '<path d="M12 3v12m-4-4 4 4 4-4M4 16v5h16v-5"/>',
  upload: '<path d="M12 16V4m-4 4 4-4 4 4M4 16v5h16v-5"/>',
  edit: '<path d="m15 4 5 5M4 20l5-1L21 7a2 2 0 0 0-5-5L4 14z"/>',
  eye: '<path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/>',
  trash: '<path d="M3 6h18M9 6V3h6v3M6 6l1 15h10l1-15M10 10v7m4-7v7"/>',
  check: '<path d="m5 12 4 4L19 6"/>',
  save: '<path d="M5 3h12l4 4v14H3V3zM7 3v6h10V3M7 21v-8h10v8"/>',
  exit: '<path d="M9 3H4v18h5m5-14 5 5-5 5m-5-5h12"/>',
  close: '<path d="m6 6 12 12M6 18 18 6"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  chevron: '<path d="m9 5 7 7-7 7"/>',
  print: '<path d="M7 8V3h10v5M7 17H3V8h18v9h-4M7 13h10v8H7z"/>',
  table: '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 9h18M9 9v11"/>'
};
const icon = name => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[name] || paths.table}</svg>`;
const button = (action, label, symbol, cls = 'btn', extra = '') => `<button type="button" class="${cls}" data-action="${action}" ${extra}>${symbol ? icon(symbol) : ''}${label}</button>`;
let data, saved, view = 'panel', page = 1, inline = false, dialogDirty = false, editorSave = null, columnDraft, columnDefaults = {}, toastTimer;
let chosenColumns = [], sumColumns = [];
const queries = { panel: { search: '', filters: [], from: '', to: '' }, reports: { search: '', filters: [], from: '', to: '' } };
let filtersOpen = false;
const dirty = () => data && JSON.stringify(data) !== JSON.stringify(saved);
const dateTime = value => new Date(value).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' });
function toast(message, error = false) {
  const el = $('#toast'); el.textContent = message; el.className = `visible ${error ? 'error' : ''}`;
  clearTimeout(toastTimer); toastTimer = setTimeout(() => el.className = '', error ? 9000 : 4500);
}
function showError(error) { toast(error.message || String(error), true); }
function saveAll() {
  for (const input of document.querySelectorAll('[data-cell]')) if (!input.reportValidity()) return false;
  try { repository.save(data); saved = clone(data); inline = false; toast('Alterações salvas.'); render(); return true; }
  catch (error) { showError(error); return false; }
}
function confirmAction(title, description, choices = [{ value: 'cancel', label: 'Cancelar' }, { value: 'confirm', label: 'Confirmar', cls: 'primary' }]) {
  return new Promise(resolve => {
    const dialog = $('#confirmation');
    dialog.innerHTML = `<div class="modal-head"><h2 id="confirmation-title">${esc(title)}</h2></div><p class="confirm-copy">${esc(description)}</p><div class="modal-actions">${choices.map(c => `<button class="btn ${c.cls || ''}" data-choice="${c.value}">${esc(c.label)}</button>`).join('')}</div>`;
    const finish = result => { dialog.close(); dialog.removeEventListener('cancel', cancel); resolve(result); };
    const cancel = event => { event.preventDefault(); finish('cancel'); };
    dialog.addEventListener('cancel', cancel);
    dialog.querySelectorAll('[data-choice]').forEach(el => el.onclick = () => finish(el.dataset.choice));
    dialog.showModal();
  });
}
async function guard(action) {
  if (!dirty()) { action(); return; }
  const choice = await confirmAction('Você tem alterações não salvas', 'Escolha o que fazer com o rascunho antes de continuar.', [
    { value: 'cancel', label: 'Continuar editando' }, { value: 'discard', label: 'Descartar' }, { value: 'save', label: 'Salvar e continuar', cls: 'primary' }
  ]);
  if (choice === 'discard') { data = clone(saved); inline = false; action(); }
  if (choice === 'save' && saveAll()) action();
}
function loginScreen() {
  $('#app').innerHTML = `<main class="login-shell"><section class="login-story"><a class="brand brand--rio" href="./" aria-label="Rio Quente — Painel de Registros"><img src="./assets/rio-quente-logo.png?v=2" alt="Rio Quente" width="447" height="447"></a><div class="login-copy"><div class="eyebrow">SEU ESPAÇO DE GESTÃO</div><h1>Clareza para<br>organizar.<br>Liberdade para<br><em>adaptar.</em></h1><p>Seus registros, suas colunas.<br>Um painel que acompanha o seu trabalho.</p></div><div class="story-footer">ORGANIZE · PERSONALIZE · ACOMPANHE <span>01 / 01</span></div></section><section class="login-main"><div class="login-form-wrap"><span class="tiny-label">BEM-VINDO AO PAINEL</span><h2>Seu trabalho,<br>em um só lugar.</h2><p class="muted">Entre para acessar seu painel de registros.</p><form id="login-form"><label>Usuário<input name="user" autocomplete="username" placeholder="Seu usuário" required autofocus></label><label>Senha<div class="password-field"><input name="password" type="password" autocomplete="current-password" placeholder="Sua senha" required><button type="button" class="icon-btn" id="toggle-password" aria-label="Mostrar senha">${icon('eye')}</button></div></label><p id="login-error" class="field-error" role="alert"></p><button class="btn primary login-submit" type="submit">Entrar no painel</button></form><div class="demo-credentials"><span class="demo-icon">${icon('grid')}</span><div><strong>Acesso de demonstração</strong><p>Usuário: <b>admin</b> <span>·</span> Senha: <b>admin123</b></p></div></div><p class="local-note">Os dados ficam salvos neste navegador.</p></div><footer>Painel de Registros <span>Ambiente local · v1.0</span></footer></section></main>`;
  $('#toggle-password').onclick = event => { const input = $('[name="password"]'); input.type = input.type === 'password' ? 'text' : 'password'; event.currentTarget.setAttribute('aria-label', input.type === 'password' ? 'Mostrar senha' : 'Ocultar senha'); };
  $('#login-form').onsubmit = event => {
    event.preventDefault();
    try { const fields = new FormData(event.target); repository.login(fields.get('user'), fields.get('password')); initialize(); }
    catch (error) { $('#login-error').textContent = error.message; }
  };
}
function initialize() {
  try {
    data = repository.load(); saved = clone(data); chosenColumns = data.columns.filter(c => !c.hidden).map(c => c.id); sumColumns = []; render();
  } catch (error) {
    $('#app').innerHTML = `<main class="recovery"><img class="recovery-logo" src="./assets/rio-quente-logo.png?v=2" alt="Rio Quente" width="447" height="447"><h1>Vamos recuperar seu painel</h1><p>${esc(error.message)}</p>${button('import', 'Importar backup JSON', 'upload', 'btn primary')}<p class="muted">O conteúdo existente será substituído somente após sua confirmação.</p></main>`;
  }
}
function control(column, value, attributes = '') {
  const common = `${attributes} ${column.required ? 'required' : ''}`;
  if (column.type === 'select' || column.type === 'boolean') {
    const options = column.type === 'boolean' ? [{ value: 'true', label: 'Sim' }, { value: 'false', label: 'Não' }] : column.options.map(v => ({ value: v, label: v }));
    return `<select ${common}><option value="">Selecione</option>${options.map(o => `<option value="${esc(o.value)}" ${!isEmpty(value) && String(value) === o.value ? 'selected' : ''}>${esc(o.label)}</option>`).join('')}</select>`;
  }
  if (column.type === 'longtext') return `<textarea rows="3" ${common}>${esc(value)}</textarea>`;
  return `<input type="${column.type === 'number' ? 'number' : column.type === 'date' ? 'date' : 'text'}" ${column.type === 'number' ? 'step="any"' : ''} value="${esc(value)}" ${common}>`;
}
function readControl(column, input) {
  if (input.value === '') return null;
  return column.type === 'number' ? input.valueAsNumber : column.type === 'boolean' ? input.value === 'true' : input.value;
}
function valueHTML(column, value) {
  const text = esc(displayValue(column, value));
  if (isEmpty(value)) return '<span class="muted">—</span>';
  if (column.type === 'select') return `<span class="tag ${value === 'Ativo' ? 'active' : value === 'Inativo' ? 'inactive' : ['Administrativo', 'Comercial', 'Financeiro', 'Operacional'].includes(value) ? 'category-' + column.options.indexOf(value) : 'neutral'}">${value === 'Ativo' || value === 'Inativo' ? '<i></i>' : ''}${text}</span>`;
  return text;
}
function filterMarkup() {
  const q = queries[view];
  return `<div class="filter-panel ${filtersOpen ? '' : 'hidden'}"><div class="date-filters"><label>Criado a partir de<input id="date-from" type="date" value="${esc(q.from)}"></label><label>Até<input id="date-to" type="date" value="${esc(q.to)}"></label>${button('add-filter', 'Adicionar condição', 'plus')}${button('clear-filters', 'Limpar filtros', null, 'btn text-btn')}</div>${q.filters.map((f, i) => {
    const column = data.columns.find(c => c.id === f.column);
    const operators = ['text', 'longtext'].includes(column.type) ? [['contains', 'Contém'], ['eq', 'É igual a']] : ['number', 'date'].includes(column.type) ? [['eq', 'É igual a'], ['gte', 'Maior ou igual a'], ['lte', 'Menor ou igual a']] : [['eq', 'É igual a']];
    operators.push(['empty', 'Está vazio'], ['filled', 'Está preenchido']);
    const inputColumn = { ...column, required: false, type: column.type === 'longtext' ? 'text' : column.type };
    return `<div class="filter-row"><select aria-label="Coluna da condição ${i + 1}" data-filter-column="${i}">${data.columns.map(c => `<option value="${c.id}" ${c.id === f.column ? 'selected' : ''}>${esc(c.name)}</option>`).join('')}</select><select aria-label="Operador da condição ${i + 1}" data-filter-operator="${i}">${operators.map(([value, label]) => `<option value="${value}" ${f.operator === value ? 'selected' : ''}>${label}</option>`).join('')}</select>${['empty', 'filled'].includes(f.operator) ? '<span></span>' : control(inputColumn, f.value, `id="filter-value-${i}" data-filter-value="${i}" aria-label="Valor da condição ${i + 1}"`)}${button('remove-filter', '', 'close', 'icon-btn', `data-index="${i}" aria-label="Remover condição ${i + 1}"`)}</div>`;
  }).join('')}</div>`;
}
function tableMarkup(rows, columns) {
  if (!columns.length) return '<div class="empty-state"><h3>Escolha as colunas do relatório</h3><p>Marque pelo menos uma coluna nas opções acima.</p></div>';
  if (!rows.length) return `<div class="empty-state">${icon('table')}<h3>${data.records.length ? 'Nenhum registro encontrado' : 'Seu painel está pronto para começar'}</h3><p>${data.records.length ? 'Ajuste a pesquisa ou os filtros para ver outros resultados.' : 'Insira seu primeiro registro e organize as informações do seu jeito.'}</p>${view === 'panel' ? button(data.records.length ? 'clear-filters' : 'insert', data.records.length ? 'Limpar pesquisa e filtros' : 'Inserir registro', 'plus', 'btn primary') : ''}</div>`;
  const slice = view === 'reports' ? rows : rows.slice((page - 1) * data.preferences.pageSize, page * data.preferences.pageSize);
  return `<div class="table-scroll"><table><caption class="sr-only">${view === 'reports' ? 'Resultados do relatório' : 'Lista de registros'}</caption><colgroup><col style="width:60px">${columns.map(c => `<col style="width:${c.width}px">`).join('')}${view === 'panel' ? '<col style="width:138px">' : ''}</colgroup><thead><tr><th scope="col" class="row-number">#</th>${columns.map(c => `<th scope="col" aria-sort="${data.preferences.sortColumn === c.id ? data.preferences.sortDirection === 'asc' ? 'ascending' : 'descending' : 'none'}"><button data-action="sort" data-id="${c.id}">${esc(c.name)}<span>${data.preferences.sortColumn === c.id ? data.preferences.sortDirection === 'asc' ? '↑' : '↓' : '↕'}</span></button></th>`).join('')}${view === 'panel' ? '<th scope="col" class="actions-cell">Ações</th>' : ''}</tr></thead><tbody>${slice.map((row, index) => `<tr><td class="row-number">${String((view === 'reports' ? 0 : (page - 1) * data.preferences.pageSize) + index + 1).padStart(2, '0')}</td>${columns.map((c, ci) => `<td class="${ci === 0 ? 'first-col' : ''} ${inline && view === 'panel' ? 'editable' : ''}">${inline && view === 'panel' ? control(c, row.values[c.id], `data-cell="${row.id}" data-column="${c.id}" aria-label="${esc(c.name)} do registro ${index + 1}"`) : `<div class="cell-value" title="${esc(displayValue(c, row.values[c.id]))}">${valueHTML(c, row.values[c.id])}</div>`}</td>`).join('')}${view === 'panel' ? `<td class="actions-cell"><div class="row-actions">${button('view', '', 'eye', 'icon-btn', `data-id="${row.id}" aria-label="Visualizar registro ${index + 1}"`)}${button('edit', '', 'edit', 'icon-btn', `data-id="${row.id}" aria-label="Editar registro ${index + 1}"`)}${button('delete', '', 'trash', 'icon-btn danger-icon', `data-id="${row.id}" aria-label="Excluir registro ${index + 1}"`)}</div></td>` : ''}</tr>`).join('')}</tbody></table></div>`;
}
function render(preserveFocus = false) {
  if (!repository.loggedIn()) { loginScreen(); return; }
  if (!data) { initialize(); return; }
  const focused = preserveFocus ? document.activeElement : null;
  const focusId = focused?.id, selectionStart = focused?.selectionStart, selectionEnd = focused?.selectionEnd;
  const q = queries[view]; let rows = [], queryError = '';
  try { rows = queryRecords(data, q); } catch (error) { queryError = error.message; }
  const columns = data.columns.filter(c => view === 'reports' ? chosenColumns.includes(c.id) : !c.hidden);
  const pages = Math.max(1, Math.ceil(rows.length / data.preferences.pageSize)); page = Math.min(page, pages);
  const updated = data.records.reduce((max, r) => r.updatedAt > max ? r.updatedAt : max, '');
  $('#app').innerHTML = `<div class="app-shell"><aside class="sidebar"><a class="brand brand--rio" href="./" data-action="home" aria-label="Rio Quente — início do painel"><img src="./assets/rio-quente-logo.png?v=2" alt="Rio Quente" width="447" height="447"></a><div class="workspace-picker"><div class="workspace-avatar">M</div><div><strong>Meu espaço</strong><small>Espaço pessoal</small></div><span class="workspace-caret">⌄</span></div><div class="nav-label">GERENCIAMENTO</div><nav aria-label="Navegação principal">${button('panel', 'Painel de registros', 'grid', `nav-item ${view === 'panel' ? 'selected' : ''}`, view === 'panel' ? 'aria-current="page"' : '')}${button('reports', 'Relatórios', 'report', `nav-item ${view === 'reports' ? 'selected' : ''}`, view === 'reports' ? 'aria-current="page"' : '')}</nav><div class="sidebar-bottom"><div class="local-card"><span class="local-icon">${icon('save')}</span><strong>Seu espaço, neste navegador</strong><p>Exporte um backup para guardar uma cópia dos seus dados.</p>${button('backup', 'Exportar backup', 'download', 'backup-link')}</div><div class="profile"><div class="avatar">AD</div><div><strong>Administrador</strong><small>Conta de demonstração</small></div>${button('logout', '', 'exit', 'icon-btn', 'aria-label="Sair do sistema"')}</div></div></aside><div class="workspace-main"><header class="topbar"><div class="breadcrumb">Meu espaço ${icon('chevron')} <strong>${view === 'panel' ? 'Painel de registros' : 'Relatórios'}</strong></div><div class="topbar-tools"><span class="environment"><i></i>Ambiente local</span><div class="compact-actions">${button('backup', '', 'download', 'icon-btn', 'aria-label="Exportar backup"')}${button('logout', '', 'exit', 'icon-btn', 'aria-label="Sair do sistema"')}</div></div></header><main class="main-content"><div class="page-heading"><div><div class="eyebrow">${view === 'panel' ? 'ORGANIZAÇÃO DO SEU JEITO' : 'DADOS QUE VIRAM INFORMAÇÃO'}</div><h1>${view === 'panel' ? 'Painel de registros' : 'Relatórios'}</h1><p class="muted">${view === 'panel' ? 'Organize informações e adapte cada coluna ao seu trabalho.' : 'Selecione os dados e prepare uma visão do seu trabalho.'}</p></div><div class="heading-actions">${view === 'panel' ? button('import', 'Importar JSON', 'upload') + button('insert', 'Inserir registro', 'plus', 'btn primary') : button('print', 'Imprimir / PDF', 'print') + button('csv', 'Exportar CSV', 'download', 'btn primary')}</div></div><section class="stats" aria-label="Resumo"><article class="stat-card"><div><span>Total de registros</span><strong>${data.records.length.toLocaleString('pt-BR')}</strong><small>Na sua base de dados</small></div><span class="stat-icon blue">${icon('table')}</span></article><article class="stat-card"><div><span>${view === 'panel' ? 'Colunas personalizadas' : 'Resultados encontrados'}</span><strong>${view === 'panel' ? data.columns.length : rows.length}</strong><small>${view === 'panel' ? `${data.columns.filter(c => !c.hidden).length} visíveis no painel` : 'Com os filtros atuais'}</small></div><span class="stat-icon purple">${icon(view === 'panel' ? 'columns' : 'filter')}</span></article><article class="stat-card"><div><span>Última atualização</span><strong class="date-stat">${updated ? new Date(updated).toLocaleDateString('pt-BR', { day: '2-digit', month: 'short' }) : '—'}</strong><small>${updated ? `Às ${new Date(updated).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })}` : 'Insira seu primeiro registro'}</small></div><span class="stat-icon teal">${icon('clock')}</span></article></section>${view === 'reports' ? reportOptions() : ''}<section class="data-card"><div class="data-heading"><div><h2>${view === 'panel' ? 'Todos os registros' : 'Prévia do relatório'}</h2><span class="count-pill">${rows.length}</span></div><div class="data-heading-actions">${view === 'panel' ? button('toggle-edit', inline ? 'Concluir edição' : 'Editar tabela', 'edit', `btn text-btn ${inline ? 'editing-button' : ''}`) + button('columns', 'Gerenciar colunas', 'columns', 'btn text-btn') : '<span class="muted">Resultados completos</span>'}</div></div><div class="toolbar"><div class="search-wrap">${icon('search')}<input id="search" type="search" placeholder="Pesquisar nos registros…" aria-label="Pesquisar nos registros" value="${esc(q.search)}"></div><div class="toolbar-right">${button('filters', `Filtros${q.filters.length ? ' · ' + q.filters.length : ''}`, 'filter', `btn ${filtersOpen ? 'filter-active' : ''}`, `aria-expanded="${filtersOpen}"`)}<label class="sort-label"><span class="sr-only">Ordenar registros</span><select id="sort"><option value="createdAt" ${data.preferences.sortColumn === 'createdAt' ? 'selected' : ''}>Data de criação</option>${data.columns.map(c => `<option value="${c.id}" ${data.preferences.sortColumn === c.id ? 'selected' : ''}>${esc(c.name)}</option>`).join('')}</select></label>${button('direction', data.preferences.sortDirection === 'asc' ? '↑' : '↓', null, 'btn direction-btn', 'aria-label="Inverter ordem"')}</div></div>${filterMarkup()}<div id="draft-bar" class="draft-bar ${dirty() || inline ? '' : 'hidden'}"><span>${icon(dirty() ? 'clock' : 'edit')}<span id="draft-message">${dirty() ? 'Alterações não salvas' : 'Modo de edição · altere os valores nas células'}</span></span><div>${button('cancel-draft', 'Cancelar', null, 'btn small')}${button('save', 'Salvar alterações', 'save', 'btn primary small')}</div></div>${queryError ? `<p class="inline-error" role="alert">${esc(queryError)}</p>` : tableMarkup(rows, columns)}<div class="table-footer"><span>${view === 'reports' ? `${rows.length} registros no relatório` : rows.length ? `Exibindo ${(page - 1) * data.preferences.pageSize + 1}–${Math.min(page * data.preferences.pageSize, rows.length)} de ${rows.length} registros` : '0 registros'}</span>${view === 'panel' ? `<div class="pagination"><label>Por página <select id="page-size">${[10, 20, 50].map(n => `<option ${data.preferences.pageSize === n ? 'selected' : ''}>${n}</option>`).join('')}</select></label>${button('prev', '‹', null, 'btn page-btn', `${page === 1 ? 'disabled' : ''} aria-label="Página anterior"`)}<span class="page-counter">${page} / ${pages}</span>${button('next', '›', null, 'btn page-btn', `${page === pages ? 'disabled' : ''} aria-label="Próxima página"`)}</div>` : ''}</div></section>${view === 'reports' ? sumsMarkup(rows) : ''}<footer class="main-footer"><span>${icon('check')} ${dirty() ? 'Há alterações aguardando salvamento' : 'Dados salvos neste navegador'}</span><span>${view === 'panel' ? 'Personalize as colunas. Deixe o painel com a sua cara.' : 'Os filtros são aplicados à exportação e à impressão.'}</span></footer></main></div></div>`;
  bindInputs();
  if (focusId) { const el = document.getElementById(focusId); if (el) { el.focus(); if (typeof selectionStart === 'number' && el.setSelectionRange && !['date', 'number'].includes(el.type)) el.setSelectionRange(selectionStart, selectionEnd); } }
}
function reportOptions() {
  return `<section class="report-options"><div><h2>Monte seu relatório</h2><p class="muted">Escolha as colunas que deseja incluir.</p><div class="check-list">${data.columns.map(c => `<label><input type="checkbox" data-report-column="${c.id}" ${chosenColumns.includes(c.id) ? 'checked' : ''}>${esc(c.name)}</label>`).join('')}</div></div>${data.columns.some(c => c.type === 'number') ? `<div><h3>Somar valores</h3><div class="check-list">${data.columns.filter(c => c.type === 'number').map(c => `<label><input type="checkbox" data-sum-column="${c.id}" ${sumColumns.includes(c.id) ? 'checked' : ''}>${esc(c.name)}</label>`).join('')}</div></div>` : ''}</section>`;
}
function sumsMarkup(rows) {
  return `<div class="sum-cards">${data.columns.filter(c => c.type === 'number' && sumColumns.includes(c.id)).map(c => `<article><span>Total · ${esc(c.name)}</span><strong>${esc(displayValue(c, rows.reduce((sum, row) => sum + (row.values[c.id] || 0), 0)))}</strong></article>`).join('')}</div>`;
}
function bindInputs() {
  $('#search').oninput = event => { queries[view].search = event.target.value; page = 1; render(true); };
  for (const name of ['from', 'to']) $(`#date-${name}`).onchange = event => { queries[view][name] = event.target.value; page = 1; render(true); };
  $('#sort').onchange = event => { data.preferences.sortColumn = event.target.value; render(); };
  if ($('#page-size')) $('#page-size').onchange = event => { data.preferences.pageSize = Number(event.target.value); page = 1; render(); };
  document.querySelectorAll('[data-cell]').forEach(el => el.oninput = () => {
    const column = data.columns.find(c => c.id === el.dataset.column);
    const row = data.records.find(r => r.id === el.dataset.cell);
    row.values[column.id] = readControl(column, el); row.updatedAt = new Date().toISOString();
    const error = validateValue(column, row.values[column.id]); el.setCustomValidity(error || ''); el.setAttribute('aria-invalid', String(Boolean(error)));
    $('#draft-message').textContent = 'Alterações não salvas'; $('#draft-bar').classList.remove('hidden');
  });
  document.querySelectorAll('[data-filter-column]').forEach(el => el.onchange = () => { const c = data.columns.find(c => c.id === el.value); queries[view].filters[Number(el.dataset.filterColumn)] = { column: c.id, operator: ['text', 'longtext'].includes(c.type) ? 'contains' : 'eq', value: '' }; render(); });
  document.querySelectorAll('[data-filter-operator]').forEach(el => el.onchange = () => { queries[view].filters[Number(el.dataset.filterOperator)].operator = el.value; page = 1; render(); });
  document.querySelectorAll('[data-filter-value]').forEach(el => el.oninput = () => { queries[view].filters[Number(el.dataset.filterValue)].value = el.value; page = 1; render(true); });
  document.querySelectorAll('[data-report-column]').forEach(el => el.onchange = () => { chosenColumns = el.checked ? [...chosenColumns, el.dataset.reportColumn] : chosenColumns.filter(id => id !== el.dataset.reportColumn); render(); });
  document.querySelectorAll('[data-sum-column]').forEach(el => el.onchange = () => { sumColumns = el.checked ? [...sumColumns, el.dataset.sumColumn] : sumColumns.filter(id => id !== el.dataset.sumColumn); render(); });
}
function openEditor(content, wide = false) {
  const dialog = $('#editor'); dialog.className = wide ? 'wide-modal' : ''; dialog.innerHTML = content; dialogDirty = false; editorSave = null;
  dialog.oninput = () => { dialogDirty = true; };
  dialog.oncancel = event => { event.preventDefault(); closeEditor(); };
  dialog.showModal();
}
async function closeEditor() {
  if (dialogDirty) {
    const choice = await confirmAction('Salvar as alterações?', 'As alterações deste formulário ainda não foram salvas.', [{ value: 'cancel', label: 'Continuar editando' }, { value: 'discard', label: 'Descartar' }, { value: 'save', label: 'Salvar', cls: 'primary' }]);
    if (choice === 'cancel') return;
    if (choice === 'save') { if (editorSave) editorSave(); return; }
  }
  $('#editor').close(); dialogDirty = false;
}
function recordEditor(id, readonly = false) {
  const row = id ? data.records.find(r => r.id === id) : null;
  if (id && !row) return;
  openEditor(`<div class="modal-head"><div><span class="tiny-label">REGISTROS</span><h2 id="editor-title">${readonly ? 'Detalhes do registro' : row ? 'Editar registro' : 'Inserir registro'}</h2></div>${button('close-editor', '', 'close', 'icon-btn', 'aria-label="Fechar formulário"')}</div>${readonly ? `<dl class="record-details">${data.columns.map(c => `<div><dt>${esc(c.name)}</dt><dd>${valueHTML(c, row.values[c.id])}</dd></div>`).join('')}<div><dt>Criado em</dt><dd>${dateTime(row.createdAt)}</dd></div><div><dt>Atualizado em</dt><dd>${dateTime(row.updatedAt)}</dd></div><div><dt>Identificador</dt><dd class="record-id">${esc(row.id)}</dd></div></dl><div class="modal-actions">${button('close-editor', 'Fechar', null)}</div>` : `<form id="record-form"><div class="modal-body form-grid">${data.columns.map(c => `<label class="${c.type === 'longtext' ? 'full-width' : ''}">${esc(c.name)} ${c.required ? '<span class="required">*</span>' : ''}${control(c, row?.values[c.id] ?? '', `name="${c.id}"`)}</label>`).join('')}<p class="muted full-width form-note">* Campos obrigatórios. Os dados só serão gravados ao salvar.</p><p id="record-error" class="field-error full-width" role="alert"></p></div><div class="modal-actions">${button('close-editor', 'Cancelar', null)}<button class="btn primary" type="submit">${icon('save')}Salvar registro</button></div></form>`}`);
  if (readonly) return;
  editorSave = () => {
    const form = $('#record-form'); if (!form.reportValidity()) return false;
    const candidate = clone(data), values = Object.fromEntries(data.columns.map(c => [c.id, readControl(c, form.elements.namedItem(c.id))]));
    const now = new Date().toISOString();
    if (row) { const target = candidate.records.find(r => r.id === row.id); target.values = values; target.updatedAt = now; }
    else candidate.records.unshift({ id: uid('row'), values, createdAt: now, updatedAt: now });
    try { repository.save(candidate); data = candidate; saved = clone(data); dialogDirty = false; $('#editor').close(); render(); toast(row ? 'Registro atualizado.' : 'Registro inserido.'); return true; }
    catch (error) { $('#record-error').textContent = error.message; return false; }
  };
  $('#record-form').onsubmit = event => { event.preventDefault(); editorSave(); };
}
function columnsEditor() {
  columnDraft = clone(data); columnDefaults = {};
  openEditor('', true); renderColumnEditor();
}
function renderColumnEditor(openId = '') {
  const existingOpen = [...$('#editor').querySelectorAll('details[open]')].map(el => el.dataset.id);
  $('#editor').innerHTML = `<div class="modal-head"><div><span class="tiny-label">PERSONALIZE SEU PAINEL</span><h2 id="editor-title">Gerenciar colunas</h2></div>${button('close-editor', '', 'close', 'icon-btn', 'aria-label="Fechar configuração de colunas"')}</div><form id="columns-form"><div class="modal-body"><p class="muted">Altere os campos, a ordem e a visibilidade. Renomear mantém os dados existentes.</p><div class="column-list">${columnDraft.columns.map((c, i) => `<details data-id="${c.id}" ${openId === c.id || existingOpen.includes(c.id) ? 'open' : ''}><summary><span class="column-type-icon">${c.type === 'number' ? '#' : c.type === 'date' ? '◷' : 'T'}</span><strong>${esc(c.name)}</strong><span class="muted">${TYPES[c.type]}${c.hidden ? ' · Oculta' : ''}</span></summary><div class="column-fields"><label>Nome<input data-column-prop="name" data-id="${c.id}" value="${esc(c.name)}" maxlength="80" required></label><label>Tipo<select data-column-prop="type" data-id="${c.id}">${Object.entries(TYPES).map(([key, value]) => `<option value="${key}" ${c.type === key ? 'selected' : ''}>${value}</option>`).join('')}</select></label><label>Largura (120 a 600 px)<input type="number" min="120" max="600" step="1" data-column-prop="width" data-id="${c.id}" value="${c.width}" required></label>${c.type === 'select' ? `<label class="full-width">Opções (uma por linha)<textarea data-column-prop="options" data-id="${c.id}" rows="3" required>${esc(c.options.join('\n'))}</textarea></label>` : ''}<div class="check-list full-width"><label><input type="checkbox" data-column-prop="required" data-id="${c.id}" ${c.required ? 'checked' : ''}>Preenchimento obrigatório</label><label><input type="checkbox" data-column-prop="hidden" data-id="${c.id}" ${c.hidden ? 'checked' : ''}>Ocultar no painel</label></div>${c.required && columnDraft.records.some(r => isEmpty(r.values[c.id])) ? `<label class="full-width">Valor padrão para registros sem preenchimento${control({ ...c, required: true }, columnDefaults[c.id] ?? '', `data-default="${c.id}"`)}<small class="muted">Aplicado apenas aos registros que estão vazios.</small></label>` : ''}<div class="column-row-actions full-width">${button('column-up', 'Subir', null, 'btn small', `data-id="${c.id}" ${i === 0 ? 'disabled' : ''}`)}${button('column-down', 'Descer', null, 'btn small', `data-id="${c.id}" ${i === columnDraft.columns.length - 1 ? 'disabled' : ''}`)}${button('column-delete', 'Excluir coluna', 'trash', 'btn small danger-text', `data-id="${c.id}"`)}</div></div></details>`).join('')}</div>${button('column-add', 'Adicionar coluna', 'plus', 'btn add-column')}<p id="columns-error" class="field-error" role="alert"></p></div><div class="modal-actions">${button('close-editor', 'Cancelar', null)}<button type="submit" class="btn primary">${icon('save')}Salvar configuração</button></div></form>`;
  $('#editor').querySelectorAll('[data-column-prop]').forEach(el => {
    const mutate = () => {
      dialogDirty = true;
      const c = columnDraft.columns.find(c => c.id === el.dataset.id), prop = el.dataset.columnProp;
      c[prop] = el.type === 'checkbox' ? el.checked : prop === 'width' ? Number(el.value) : prop === 'options' ? el.value.split('\n').map(v => v.trim()).filter(Boolean) : el.value;
      if (['type', 'required'].includes(prop)) { columnDefaults[c.id] = null; renderColumnEditor(c.id); }
    };
    if (el.dataset.columnProp === 'options') el.addEventListener('change', () => renderColumnEditor(el.dataset.id));
    el.addEventListener(el.tagName === 'SELECT' || el.type === 'checkbox' ? 'change' : 'input', mutate);
  });
  $('#editor').querySelectorAll('[data-default]').forEach(el => el.oninput = () => { dialogDirty = true; columnDefaults[el.dataset.default] = readControl(columnDraft.columns.find(c => c.id === el.dataset.default), el); });
  editorSave = () => {
    if (!$('#columns-form').reportValidity()) return false;
    try {
      const candidate = clone(columnDraft), now = new Date().toISOString();
      for (const c of candidate.columns) {
        c.name = c.name.trim();
        for (const r of candidate.records) {
          if (c.required && isEmpty(r.values[c.id]) && !isEmpty(columnDefaults[c.id])) { r.values[c.id] = columnDefaults[c.id]; r.updatedAt = now; }
        }
      }
      validateData(candidate); repository.save(candidate); data = candidate; saved = clone(data);
      reconcileSchema(); dialogDirty = false; $('#editor').close(); render(); toast('Configuração das colunas salva.'); return true;
    } catch (error) { $('#columns-error').textContent = `${error.message} Nenhum dado foi alterado. Se mudou o tipo ou as opções, verifique os valores existentes.`; $('#columns-error').scrollIntoView({ block: 'nearest' }); return false; }
  };
  $('#columns-form').onsubmit = event => { event.preventDefault(); editorSave(); };
}
function reconcileSchema() {
  const ids = data.columns.map(c => c.id);
  for (const q of Object.values(queries)) q.filters = q.filters.filter(f => ids.includes(f.column));
  chosenColumns = chosenColumns.filter(id => ids.includes(id));
  if (!chosenColumns.length) chosenColumns = data.columns.filter(c => !c.hidden).map(c => c.id);
  sumColumns = sumColumns.filter(id => data.columns.some(c => c.id === id && c.type === 'number'));
}
function download(filename, text, type) {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const link = document.createElement('a'); link.href = url; link.download = filename; document.body.append(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
}
function exportReport(print = false) {
  const columns = data.columns.filter(c => chosenColumns.includes(c.id));
  if (!columns.length) { toast('Selecione pelo menos uma coluna para o relatório.', true); return; }
  try {
    const rows = queryRecords(data, queries.reports);
    if (!print) { download(`painel-relatorio-${new Date().toISOString().slice(0, 10)}.csv`, toCSV(columns, rows), 'text/csv;charset=utf-8'); toast('Relatório CSV exportado.'); return; }
    const filters = queries.reports;
    const criteria = [filters.search ? `Pesquisa: ${filters.search}` : '', filters.from ? `De: ${filters.from.split('-').reverse().join('/')}` : '', filters.to ? `Até: ${filters.to.split('-').reverse().join('/')}` : '', ...filters.filters.map(f => `${data.columns.find(c => c.id === f.column)?.name}: ${{ eq: 'igual a', contains: 'contém', gte: 'maior ou igual a', lte: 'menor ou igual a', empty: 'está vazio', filled: 'está preenchido' }[f.operator]} ${f.value}`)].filter(Boolean).join(' · ');
    let area = $('#print-area'); if (area) area.remove();
    area = document.createElement('section'); area.id = 'print-area';
    area.innerHTML = `<header><img class="report-logo" src="./assets/rio-quente-logo.png?v=2" alt="Rio Quente" width="447" height="447"><strong>Painel de Registros / relatórios</strong><p>Gerado em ${dateTime(new Date())}</p></header><h1>Relatório de registros</h1><p>${rows.length} registros · ${columns.length} colunas</p><p>${esc(criteria || 'Todos os registros')}</p><table><thead><tr>${columns.map(c => `<th>${esc(c.name)}</th>`).join('')}</tr></thead><tbody>${rows.map(r => `<tr>${columns.map(c => `<td>${esc(displayValue(c, r.values[c.id]))}</td>`).join('')}</tr>`).join('')}</tbody></table>${sumsMarkup(rows)}`;
    document.body.append(area); window.print();
  } catch (error) { showError(error); }
}
document.addEventListener('click', async event => {
  const target = event.target.closest('[data-action]'); if (!target) return;
  event.preventDefault(); const { action, id, index } = target.dataset;
  try {
    if (action === 'import') { await guard(() => $('#import-file').click()); return; }
    if (action === 'close-editor') { await closeEditor(); return; }
    if (!data) return;
    switch (action) {
      case 'home': case 'panel': case 'reports': await guard(() => { view = action === 'reports' ? 'reports' : 'panel'; filtersOpen = view === 'reports'; page = 1; inline = false; render(); }); break;
      case 'logout': await guard(() => { repository.logout(); data = null; saved = null; loginScreen(); }); break;
      case 'backup': download(`painel-backup${dirty() ? '-rascunho' : ''}-${new Date().toISOString().slice(0, 10)}.json`, JSON.stringify(data, null, 2), 'application/json'); toast(dirty() ? 'Backup do rascunho exportado. Valide os dados antes de reimportar.' : 'Backup JSON exportado.'); break;
      case 'insert': await guard(() => recordEditor()); break;
      case 'edit': await guard(() => recordEditor(id)); break;
      case 'view': recordEditor(id, true); break;
      case 'delete': if (await confirmAction('Excluir registro?', 'O registro será removido do painel ao salvar as alterações.', [{ value: 'cancel', label: 'Cancelar' }, { value: 'confirm', label: 'Excluir registro', cls: 'danger' }]) === 'confirm') { data.records = data.records.filter(r => r.id !== id); render(); toast('Exclusão em rascunho. Clique em Salvar alterações.'); } break;
      case 'toggle-edit': inline = !inline; render(); break;
      case 'save': saveAll(); break;
      case 'cancel-draft': await guard(() => { inline = false; render(); }); break;
      case 'columns': await guard(columnsEditor); break;
      case 'filters': filtersOpen = !filtersOpen; render(); break;
      case 'add-filter': { const c = data.columns[0]; queries[view].filters.push({ column: c.id, operator: ['text', 'longtext'].includes(c.type) ? 'contains' : 'eq', value: '' }); filtersOpen = true; render(); break; }
      case 'remove-filter': queries[view].filters.splice(Number(index), 1); page = 1; render(); break;
      case 'clear-filters': queries[view] = { search: '', filters: [], from: '', to: '' }; page = 1; render(); break;
      case 'sort': data.preferences.sortDirection = data.preferences.sortColumn === id && data.preferences.sortDirection === 'asc' ? 'desc' : 'asc'; data.preferences.sortColumn = id; render(); break;
      case 'direction': data.preferences.sortDirection = data.preferences.sortDirection === 'asc' ? 'desc' : 'asc'; render(); break;
      case 'prev': page--; render(); break;
      case 'next': page++; render(); break;
      case 'csv': exportReport(); break;
      case 'print': exportReport(true); break;
      case 'column-add': { const c = { id: uid('col'), name: `Coluna ${columnDraft.columns.length + 1}`, type: 'text', required: false, hidden: false, width: 200, options: [] }; columnDraft.columns.push(c); dialogDirty = true; renderColumnEditor(c.id); break; }
      case 'column-up': case 'column-down': { const at = columnDraft.columns.findIndex(c => c.id === id), to = at + (action === 'column-up' ? -1 : 1); if (to < 0 || to >= columnDraft.columns.length) break; [columnDraft.columns[at], columnDraft.columns[to]] = [columnDraft.columns[to], columnDraft.columns[at]]; dialogDirty = true; renderColumnEditor(id); break; }
      case 'column-delete': {
        if (columnDraft.columns.length === 1) { toast('Mantenha pelo menos uma coluna.', true); break; }
        const col = columnDraft.columns.find(c => c.id === id);
        if (await confirmAction(`Excluir a coluna “${col.name}”?`, 'Todos os valores desta coluna serão apagados ao salvar a configuração. Ocultar mantém os dados.', [{ value: 'cancel', label: 'Cancelar' }, { value: 'confirm', label: 'Excluir coluna', cls: 'danger' }]) === 'confirm') {
          columnDraft.columns = columnDraft.columns.filter(c => c.id !== id); columnDraft.records.forEach(r => { delete r.values[id]; r.updatedAt = new Date().toISOString(); });
          if (columnDraft.preferences.sortColumn === id) columnDraft.preferences.sortColumn = 'createdAt'; dialogDirty = true; renderColumnEditor();
        } break;
      }
    }
  } catch (error) { showError(error); }
});
$('#import-file').onchange = async event => {
  const file = event.target.files[0]; event.target.value = ''; if (!file) return;
  try {
    if (file.size > 10 * 1024 * 1024) throw new Error('Escolha um arquivo de até 10 MB.');
    const candidate = repository.import(await file.text());
    const choice = await confirmAction('Substituir os dados pelo backup?', `O arquivo contém ${candidate.records.length} registros e ${candidate.columns.length} colunas. Todos os dados e configurações atuais serão substituídos.`, [{ value: 'cancel', label: 'Cancelar' }, { value: 'confirm', label: 'Importar e substituir', cls: 'primary' }]);
    if (choice !== 'confirm') return;
    repository.save(candidate, { overwrite: true }); data = candidate; saved = clone(data); chosenColumns = data.columns.filter(c => !c.hidden).map(c => c.id); sumColumns = []; queries.panel = { search: '', filters: [], from: '', to: '' }; queries.reports = { search: '', filters: [], from: '', to: '' }; page = 1; inline = false; render(); toast('Backup importado com sucesso.');
  } catch (error) { toast(error instanceof SyntaxError ? 'O arquivo não contém um JSON válido. Os dados atuais foram preservados.' : error.message, true); }
};
window.addEventListener('beforeunload', event => { if (dirty() || dialogDirty) { event.preventDefault(); event.returnValue = ''; } });
window.addEventListener('storage', event => { if (event.key === 'prisma.workspace.v1') toast('Os dados mudaram em outra aba. Recarregue antes de editar; exporte um backup se houver rascunhos.', true); });
try { repository.loggedIn() ? initialize() : loginScreen(); } catch (error) { $('#app').innerHTML = `<main class="recovery"><h1>Armazenamento indisponível</h1><p>Permita o armazenamento local neste navegador e recarregue a página.</p></main>`; }
