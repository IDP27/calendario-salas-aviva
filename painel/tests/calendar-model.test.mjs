import test from 'node:test';
import assert from 'node:assert/strict';

import {
  allocationResort, buildQueryString, esc, monthRange, spaceOptions,
} from '../dist/js/calendar-model.js';

test('seleção de espaços respeita o empreendimento de cada configuração', () => {
  const catalog = [
    { id: 'sauipe', name: 'Sala Sauípe', resort_id: 'cs' },
    { id: 'rio', name: 'Sala Rio', resort_id: 'rq' },
    { id: 'review', name: 'A classificar', resort_id: null },
  ];
  const rio = spaceOptions(catalog, 'rq', 'rio');
  assert.match(rio, /Sala Rio/);
  assert.match(rio, /value="rio" selected/);
  assert.doesNotMatch(rio, /Sala Sauípe|A classificar/);
  assert.equal(allocationResort(catalog[2]), 'unassigned');
});

test('datas e filtros preservam o intervalo correto, incluindo fevereiro bissexto', () => {
  assert.deepEqual(monthRange(2028, 1), { from: '2028-02-01', to: '2028-02-29' });
  const state = {
    year: 2028, month: 1, view: 'calendar', resort: 'rq', status: 'waiting',
    search: 'São Tomé', reportFrom: '2027-01-01', reportTo: '2027-01-31',
  };
  const calendar = new URLSearchParams(buildQueryString(state));
  assert.equal(calendar.get('to'), '2028-02-29');
  assert.equal(calendar.get('resort'), 'rq');
  assert.equal(calendar.get('search'), 'São Tomé');
  assert.equal(new URLSearchParams(buildQueryString({ ...state, view: 'reports' })).get('from'), '2027-01-01');
});

test('nomes do catálogo são escapados antes de compor opções HTML', () => {
  const html = spaceOptions([{ id: 'safe', name: '<img src=x>', resort_id: 'cs' }], 'cs');
  assert.match(html, /&lt;img src=x&gt;/);
  assert.doesNotMatch(html, /<img/);
  assert.equal(esc('"&'), '&quot;&amp;');
});
