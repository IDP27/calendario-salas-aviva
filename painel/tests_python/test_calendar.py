import json
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from uuid import uuid4

import pytest
from conftest import API, PASSWORD, allocation, edit_body
from flask import g

from calendar_app import ROOT
from calendar_app.common import Problem
from calendar_app.db import get_db, write_transaction


def test_import_preserves_source_without_inventing_resources(api, app):
    data = api.get("/catalog").json
    assert (
        data["source_count"] == 125
        and len(data["configurations"]) == 99
        and len(data["resources"]) == 63
    )
    assert all(
        c["resort_id"] is None and c["validated"] is False and not c["options"]
        for c in data["configurations"]
    )
    assert len([c for c in data["configurations"] if c["id"].startswith("arena_")]) == 4
    assert not any(
        c["id"] in ["space_005", "space_006"] for c in data["configurations"]
    )
    assert api.config(13)["id"] != api.config(62)["id"]


def test_import_preview_idempotency_and_invalid_preserves_data(api):
    source = json.loads((ROOT / "docs/catalogo-salas-preliminar.json").read_text())
    assert api.send("/catalog/import", {"catalog": source}).json["already_imported"]
    assert (
        api.send("/catalog/import", {"catalog": source, "confirm": True}).json["new"]
        == 0
    )
    source["itens"][1]["codigo_fonte"] = 1
    assert (
        api.send("/catalog/import", {"catalog": source, "confirm": True}).status_code
        == 400
    )
    assert api.get("/catalog").json["source_count"] == 125


def test_unvalidated_reservation_does_not_block_until_scheduler_confirms(api, app):
    b = api.create(status="reserved")
    assert b.status_code == 201
    assert api.create().status_code == 201
    assert API(app, "seller").create(status="confirmed").status_code == 409
    calendar = api.get("/calendar?from=2027-01-01&to=2027-01-31").json
    c = next(c for c in calendar["configurations"] if c["id"] == "space_007")
    assert c["days"]["2027-01-10"]["state"] == "unvalidated"
    assert b.json["id"] in c["days"]["2027-01-10"]["requests"]
    assert len(c["days"]["2027-01-10"]["requests"]) == 2
    assert api.confirm(b.json).status_code == 200
    updated = api.get("/calendar?from=2027-01-01&to=2027-01-31").json
    c = next(c for c in updated["configurations"] if c["id"] == "space_007")
    assert c["days"]["2027-01-10"]["state"] == "occupied"


def test_scheduler_confirmation_blocks_unvalidated_space_for_other_users(api, app):
    seller = API(app, "seller")
    ops = API(app, "ops")
    first = seller.create(
        code=4, status="reserved", start="2026-12-25", end="2026-12-26"
    ).json
    assert (
        seller.send(
            f"/bookings/{first['id']}/confirm", {"version": first["version"]}
        ).status_code
        == 403
    )
    confirmed = api.send(
        f"/bookings/{first['id']}/confirm", {"version": first["version"]}
    )
    assert confirmed.status_code == 200 and confirmed.json["status"] == "confirmed"
    availability = api.get("/availability?from=2026-12-25&to=2026-12-26").json[
        "results"
    ]
    baea = next(r for r in availability if r["id"] == "space_004")
    assert baea["available"] is False
    assert baea["periods"] == [
        {
            "status": "confirmed",
            "phase": "event",
            "start_date": "2026-12-25",
            "end_date": "2026-12-26",
            "related": False,
        }
    ]
    calendar = api.get("/calendar?from=2026-12-01&to=2026-12-31").json["configurations"]
    baea = next(r for r in calendar if r["id"] == "space_004")
    assert baea["days"]["2026-12-25"]["state"] == "occupied"
    assert confirmed.json["id"] in baea["days"]["2026-12-25"]["bookings"]
    assert (
        ops.create(
            code=4, status="reserved", start="2026-12-25", end="2026-12-26"
        ).status_code
        == 409
    )
    assert (
        seller.send(
            f"/bookings/{first['id']}/cancel",
            {"version": confirmed.json["version"], "reason": "Liberado"},
        ).status_code
        == 200
    )
    other = ops.create(
        code=4, status="reserved", start="2026-12-25", end="2026-12-26"
    ).json
    assert (
        api.send(
            f"/bookings/{other['id']}/confirm", {"version": other["version"]}
        ).status_code
        == 200
    )


def test_confirmation_of_multiple_spaces_is_atomic(api, app):
    occupied = api.create(
        code=4, status="confirmed", start="2027-01-10", end="2027-01-12"
    )
    assert occupied.status_code == 201
    seller = API(app, "seller")
    assert (
        seller.create(
            status="reserved", allocations=[allocation(4), allocation(7)]
        ).status_code
        == 409
    )
    free = api.get("/availability?from=2027-01-10&to=2027-01-12").json["results"]
    assert next(r for r in free if r["id"] == "space_007")["available"] is None


def test_concurrent_confirmations_cannot_double_book_unvalidated_space(api, app):
    first = api.create(code=4, status="reserved").json
    second = api.create(code=4, status="reserved").json
    clients = [API(app), API(app)]
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(
            pool.map(
                lambda pair: (
                    pair[0]
                    .send(
                        f"/bookings/{pair[1]['id']}/confirm",
                        {"version": pair[1]["version"]},
                    )
                    .status_code
                ),
                zip(clients, [first, second]),
            )
        )
    assert sorted(outcomes) == [200, 409]
    assert sum(api.detail(b)["status"] == "confirmed" for b in (first, second)) == 1


def test_availability_shows_reserved_request_separately_from_occupation(api):
    reserved = api.create(
        code=4, status="reserved", start="2026-12-25", end="2026-12-26"
    ).json

    def baea(first="2026-12-25", last="2026-12-26"):
        results = api.get(f"/availability?from={first}&to={last}").json["results"]
        return next(row for row in results if row["id"] == "space_004")

    assert baea()["reserved_count"] == 1
    assert baea()["available"] is None
    assert baea()["periods"] == [
        {
            "status": "reserved",
            "phase": "event",
            "start_date": "2026-12-25",
            "end_date": "2026-12-26",
            "related": False,
        }
    ]
    assert baea("2026-12-27", "2026-12-27")["reserved_count"] == 0
    assert baea("2026-12-27", "2026-12-27")["periods"] == []
    api.validate(4)
    assert baea()["available"] is True
    second = api.create(code=4, start="2026-12-25", end="2026-12-26").json
    assert baea()["reserved_count"] == 2
    assert baea()["available"] is True
    assert api.confirm(second).status_code == 409
    assert api.confirm(reserved).status_code == 200
    assert baea()["reserved_count"] == 1
    assert baea()["available"] is False
    assert [
        (p["status"], p["start_date"], p["end_date"]) for p in baea()["periods"]
    ] == [
        ("confirmed", "2026-12-25", "2026-12-26"),
        ("reserved", "2026-12-25", "2026-12-26"),
    ]
    assert api.detail(second)["status"] == "reserved"


@pytest.mark.parametrize("first,second", [(10, 7), (7, 10)])
def test_configurations_conflict_with_components_both_directions(api, first, second):
    for n in (7, 8, 10):
        api.validate(n)
    b = api.create(code=first).json
    assert api.confirm(b).status_code == 200
    availability = api.get("/availability?from=2027-01-10&to=2027-01-12").json[
        "results"
    ]
    affected = next(r for r in availability if r["id"] == f"space_{second:03}")
    assert any(
        p["related"]
        and p["status"] == "confirmed"
        and p["start_date"] == "2027-01-10"
        and p["end_date"] == "2027-01-12"
        for p in affected["periods"]
    )
    assert api.create(code=second).status_code == 409


def test_disjoint_spaces_and_waiting_can_overlap(api):
    api.validate(7)
    api.validate(8)
    a = api.create().json
    b = api.create(code=8).json
    c = api.create().json
    assert api.confirm(a).status_code == 200
    assert api.confirm(b).status_code == 200
    assert api.confirm(c).status_code == 409


def test_waiting_combination_is_visible_on_its_components(api):
    for code in (7, 8, 10):
        api.validate(code)
    waiting = api.create(code=10).json
    calendar = api.get("/calendar?from=2027-01-01&to=2027-01-31").json
    for code in (7, 8, 10):
        row = next(
            c for c in calendar["configurations"] if c["id"] == f"space_{code:03}"
        )
        assert waiting["id"] in row["days"]["2027-01-10"]["requests"]
        assert row["days"]["2027-01-10"]["state"] == "available"


def test_access_revoked_while_mutation_waits_cannot_commit(api, app):
    with app.test_request_context("/api/bookings"):
        conn = get_db()
        g.user = conn.execute(
            "SELECT * FROM users WHERE id=%s", (api.user["id"],)
        ).fetchone()
        conn.execute(
            "UPDATE users SET active=false,version=version+1 WHERE id=%s",
            (api.user["id"],),
        )
        with pytest.raises(Problem, match="acesso foi atualizado"):
            with write_transaction():
                pytest.fail("A operação não pode iniciar com o acesso revogado.")


def test_fifo_manual_and_no_automatic_confirmation(api):
    api.validate(7)
    a = api.create().json
    b = api.create().json
    assert api.confirm(b).status_code == 409
    active = api.confirm(a).json
    assert (
        api.send(
            f"/bookings/{a['id']}/cancel",
            {"version": active["version"], "reason": "Teste de liberação"},
        ).status_code
        == 200
    )
    assert api.detail(b)["status"] == "reserved"
    assert api.confirm(api.detail(b)).status_code == 200


def test_atomic_multi_space_failure_leaves_no_partial_occupation(api, app):
    api.validate(7)
    api.validate(8)
    held = api.create(code=8).json
    api.confirm(held)
    assert api.create(allocations=[allocation(7), allocation(8)]).status_code == 409
    with app.app_context():
        assert (
            get_db().execute("SELECT count(*) AS n FROM bookings").fetchone()["n"] == 1
        )
        assert (
            get_db().execute("SELECT count(*) AS n FROM occupations").fetchone()["n"]
            == 3
        )


def test_concurrent_confirmations_never_double_occupy(api, app):
    api.validate(7)
    a = api.create().json
    b = api.create().json
    clients = [API(app), API(app)]
    with ThreadPoolExecutor(max_workers=2) as pool:
        codes = list(
            pool.map(
                lambda pair: pair[0].confirm(pair[1]).status_code, zip(clients, [a, b])
            )
        )
    assert sorted(codes) == [200, 409]
    with app.app_context():
        rows = list(get_db().execute("SELECT * FROM occupations"))
        assert len(rows) == 3 and len({r["booking_id"] for r in rows}) == 1


def test_team_edit_permissions_and_scheduler_exception(api, app):
    api.validate(7)
    ops = API(app, "ops")
    seller = API(app, "seller")
    b = ops.create().json
    assert (
        api.send(
            f"/bookings/{b['id']}", edit_body(b, title="Não permitido"), method="PUT"
        ).status_code
        == 403
    )
    assert (
        api.send(
            f"/bookings/{b['id']}/cancel",
            {"version": b["version"], "reason": "Não permitido"},
        ).status_code
        == 403
    )
    assert seller.confirm(b).status_code == 403
    assert (
        ops.send(
            f"/bookings/{b['id']}", edit_body(b, status="confirmed"), method="PUT"
        ).status_code
        == 409
    )
    confirmed = api.confirm(b)
    assert confirmed.status_code == 200 and confirmed.json["team_id"] == "operations"
    assert api.confirm(confirmed.json).status_code == 409
    changed = allocation(
        7,
        "2027-01-11",
        "2027-01-12",
        resources=confirmed.json["allocations"][0]["resources"],
    )
    assert (
        ops.send(
            f"/bookings/{b['id']}",
            edit_body(confirmed.json, allocations=[changed]),
            method="PUT",
        ).status_code
        == 403
    )
    assert seller.create(status="reserved", team_id="operations").status_code == 403


def test_catalog_role_does_not_grant_queue_or_booking_edit(api, app):
    reviewer = API(app, "reviewer")
    api.validate(7)
    b = api.create().json
    assert reviewer.confirm(b).status_code == 403
    assert (
        reviewer.send(f"/bookings/{b['id']}", edit_body(b), method="PUT").status_code
        == 403
    )


def test_stale_version_preserves_newer_content(api):
    b = api.create(status="reserved").json
    assert (
        api.send(
            f"/bookings/{b['id']}", edit_body(b, title="Mais recente"), method="PUT"
        ).status_code
        == 200
    )
    assert (
        api.send(
            f"/bookings/{b['id']}", edit_body(b, title="Antigo"), method="PUT"
        ).status_code
        == 409
    )
    assert api.detail(b)["title"] == "Mais recente"


def test_idempotency_replays_same_create_and_rejects_changed_payload(api):
    body = {
        "title": "Idempotente",
        "responsible": "Equipe",
        "status": "reserved",
        "allocations": [allocation(7)],
    }
    key = str(uuid4())
    a = api.send("/bookings", body, key=key)
    b = api.send("/bookings", body, key=key)
    assert a.json["id"] == b.json["id"]
    assert api.send("/bookings", {**body, "title": "Outro"}, key=key).status_code == 409


@pytest.mark.parametrize(
    "start,end,expected",
    [
        ("2028-02-29", "2028-02-29", 201),
        ("2026-02-29", "2026-03-01", 400),
        ("2028-12-31", "2028-12-31", 201),
        ("2027-12-30", "2028-01-02", 201),
        ("2025-12-31", "2026-01-02", 400),
        ("2028-12-31", "2029-01-01", 400),
        ("2027-01-12", "2027-01-10", 400),
    ],
)
def test_dates(api, start, end, expected):
    b = api.create(status="reserved", start=start, end=end)
    assert b.status_code == expected, b.json
    if end == "2028-12-31" and expected == 201:
        assert b.json["allocations"][0]["end_exclusive"] == "2029-01-01"


def test_overlapping_phases_union_and_edit_preserves_other_phase(api, app):
    api.validate(7)
    a = allocation(7, "2028-02-28", "2028-02-29", "setup")
    b = allocation(7, "2028-02-29", "2028-03-02", "event")
    booking = api.create(allocations=[a, b]).json
    active = api.confirm(booking).json
    with app.app_context():
        assert (
            get_db().execute("SELECT count(*) AS n FROM occupations").fetchone()["n"]
            == 4
        )
    edited = api.send(
        f"/bookings/{active['id']}", edit_body(active, allocations=[b]), method="PUT"
    )
    assert edited.status_code == 200
    with app.app_context():
        assert [
            r["day"]
            for r in get_db().execute("SELECT day FROM occupations ORDER BY day")
        ] == [date(2028, 2, 29), date(2028, 3, 1), date(2028, 3, 2)]


def test_classification_preserves_bookings_and_conflicts(api, app):
    c = api.validate(7)
    a = api.create().json
    active = api.confirm(a).json
    classified = api.send(
        "/catalog/classify",
        {
            "changes": [{"id": c["id"], "version": c["version"]}],
            "resort_id": "cs",
            "location": "Local confirmado no teste",
            "reason": "Validação fictícia de teste",
        },
    )
    assert classified.status_code == 200
    after = api.detail(active)
    for key in ("id", "version", "status", "team_id", "queue_number"):
        assert after[key] == active[key]
    assert after["allocations"][0]["resort_id"] == "cs"
    assert api.create().status_code == 409
    c = api.config(7)
    assert (
        api.send(
            "/catalog/classify",
            {
                "changes": [{"id": c["id"], "version": c["version"]}],
                "resort_id": None,
                "reason": "Correção",
            },
        ).status_code
        == 400
    )
    assert (
        api.send(
            "/resources",
            {
                "name": "Recurso de teste",
                "evidence": "Conferência de teste",
                "resort_id": None,
            },
        ).status_code
        == 400
    )
    assert api.detail(active)["id"] == active["id"]


def test_reclassification_rechecks_scope(api, app):
    created = api.send(
        "/users",
        {
            "username": "limited",
            "name": "Restrito",
            "password": PASSWORD,
            "team_id": "commercial",
            "scopes": ["unassigned"],
        },
    )
    assert created.status_code == 201
    limited = API(app, "limited")
    b = limited.create(status="reserved").json
    c = api.config(7)
    api.send(
        "/catalog/classify",
        {
            "changes": [{"id": c["id"], "version": c["version"]}],
            "resort_id": "cs",
            "reason": "Mudança cadastral",
        },
    )
    assert limited.get(f"/bookings/{b['id']}").status_code == 403
    assert not any(
        c["id"] == "space_007" for c in limited.get("/catalog").json["configurations"]
    )


def test_edit_waiting_period_reenters_queue(api):
    api.validate(7)
    a = api.create().json
    b = api.create().json
    edited = api.send(
        f"/bookings/{a['id']}",
        edit_body(a, allocations=[allocation(7, "2027-01-11", "2027-01-13")]),
        method="PUT",
    ).json
    assert edited["queue_number"] > b["queue_number"]


def test_active_edit_conflict_rolls_back_original(api):
    api.validate(7)
    a = api.confirm(api.create(start="2027-01-10", end="2027-01-10").json).json
    b = api.confirm(api.create(start="2027-01-11", end="2027-01-11").json).json
    bad = api.send(
        f"/bookings/{a['id']}",
        edit_body(a, allocations=[allocation(7, "2027-01-10", "2027-01-11")]),
        method="PUT",
    )
    assert bad.status_code == 409
    assert api.detail(a)["version"] == a["version"]
    assert api.detail(a)["allocations"][0]["end_date"] == "2027-01-10"
    assert api.detail(b)["status"] == "confirmed"


def test_topology_cannot_change_under_waiting_or_active_request(api):
    c = api.validate(10)
    api.create(code=10)
    assert (
        api.send(
            f"/catalog/{c['id']}/topology",
            {
                "version": c["version"],
                "attested": True,
                "reason": "Mudança",
                "options": [["resource_007"]],
            },
        ).status_code
        == 409
    )


def test_arena_variants_share_one_configuration_per_quantity(api):
    sources = api.get("/catalog/sources").json["items"]
    assert len({s["configuration_id"] for s in sources if 90 <= s["code"] <= 97}) == 1
    assert len({s["configuration_id"] for s in sources if 90 <= s["code"] <= 117}) == 4
    assert any(
        c for c in api.get("/catalog").json["configurations"] if c["id"] == "arena_1"
    )
    reserved = api.create(allocations=[allocation("arena_1")])
    assert reserved.status_code == 201
    assert api.confirm(reserved.json).status_code == 200


def test_period_filter_is_intersection_and_csv_safe(api):
    api.create(
        status="reserved",
        start="2027-12-29",
        end="2028-01-03",
        title='=Evento; "teste"',
    )
    rows = api.get("/bookings?from=2028-01-01&to=2028-01-01").json["bookings"]
    assert len(rows) == 1
    csv = api.get("/reports.csv?from=2028-01-01&to=2028-01-01").data.decode()
    assert csv.startswith("\ufeff") and "'=Evento" in csv and '""teste""' in csv
    assert not api.get("/bookings?from=2028-02-01&to=2028-02-28").json["bookings"]


def test_two_independent_sessions_see_committed_changes(api, app):
    other = API(app, "ops")
    b = api.create(status="reserved", title="Visível nas duas equipes").json
    assert other.detail(b)["title"] == "Visível nas duas equipes"
    api.send(f"/bookings/{b['id']}", edit_body(b, title="Atualizado"), method="PUT")
    assert other.detail(b)["title"] == "Atualizado"


def test_csrf_auth_and_static_security(app, api):
    anon = app.test_client()
    assert anon.get("/api/catalog").status_code == 401
    assert api.client.post("/api/bookings", json={}).status_code == 403
    assert app.test_client().get("/").status_code == 200
    assert app.test_client().get("/static/../.env").status_code == 404
    assert "frame-ancestors" in api.get("/catalog").headers["Content-Security-Policy"]


def test_capacity_absence_source_notes_and_resort_filter(api):
    assert api.config(38)["technical"]["area_m2"] is None
    assert "Não comporta" in api.config(38)["notes"]
    assert not api.get("/calendar?from=2027-01-01&to=2027-01-31&resort=cs").json[
        "configurations"
    ]
    assert (
        len(
            api.get("/calendar?from=2027-01-01&to=2027-01-31&resort=unassigned").json[
                "configurations"
            ]
        )
        == 99
    )


def test_user_deactivation_revokes_existing_session(api, app):
    seller = API(app, "seller")
    u = next(u for u in api.get("/users").json["users"] if u["username"] == "seller")
    result = api.send(f"/users/{u['id']}", {**u, "active": False}, method="PUT")
    assert result.status_code == 200
    assert seller.get("/catalog").status_code == 401
