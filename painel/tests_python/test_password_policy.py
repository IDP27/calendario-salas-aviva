from werkzeug.security import generate_password_hash

from calendar_app.db import write_transaction


def test_new_passwords_allow_long_passphrases(api):
    base = {
        "username": "newuser",
        "name": "Pessoa nova",
        "team_id": "commercial",
        "scopes": ["cs"],
    }
    for password in ("x" * 14, "x" * 129):
        response = api.send("/users", {**base, "password": password})
        assert response.status_code == 400
        assert "15 a 128 caracteres" in response.json["error"]
    common = api.send("/users", {**base, "password": "password12345678"})
    assert common.status_code == 400
    assert "menos comum" in common.json["error"]
    for username, password in (
        ("fifteen", "x" * 15),
        ("long", "x" * 128),
        ("phrase", "uma frase longa e segura"),
    ):
        response = api.send(
            "/users", {**base, "username": username, "password": password}
        )
        assert response.status_code == 201


def test_password_change_accepts_new_limit_and_legacy_login(app, api):
    legacy_password = "Senha#2026"
    with app.app_context(), write_transaction() as conn:
        conn.execute(
            "UPDATE users SET password_hash=%s WHERE username=%s",
            (generate_password_hash(legacy_password), "seller"),
        )

    client = app.test_client()
    csrf = client.get("/api/session").json["csrf"]
    login = client.post(
        "/api/login",
        json={"username": "seller", "password": legacy_password},
        headers={"X-CSRF-Token": csrf},
    )
    assert login.status_code == 200

    for new_password in ("x" * 14, "x" * 129):
        rejected = client.post(
            "/api/password",
            json={"current_password": legacy_password, "password": new_password},
            headers={"X-CSRF-Token": login.json["csrf"]},
        )
        assert rejected.status_code == 400

    common = client.post(
        "/api/password",
        json={"current_password": legacy_password, "password": "password12345678"},
        headers={"X-CSRF-Token": login.json["csrf"]},
    )
    assert common.status_code == 400

    changed = client.post(
        "/api/password",
        json={
            "current_password": legacy_password,
            "password": "Nova senha segura 2026",
        },
        headers={"X-CSRF-Token": login.json["csrf"]},
    )
    assert changed.status_code == 200
    client.post("/api/logout", headers={"X-CSRF-Token": login.json["csrf"]})
    csrf = client.get("/api/session").json["csrf"]
    assert (
        client.post(
            "/api/login",
            json={"username": "seller", "password": "Nova senha segura 2026"},
            headers={"X-CSRF-Token": csrf},
        ).status_code
        == 200
    )
