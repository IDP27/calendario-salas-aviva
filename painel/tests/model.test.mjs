import test from 'node:test';
import assert from 'node:assert/strict';
import { seedData, validateData, validateValue, clone, queryRecords, toCSV } from '../legacy/dist/js/model.js';
import { repository, STORAGE_KEY } from '../legacy/dist/js/storage.js';

test('renomear, reordenar e ocultar preserva a associação dos valores', () => {
  const data = seedData(), before = clone(data.records);
  data.columns[0].name = 'Título'; data.columns[0].hidden = true; data.columns.reverse();
  validateData(data);
  assert.deepEqual(data.records, before);
  assert.equal(data.records[0].values.name, 'Planejamento trimestral');
});
test('validação bloqueia tipos incompatíveis e opções removidas', () => {
  const data = seedData(); data.columns[0].type = 'number';
  assert.throws(() => validateData(data), /número/);
  data.columns[0].type = 'text'; data.columns[2].options = ['Comercial'];
  assert.throws(() => validateData(data), /opção/);
});
test('coluna obrigatória nova exige preenchimento e aceita zero e falso', () => {
  const data = seedData();
  const col = { id: 'amount', name: 'Valor', type: 'number', required: true, width: 160, hidden: false, options: [] };
  data.columns.push(col); assert.throws(() => validateData(data), /obrigatório/);
  for (const row of data.records) row.values.amount = 0;
  assert.doesNotThrow(() => validateData(data));
  assert.equal(validateValue({ ...col, type: 'boolean' }, false), null);
});
test('datas impossíveis e números não finitos são recusados', () => {
  assert.match(validateValue({ name: 'Data', type: 'date' }, '2026-02-30'), /data válida/);
  assert.equal(validateValue({ name: 'Data', type: 'date' }, '2024-02-29'), null);
  assert.match(validateValue({ name: 'Valor', type: 'number' }, Infinity), /número/);
});
test('importação rejeita IDs duplicados, colunas órfãs e versões inválidas', () => {
  const data = seedData(); data.columns[1].id = data.columns[0].id;
  assert.throws(() => validateData(data), /duplicado/);
  const other = seedData(); other.records[0].values.unknown = 'valor';
  assert.throws(() => repository.import(JSON.stringify(other)), /inexistente/);
  assert.throws(() => repository.import('{'), SyntaxError);
  assert.throws(() => validateData({ ...seedData(), version: 2 }), /versão/);
});
test('pesquisa ignora acentos e filtros são combinados', () => {
  const data = seedData();
  assert.equal(queryRecords(data, { search: 'orcamento' }).length, 1);
  const rows = queryRecords(data, { filters: [{ column: 'category', operator: 'eq', value: 'Administrativo' }, { column: 'status', operator: 'eq', value: 'Inativo' }] });
  assert.equal(rows.length, 2);
  assert.throws(() => queryRecords(data, { from: '2026-10-02', to: '2026-10-01' }), /inicial/);
});
test('filtros numéricos, booleanos, datas e vazios', () => {
  const data = seedData();
  data.columns.push({ id: 'n', type: 'number' }, { id: 'b', type: 'boolean' }, { id: 'd', type: 'date' });
  data.records[0].values.n = 42; data.records[0].values.b = false; data.records[0].values.d = '2026-10-02';
  assert.equal(queryRecords(data, { filters: [{ column: 'n', operator: 'gte', value: '40' }] }).length, 1);
  assert.equal(queryRecords(data, { filters: [{ column: 'b', operator: 'eq', value: 'false' }] }).length, 1);
  assert.equal(queryRecords(data, { filters: [{ column: 'd', operator: 'lte', value: '2026-10-02' }] }).length, 1);
  assert.equal(queryRecords(data, { filters: [{ column: 'n', operator: 'empty' }] }).length, 11);
});
test('CSV preserva aspas, separadores, quebras e neutraliza fórmulas', () => {
  const columns = [{ id: 'x', name: 'Campo', type: 'text' }];
  const csv = toCSV(columns, [{ values: { x: 'Texto; "com aspas"\ne linha' } }, { values: { x: '=1+2' } }]);
  assert.ok(csv.startsWith('\uFEFF'));
  assert.ok(csv.includes('"Texto; ""com aspas""\ne linha"'));
  assert.ok(csv.includes('"\'=1+2"'));
});
test('persistência não recria registros apagados e preserva dados após importação inválida', () => {
  const memory = new Map();
  globalThis.localStorage = { getItem: key => memory.get(key) ?? null, setItem: (key, value) => memory.set(key, value) };
  const data = repository.load(); assert.equal(data.records.length, 12);
  data.records = []; repository.save(data);
  assert.equal(repository.load().records.length, 0);
  const before = memory.get(STORAGE_KEY);
  assert.throws(() => repository.import('{"version":999}'));
  assert.equal(memory.get(STORAGE_KEY), before);
  memory.set(STORAGE_KEY, 'alterado-em-outra-aba');
  assert.throws(() => repository.save(data), /outra aba/);
  repository.save(data, { overwrite: true });
  globalThis.localStorage.setItem = () => { throw new Error('QuotaExceededError'); };
  assert.throws(() => repository.save(data), /armazenamento/);
});
