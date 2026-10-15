"""Account administration with version checks, audit and session revocation."""

import secrets

from werkzeug.security import generate_password_hash

from .auth import create_user, public_user, security_event
from .common import (
    Problem,
    audit,
    ensure_version,
    json_value,
    require_capability,
    serialize,
)
from .db import get_db, write_transaction


def list_people(actor):
    require_capability(actor, "can_manage_users")
    rows = get_db().execute(
        "SELECT * FROM users WHERE deleted_at IS NULL ORDER BY name"
    )
    return [public_user(user) for user in rows]


def create_person(actor, data):
    require_capability(actor, "can_manage_users")
    with write_transaction() as conn:
        user = create_user(conn, data, actor)
    return public_user(user)


def update_access(actor, user_id, data):
    require_capability(actor, "can_manage_users")
    with write_transaction() as conn:
        user = conn.execute(
            "SELECT * FROM users WHERE id=%s AND deleted_at IS NULL", (user_id,)
        ).fetchone()
        if not user:
            raise Problem("Usuário não encontrado.", 404)
        ensure_version(user, data)
        if user_id == actor["id"]:
            raise Problem("Peça a outro administrador para alterar seu próprio acesso.")
        scopes = data.get("scopes", user["scopes"])
        if (
            not isinstance(scopes, list)
            or not scopes
            or any(scope not in ("cs", "rq", "unassigned") for scope in scopes)
        ):
            raise Problem("Escopo inválido.")
        conn.execute(
            """UPDATE users SET scopes=%s,can_catalog=%s,can_schedule=%s,
                      can_manage_users=%s,active=%s,version=version+1 WHERE id=%s""",
            (
                json_value(scopes),
                data.get("can_catalog") is True,
                data.get("can_schedule") is True,
                data.get("can_manage_users") is True,
                data.get("active") is True,
                user_id,
            ),
        )
        conn.execute(
            "UPDATE auth_sessions SET revoked_at=now() WHERE user_id=%s AND revoked_at IS NULL",
            (user_id,),
        )
        after = conn.execute("SELECT * FROM users WHERE id=%s", (user_id,)).fetchone()
        audit(
            conn,
            actor,
            "user",
            user_id,
            "access_update",
            public_user(user),
            public_user(after),
        )
        security_event(
            conn, "access_change", "accepted", user_id, reason="sessions_revoked"
        )
        return public_user(after)


def delete_person(actor, user_id, data):
    require_capability(actor, "can_manage_users")
    if user_id == actor["id"]:
        raise Problem("Você não pode excluir seu próprio acesso.")
    with write_transaction() as conn:
        user = conn.execute(
            "SELECT * FROM users WHERE id=%s AND deleted_at IS NULL", (user_id,)
        ).fetchone()
        if not user:
            raise Problem("Usuário não encontrado.", 404)
        ensure_version(user, data)
        conn.execute(
            """UPDATE users SET username=%s,name='Pessoa excluída',active=false,
                      scopes='[]'::jsonb,can_catalog=false,can_schedule=false,
                      can_manage_users=false,entra_tenant_id=NULL,entra_object_id=NULL,
                      password_hash=%s,deleted_at=now(),version=version+1 WHERE id=%s""",
            (
                "deleted-" + user_id,
                generate_password_hash(secrets.token_urlsafe(48)),
                user_id,
            ),
        )
        conn.execute(
            "UPDATE auth_sessions SET revoked_at=now() WHERE user_id=%s AND revoked_at IS NULL",
            (user_id,),
        )
        audit(
            conn,
            actor,
            "user",
            user_id,
            "delete",
            public_user(user),
            {"deleted": True},
            "Acesso excluído; vínculos históricos preservados.",
        )
        security_event(
            conn, "access_delete", "accepted", user_id, reason="sessions_revoked"
        )
    return {"deleted": True}


def access_history(actor):
    require_capability(actor, "can_manage_users")
    rows = get_db().execute(
        """SELECT e.id,e.occurred_at,e.event_type,e.result,e.session_id,
                  e.request_id,e.reason,u.name AS user_name
           FROM auth_events e LEFT JOIN users u ON u.id=e.user_id
           ORDER BY e.id DESC LIMIT 300"""
    )
    return serialize({"events": list(rows)})
