"""Prepare container secrets, initialize a new database and run the app or CLI."""

import json
import os
import sys
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent


def _secret(path_variable):
    path = os.environ.get(path_variable)
    if not path:
        raise RuntimeError(f"Segredo obrigatório ausente: {path_variable}")
    value = Path(path).read_text(encoding="utf-8").strip()
    if not value:
        raise RuntimeError(f"Segredo vazio: {path_variable}")
    return value


def configure_environment():
    password = _secret("DB_PASSWORD_FILE")
    user = os.environ.get("DB_USER", "calendario")
    host = os.environ.get("DB_HOST", "db")
    name = os.environ.get("DB_NAME", "calendario")
    if not all((user, host, name)):
        raise RuntimeError("Configure DB_USER, DB_HOST e DB_NAME.")
    os.environ["DATABASE_URL"] = (
        f"postgresql://{quote(user, safe='')}:{quote(password, safe='')}"
        f"@{host}/{quote(name, safe='')}"
    )
    os.environ["CALENDAR_SECRET_KEY"] = _secret("CALENDAR_SECRET_KEY_FILE")
    if os.environ.get("CALENDAR_AUTH_MODE") == "entra":
        os.environ["ENTRA_CLIENT_SECRET"] = _secret("ENTRA_CLIENT_SECRET_FILE")


def initialize():
    from calendar_app import create_app
    from calendar_app.catalog import assign_reviewed_resort, import_catalog
    from calendar_app.db import migrate

    app = create_app()
    with app.app_context():
        migrate()
        catalog = json.loads(
            (ROOT / "docs/catalogo-salas-preliminar.json").read_text(encoding="utf-8")
        )
        result = import_catalog(catalog)
        if result["new"] == 125:
            for filename in (
                "classificacao-costa-sauipe-2026-10-08.json",
                "classificacao-rio-quente-2026-10-08.json",
            ):
                reviewed = json.loads(
                    (ROOT / "docs" / filename).read_text(encoding="utf-8")
                )
                assign_reviewed_resort(reviewed, apply=True)
        app.logger.info("Banco e catálogo preparados para iniciar a agenda.")
    return app


def main():
    configure_environment()
    if len(sys.argv) == 2 and sys.argv[1] == "serve":
        from waitress import serve

        app = initialize()
        serve(app, host="0.0.0.0", port=4174, threads=6)
    elif len(sys.argv) > 1:
        os.execvpe(sys.argv[1], sys.argv[1:], os.environ)
    else:
        raise SystemExit(
            "Use 'serve' ou um comando administrativo, por exemplo 'flask'."
        )


if __name__ == "__main__":
    main()
