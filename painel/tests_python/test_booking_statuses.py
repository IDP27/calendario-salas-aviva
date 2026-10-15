from calendar_app import ROOT
from calendar_app.db import get_db
from conftest import API, allocation, edit_body
def test_only_confirmed_blocks_and_retired_statuses_are_rejected(api, app):
    api.validate(4)
    first = api.create(code=4, status='reserved').json
    second = api.create(code=4, status='reserved').json
    with app.app_context():
        assert get_db().execute('SELECT count(*) AS n FROM occupations').fetchone()['n'] == 0
    assert api.get('/bookings?status=reserved').json['bookings']
    assert api.confirm(second).status_code == 409  # Order of entry still matters.
    confirmed = api.confirm(first)
    assert confirmed.status_code == 200
    with app.app_context():
        assert get_db().execute('SELECT count(*) AS n FROM occupations WHERE booking_id=%s', (first['id'],)).fetchone()['n'] == 3
    assert api.get('/bookings?status=confirmed').json['bookings'][0]['id'] == first['id']
    assert api.confirm(second).status_code == 409
    with app.app_context():
        assert get_db().execute("SELECT count(*) AS n FROM bookings WHERE status NOT IN ('reserved','confirmed','cancelled')").fetchone()['n'] == 0
    for old_status in ('pending', 'waiting', 'option'):
        assert api.create(status=old_status).status_code == 409
        assert api.get(f'/bookings?status={old_status}').status_code == 400
    cancelled = api.send(f"/bookings/{first['id']}/cancel", {
        'version': confirmed.json['version'], 'reason': 'Liberado para novo evento',
    })
    assert cancelled.status_code == 200
    with app.app_context():
        assert get_db().execute('SELECT count(*) AS n FROM occupations WHERE booking_id=%s', (first['id'],)).fetchone()['n'] == 0
    assert api.confirm(second).status_code == 200


def test_confirmed_period_rejects_new_or_moved_reservation(api):
    api.validate(7)
    confirmed = api.create(code=7, status='confirmed').json
    assert api.create(code=7, status='reserved').status_code == 409
    movable = api.create(code=7, start='2027-01-13', end='2027-01-14').json
    moved = api.send(f"/bookings/{movable['id']}", edit_body(
        movable, allocations=[allocation(7, '2027-01-11', '2027-01-13')]
    ), method='PUT')
    assert moved.status_code == 409
    assert api.detail(movable)['allocations'][0]['start_date'] == '2027-01-13'
    assert api.detail(confirmed)['status'] == 'confirmed'


def test_confirmation_saves_newly_validated_composition_and_owner_can_edit_text(api, app):
    owner = API(app, 'seller')
    reserved = owner.create(code=7).json
    assert reserved['allocations'][0]['resources'] == []
    api.validate(7)
    confirmed = api.confirm(reserved)
    assert confirmed.status_code == 200
    chosen = api.config(7)['options'][0]
    assert confirmed.json['allocations'][0]['resources'] == chosen
    updated = owner.send(f"/bookings/{reserved['id']}", edit_body(
        confirmed.json, title='Título atualizado'
    ), method='PUT')
    assert updated.status_code == 200
    assert updated.json['title'] == 'Título atualizado'
    assert updated.json['allocations'][0]['resources'] == chosen


def test_existing_option_becomes_confirmed_and_preserves_occupation(api, app):
    api.validate(7)
    pending = api.create(start='2027-01-01', end='2027-01-02').json
    waiting = api.create(start='2027-01-05', end='2027-01-06').json
    option = api.create(status='confirmed', start='2027-01-10', end='2027-01-12').json
    migration = (ROOT / 'calendar_app/migrations/004_three_booking_statuses.sql').read_text()

    with app.app_context():
        conn = get_db()
        with conn.transaction():
            conn.execute('ALTER TABLE bookings DROP CONSTRAINT bookings_status_check')
            for booking, old_status in ((pending, 'pending'), (waiting, 'waiting'), (option, 'option')):
                conn.execute('UPDATE bookings SET status=%s WHERE id=%s', (old_status, booking['id']))
                conn.execute("UPDATE idempotency SET response=jsonb_set(response,'{status}',to_jsonb(%s::text)) WHERE response->>'id'=%s", (old_status, booking['id']))
            conn.execute("ALTER TABLE bookings ADD CONSTRAINT bookings_status_check CHECK (status IN ('pending','waiting','option','confirmed','cancelled'))")
            assert conn.execute('SELECT count(*) AS n FROM occupations WHERE booking_id=%s', (option['id'],)).fetchone()['n'] == 3
            conn.execute(migration, prepare=False)

        status_by_id = {row['id']: row['status'] for row in conn.execute('SELECT id,status FROM bookings')}
        assert status_by_id == {pending['id']: 'reserved', waiting['id']: 'reserved', option['id']: 'confirmed'}
        assert conn.execute('SELECT count(*) AS n FROM occupations WHERE booking_id=%s', (option['id'],)).fetchone()['n'] == 3
        response_statuses = {row['response']['status'] for row in conn.execute('SELECT response FROM idempotency')}
        assert response_statuses == {'reserved', 'confirmed'}
