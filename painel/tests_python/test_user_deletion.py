from calendar_app.db import get_db
from conftest import API, PASSWORD


def test_admin_deletes_access_and_preserves_history(app):
    admin = API(app, 'admin')
    seller = API(app, 'seller')
    booking = seller.create(status='pending')
    assert booking.status_code == 201, booking.json
    old = next(u for u in admin.get('/users').json['users'] if u['username'] == 'seller')

    deleted = admin.send(f"/users/{old['id']}", {'version': old['version']}, method='DELETE')
    assert deleted.status_code == 200 and deleted.json == {'deleted': True}
    assert all(u['id'] != old['id'] for u in admin.get('/users').json['users'])
    assert seller.get('/catalog').status_code == 401
    with app.app_context():
        conn = get_db()
        archived = conn.execute('SELECT * FROM users WHERE id=%s', (old['id'],)).fetchone()
        assert archived['deleted_at'] and not archived['active']
        assert archived['username'] != 'seller' and archived['entra_object_id'] is None
        assert conn.execute('SELECT count(*) AS n FROM bookings WHERE created_by=%s', (old['id'],)).fetchone()['n'] == 1
        assert conn.execute("SELECT count(*) AS n FROM audit WHERE entity_type='user' AND entity_id=%s AND action='delete'", (old['id'],)).fetchone()['n'] == 1

    replacement = admin.send('/users', {'username': 'seller', 'name': 'Nova pessoa',
                                        'password': PASSWORD, 'team_id': 'commercial', 'scopes': ['cs']})
    assert replacement.status_code == 201 and replacement.json['id'] != old['id']
    assert API(app, 'seller').get('/catalog').status_code == 200


def test_user_deletion_requires_admin_and_current_version(app):
    admin = API(app, 'admin')
    seller = API(app, 'seller')
    users = admin.get('/users').json['users']
    target = next(u for u in users if u['username'] == 'ops')
    own = next(u for u in users if u['username'] == 'admin')

    assert seller.send(f"/users/{target['id']}", {'version': target['version']}, method='DELETE').status_code == 403
    assert admin.send(f"/users/{own['id']}", {'version': own['version']}, method='DELETE').status_code == 400
    assert admin.send(f"/users/{target['id']}", {'version': target['version'] + 1}, method='DELETE').status_code == 409
    assert admin.send('/users/missing', {'version': 1}, method='DELETE').status_code == 404
    assert any(u['id'] == target['id'] for u in admin.get('/users').json['users'])
