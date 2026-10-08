export const TYPES = { text: 'Texto curto', longtext: 'Texto longo', number: 'Número', date: 'Data', select: 'Seleção de opções', boolean: 'Sim/não' };
export const clone = value => structuredClone(value);
export const uid = prefix => `${prefix}_${crypto.randomUUID()}`;
export const isEmpty = value => value === '' || value === null || value === undefined;
const validId = value => typeof value === 'string' && /^[a-zA-Z][a-zA-Z0-9_-]{0,100}$/.test(value) && !['__proto__', 'constructor', 'prototype'].includes(value);
const plain = value => value !== null && typeof value === 'object' && !Array.isArray(value);
export function isDate(value) {
  return typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value) && Number.isFinite(Date.parse(value)) && new Date(value).toISOString().slice(0, 10) === value;
}
export function validateValue(column, value) {
  if (isEmpty(value)) return column.required ? `${column.name}: preenchimento obrigatório.` : null;
  switch (column.type) {
    case 'text': case 'longtext': return typeof value === 'string' && value.trim() ? null : `${column.name}: informe um texto válido.`;
    case 'number': return typeof value === 'number' && Number.isFinite(value) ? null : `${column.name}: informe um número válido.`;
    case 'date': return isDate(value) ? null : `${column.name}: informe uma data válida.`;
    case 'select': return column.options.includes(value) ? null : `${column.name}: escolha uma opção disponível.`;
    case 'boolean': return typeof value === 'boolean' ? null : `${column.name}: selecione Sim ou Não.`;
    default: return 'Tipo de coluna inválido.';
  }
}
export function validateData(data) {
  if (!plain(data) || data.version !== 1 || !Array.isArray(data.columns) || !Array.isArray(data.records) || !plain(data.preferences)) throw new Error('Formato inválido. Importe um backup do painel na versão 1.');
  if (!data.columns.length || data.columns.length > 100) throw new Error('O painel precisa ter entre 1 e 100 colunas.');
  if (data.records.length > 50000) throw new Error('O limite do mockup é de 50.000 registros.');
  const ids = new Set(), names = new Set();
  for (const col of data.columns) {
    if (!plain(col) || !validId(col.id) || ids.has(col.id)) throw new Error('Identificador de coluna inválido ou duplicado.');
    if (typeof col.name !== 'string' || !col.name.trim() || col.name.length > 80 || names.has(col.name.trim().toLocaleLowerCase('pt-BR'))) throw new Error('Os nomes das colunas devem ser únicos e ter até 80 caracteres.');
    if (!Object.hasOwn(TYPES, col.type) || typeof col.required !== 'boolean' || typeof col.hidden !== 'boolean' || !Number.isInteger(col.width) || col.width < 120 || col.width > 600) throw new Error('Configuração de coluna inválida.');
    if (!Array.isArray(col.options) || col.options.some(v => typeof v !== 'string' || !v.trim() || v.length > 120) || new Set(col.options).size !== col.options.length || (col.type === 'select' && !col.options.length)) throw new Error(`${col.name}: configure opções únicas e não vazias.`);
    ids.add(col.id); names.add(col.name.trim().toLocaleLowerCase('pt-BR'));
  }
  if (!data.columns.some(col => !col.hidden)) throw new Error('Mantenha pelo menos uma coluna visível.');
  const recordIds = new Set();
  for (const row of data.records) {
    if (!plain(row) || !validId(row.id) || recordIds.has(row.id) || !plain(row.values) || typeof row.createdAt !== 'string' || typeof row.updatedAt !== 'string' || !Number.isFinite(Date.parse(row.createdAt)) || !Number.isFinite(Date.parse(row.updatedAt))) throw new Error('Registro ou datas de auditoria inválidos.');
    if (Object.keys(row.values).some(key => !ids.has(key))) throw new Error('Um registro contém valores para uma coluna inexistente.');
    for (const col of data.columns) { const error = validateValue(col, row.values[col.id]); if (error) throw new Error(error); }
    recordIds.add(row.id);
  }
  const p = data.preferences;
  if (![10, 20, 50].includes(p.pageSize) || !['asc', 'desc'].includes(p.sortDirection) || (p.sortColumn !== 'createdAt' && !ids.has(p.sortColumn))) throw new Error('Preferências de exibição inválidas.');
  return data;
}
export function seedData() {
  const columns = [
    { id: 'name', name: 'Nome', type: 'text', required: true, width: 270, hidden: false, options: [] },
    { id: 'description', name: 'Descrição', type: 'longtext', required: false, width: 330, hidden: false, options: [] },
    { id: 'category', name: 'Categoria', type: 'select', required: true, width: 170, hidden: false, options: ['Administrativo', 'Comercial', 'Financeiro', 'Operacional'] },
    { id: 'status', name: 'Status', type: 'select', required: true, width: 135, hidden: false, options: ['Ativo', 'Inativo'] }
  ];
  const examples = [
    ['Planejamento trimestral', 'Objetivos e prioridades da equipe', 'Administrativo', 'Ativo'],
    ['Cadastro de fornecedores', 'Base de parceiros e prestadores de serviço', 'Operacional', 'Ativo'],
    ['Propostas comerciais', 'Acompanhamento das propostas enviadas', 'Comercial', 'Ativo'],
    ['Controle de despesas', 'Organização das despesas recorrentes', 'Financeiro', 'Ativo'],
    ['Inventário de equipamentos', 'Relação dos equipamentos do escritório', 'Operacional', 'Ativo'],
    ['Contratos anteriores', 'Histórico de contratos encerrados', 'Administrativo', 'Inativo'],
    ['Agenda de entregas', 'Prazos e acompanhamento das entregas', 'Operacional', 'Ativo'],
    ['Campanha de lançamento', 'Materiais e ações de divulgação', 'Comercial', 'Ativo'],
    ['Orçamento anual', 'Previsão de custos por departamento', 'Financeiro', 'Ativo'],
    ['Processos arquivados', 'Documentação de processos concluídos', 'Administrativo', 'Inativo'],
    ['Contatos comerciais', 'Relacionamento com clientes e parceiros', 'Comercial', 'Ativo'],
    ['Conciliação mensal', 'Conferência de movimentações financeiras', 'Financeiro', 'Ativo']
  ];
  return { version: 1, columns, records: examples.map((values, i) => {
    const date = new Date(Date.now() - i * 86400000).toISOString();
    return { id: uid('row'), createdAt: date, updatedAt: date, values: Object.fromEntries(columns.map((c, index) => [c.id, values[index]])) };
  }), preferences: { pageSize: 10, sortColumn: 'createdAt', sortDirection: 'desc' } };
}
export function displayValue(column, value) {
  if (isEmpty(value)) return '—';
  if (column.type === 'boolean') return value ? 'Sim' : 'Não';
  if (column.type === 'number') return new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 10 }).format(value);
  if (column.type === 'date') return value.split('-').reverse().join('/');
  return String(value);
}
const normalize = value => String(value ?? '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
export function queryRecords(data, query = {}) {
  const { search = '', filters = [], from = '', to = '', sortColumn = data.preferences.sortColumn, sortDirection = data.preferences.sortDirection } = query;
  if (from && to && from > to) throw new Error('A data inicial deve ser anterior ou igual à data final.');
  const rows = data.records.filter(row => {
    const localDate = new Date(row.createdAt).toLocaleDateString('sv-SE');
    if ((from && localDate < from) || (to && localDate > to)) return false;
    if (search && !data.columns.some(col => normalize(displayValue(col, row.values[col.id])).includes(normalize(search)))) return false;
    return filters.every(f => {
      const column = data.columns.find(c => c.id === f.column);
      if (!column) return true;
      const value = row.values[column.id];
      if (f.operator === 'empty') return isEmpty(value);
      if (f.operator === 'filled') return !isEmpty(value);
      if (isEmpty(f.value)) return true;
      if (isEmpty(value)) return false;
      const target = column.type === 'number' ? Number(f.value) : column.type === 'boolean' ? f.value === 'true' : f.value;
      if (f.operator === 'contains') return normalize(value).includes(normalize(target));
      if (f.operator === 'gte') return value >= target;
      if (f.operator === 'lte') return value <= target;
      return value === target;
    });
  });
  return rows.sort((a, b) => {
    const av = sortColumn === 'createdAt' ? a.createdAt : a.values[sortColumn];
    const bv = sortColumn === 'createdAt' ? b.createdAt : b.values[sortColumn];
    if (isEmpty(av) && isEmpty(bv)) return 0;
    if (isEmpty(av)) return 1;
    if (isEmpty(bv)) return -1;
    const order = typeof av === 'number' ? av - bv : String(av).localeCompare(String(bv), 'pt-BR', { numeric: true });
    return sortDirection === 'asc' ? order : -order;
  });
}
export function toCSV(columns, rows) {
  const escape = value => {
    let text = String(value ?? '');
    // Neutralize spreadsheet formulas, including those preceded by whitespace.
    if (/^[\s]*[=+\-@]/.test(text)) text = "'" + text;
    return '"' + text.replaceAll('"', '""') + '"';
  };
  return '\uFEFF' + [columns.map(c => escape(c.name)).join(';'), ...rows.map(row => columns.map(c => escape(isEmpty(row.values[c.id]) ? '' : displayValue(c, row.values[c.id]))).join(';'))].join('\r\n');
}
