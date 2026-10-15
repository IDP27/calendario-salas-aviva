import test from 'node:test';
import assert from 'node:assert/strict';

import { createViews } from '../dist/js/calendar-views.js';

function views(admin = false) {
  return createViews({
    user: { id: 'current', name: 'Pessoa Teste', team_id: 'commercial', can_manage_users: admin },
    authMode: 'local', view: 'calendar', month: 0, year: 2027,
    resort: 'all', status: '', search: '', sourceCount: 125,
    catalog: [], calendar: [], bookings: [], days: [], mode: 'grid', users: [],
    reportFrom: '2027-01-01', reportTo: '2027-01-31',
  }, id => ({ cs: 'Costa do Sauípe', rq: 'Rio Quente' })[id] || 'Empreendimento não definido');
}

test('menu de administração aparece somente para quem pode administrar pessoas', () => {
  assert.doesNotMatch(views().sidebar(), /Pessoas & acessos/);
  assert.match(views(true).sidebar(), /Pessoas & acessos/);
});

test('filtro de situação oferece apenas os três status e todas', () => {
  const html = views().toolbar(false);
  assert.match(html, /<option value="confirmed"/);
  assert.match(html, /<option value="cancelled"/);
  assert.match(html, /<option value="reserved"/);
  assert.doesNotMatch(html, /value="pending"|value="waiting"|value="option"/);
  assert.equal((html.match(/<option value="(?:confirmed|cancelled|reserved)"/g) || []).length, 3);
});

test('situação em Salas & espaços limita a lista aos espaços com solicitação correspondente', () => {
  const state = {
    user: { id: 'current', name: 'Pessoa Teste', team_id: 'commercial', can_catalog: false },
    authMode: 'local', view: 'catalog', resort: 'all', status: 'confirmed', search: '', sourceCount: 2,
    catalog: [
      { id: 'one', name: 'Sala confirmada', resort_id: 'cs', source_codes: [1], validated: true },
      { id: 'two', name: 'Sala reservada', resort_id: 'cs', source_codes: [2], validated: true },
    ],
    bookings: [{ matched_allocations: [{ configuration_id: 'one' }] }],
  };
  const html = createViews(state, () => 'Costa do Sauípe').catalogView();
  assert.match(html, /Sala confirmada/);
  assert.doesNotMatch(html, /Sala reservada/);
});

test('lista de solicitações mantém datas inclusivas e escapa texto informado', () => {
  const booking = {
    id: 'booking-1', title: '<script>teste</script>', responsible: 'Equipe',
    team_name: 'Comercial MICE', queue_number: 3, status: 'reserved',
    allocations: [{ space_name: 'Gardênia', start_date: '2027-01-01', end_date: '2027-01-03' }],
  };
  const html = views().bookingList([booking]);
  assert.match(html, /01\/01\/2027/);
  assert.match(html, /03\/01\/2027/);
  assert.match(html, /&lt;script&gt;teste&lt;\/script&gt;/);
  assert.doesNotMatch(html, /<script>/);
});
