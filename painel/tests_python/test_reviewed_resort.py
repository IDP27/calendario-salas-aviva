import json
import pytest
from calendar_app import ROOT
from calendar_app.catalog import assign_reviewed_resort
from calendar_app.common import Problem
from calendar_app.db import get_db


def reviewed():
    return json.loads((ROOT/'docs/classificacao-costa-sauipe-2026-10-08.json').read_text(encoding='utf-8'))


def rio_quente():
    return json.loads((ROOT/'docs/classificacao-rio-quente-2026-10-08.json').read_text(encoding='utf-8'))


def test_reviewed_sauipe_assignment_preserves_booking_and_topology(api,app):
    booking=api.create(status='pending').json
    with app.app_context():
        preview=assign_reviewed_resort(reviewed())
        assert preview['source_codes']==114
        assert preview['configurations_to_update']==90
        assert preview['applied'] is False
        assert get_db().execute('SELECT count(*) AS n FROM configurations WHERE resort_id IS NULL').fetchone()['n']==99
        applied=assign_reviewed_resort(reviewed(),apply=True)
        assert applied['configurations_to_update']==90
        assert assign_reviewed_resort(reviewed(),apply=True)['configurations_to_update']==0
        counts={row['resort_id']:row['n'] for row in get_db().execute('SELECT resort_id,count(*) AS n FROM configurations GROUP BY resort_id')}
        assert counts=={'cs':90,None:9}
        assert get_db().execute("SELECT count(*) AS n FROM configurations WHERE validated OR options <> '[]'::jsonb").fetchone()['n']==0
        assert get_db().execute('SELECT count(*) AS n FROM resources WHERE validated').fetchone()['n']==0
        assert get_db().execute('SELECT count(*) AS n FROM audit WHERE entity_type=%s AND action=%s',('configuration','classify')).fetchone()['n']==90
    assert api.detail(booking)['status']=='pending'
    assert api.config(7)['resort_id']=='cs'
    assert api.config(10)['resort_id']=='cs'
    assert all(api.config(code)['resort_id']=='cs' for code in (20,21,22,24))


def test_reviewed_assignment_rejects_other_resort_atomically(app):
    with app.app_context():
        get_db().execute("UPDATE configurations SET resort_id='rq' WHERE id='space_007'")
        with pytest.raises(Problem,match='outro empreendimento'):
            assign_reviewed_resort(reviewed(),apply=True)
        assert get_db().execute('SELECT count(*) AS n FROM configurations WHERE resort_id=%s',('cs',)).fetchone()['n']==0


def test_reviewed_assignment_rejects_partial_arena_group(app):
    data=reviewed()
    data['codigos_fonte'].remove(90)
    data['codigos_pendentes'].append(90)
    with app.app_context(),pytest.raises(Problem,match='agrupa códigos'):
        assign_reviewed_resort(data,apply=True)


def test_rio_quente_assignment_requires_prior_classification_and_preserves_pending(api,app):
    booking=api.create(code=31,status='pending').json
    with app.app_context():
        with pytest.raises(Problem,match='classificações anteriores'):
            assign_reviewed_resort(rio_quente(),apply=True)
        assert get_db().execute('SELECT count(*) AS n FROM configurations WHERE resort_id IS NOT NULL').fetchone()['n']==0
        assign_reviewed_resort(reviewed(),apply=True)
        preview=assign_reviewed_resort(rio_quente())
        assert preview['source_codes']==9
        assert preview['configurations_to_update']==9
        assert preview['resources_to_update']==6
        assign_reviewed_resort(rio_quente(),apply=True)
        assert assign_reviewed_resort(rio_quente(),apply=True)['configurations_to_update']==0
        counts={row['resort_id']:row['n'] for row in get_db().execute('SELECT resort_id,count(*) AS n FROM configurations GROUP BY resort_id')}
        assert counts=={'cs':90,'rq':9}
        group=get_db().execute('SELECT resort_id,validated,options FROM configurations WHERE id=%s',('space_035',)).fetchone()
        assert group['resort_id']=='rq' and group['validated'] is False and group['options']==[]
        assert get_db().execute('SELECT resort_id FROM resources WHERE id=%s',('resource_031',)).fetchone()['resort_id']=='rq'
    assert api.detail(booking)['status']=='pending'
