import hashlib
import json
import unicodedata
from datetime import date, timedelta

from .catalog import all_catalog, config_access, resources_map
from .common import (
    Problem,
    audit,
    ensure_version,
    json_value,
    required_text,
    serialize,
    uid,
)
from .db import get_db, write_transaction

LABELS = {"reserved": "Reservado", "confirmed": "Confirmado", "cancelled": "Cancelado"}
ACTIVE = {"confirmed"}


def day(value):
    try:
        if not isinstance(value, str) or len(value) != 10:
            raise ValueError()
        result = date.fromisoformat(value)
        if result.isoformat() != value:
            raise ValueError()
        return result
    except (ValueError, TypeError):
        raise Problem("Informe uma data válida no formato AAAA-MM-DD.")


def period(start, end):
    first, last = day(start), day(end)
    if first > last or first < date(2026, 1, 1) or last > date(2028, 12, 31):
        raise Problem(
            "O período deve estar entre 01/01/2026 e 31/12/2028, com término igual ou posterior ao início."
        )
    return first, last + timedelta(days=1)


def get_booking(conn, booking_id):
    booking = conn.execute(
        "SELECT b.*, t.name AS team_name,u.name AS creator_name FROM bookings b JOIN teams t ON t.id=b.team_id JOIN users u ON u.id=b.created_by WHERE b.id=%s",
        (booking_id,),
    ).fetchone()
    if not booking:
        raise Problem("Solicitação não encontrada.", 404)
    booking["allocations"] = list(
        conn.execute(
            "SELECT a.*,c.name AS space_name,c.resort_id,c.location FROM allocations a JOIN configurations c ON c.id=a.configuration_id WHERE booking_id=%s ORDER BY a.id",
            (booking_id,),
        )
    )
    for a in booking["allocations"]:
        a["end_date"] = a["end_exclusive"] - timedelta(days=1)
    return booking


def accessible(actor, booking, configs=None, resources=None):
    configs = configs if configs is not None else {c["id"]: c for c in all_catalog()}
    resources = resources if resources is not None else resources_map()
    return all(
        a["configuration_id"] in configs
        and config_access(actor, configs[a["configuration_id"]], resources)
        for a in booking["allocations"]
    )


def cells(allocations):
    result = set()
    for a in allocations:
        start = (
            a["start_date"]
            if isinstance(a["start_date"], date)
            else day(a["start_date"])
        )
        end = (
            a["end_exclusive"]
            if isinstance(a["end_exclusive"], date)
            else day(a["end_exclusive"])
        )
        for offset in range((end - start).days):
            result.update(
                (rid, start + timedelta(days=offset)) for rid in a["resources"]
            )
    return result


def normalize_allocations(
    conn, actor, raw, status, allow_unvalidated_confirmation=False
):
    if not isinstance(raw, list) or not 1 <= len(raw) <= 40:
        raise Problem("Inclua de 1 a 40 períodos/espaços.")
    configs = {c["id"]: c for c in all_catalog(conn)}
    resources = resources_map(conn)
    result = []
    for item in raw:
        if not isinstance(item, dict):
            raise Problem("Período inválido.")
        conf = configs.get(item.get("configuration_id"))
        if not conf or not conf["active"]:
            raise Problem("Selecione um espaço ativo do catálogo.")
        if not config_access(actor, conf, resources):
            raise Problem("Espaço fora do seu escopo.", 403)
        first, end = period(item.get("start_date"), item.get("end_date"))
        phase = item.get("phase", "event")
        if phase not in ("setup", "event", "teardown"):
            raise Problem("Fase inválida.")
        chosen = item.get("resources")
        if chosen is None:
            chosen = conf["options"][0] if len(conf["options"]) == 1 else []
        if status == "confirmed" and not chosen and len(conf["options"]) == 1:
            chosen = conf["options"][0]
        if (
            not isinstance(chosen, list)
            or any(not isinstance(r, str) for r in chosen)
            or len(set(chosen)) != len(chosen)
        ):
            raise Problem("Seleção física inválida.")
        chosen = sorted(chosen)
        valid = (
            conf["validated"]
            and chosen
            and chosen in conf["options"]
            and all(
                resources.get(r, {}).get("validated") and resources[r]["active"]
                for r in chosen
            )
        )
        provisional_confirmed = (
            status == "confirmed"
            and allow_unvalidated_confirmation
            and not conf["validated"]
            and not chosen
        )
        if status == "confirmed" and not valid and not provisional_confirmed:
            raise Problem(
                f"{conf['name']}: a composição física precisa ser validada antes da confirmação.",
                422,
            )
        if chosen and not valid:
            raise Problem(
                "Não use uma composição que ainda não foi homologada. Remova a seleção para registrar a pendência.",
                422,
            )
        result.append(
            {
                "configuration_id": conf["id"],
                "phase": phase,
                "start_date": first,
                "end_exclusive": end,
                "resources": chosen,
            }
        )
    # Stable normalization lets repeated/overlapping phases produce a physical set, not duplicates.
    return sorted(
        result,
        key=lambda a: (
            a["configuration_id"],
            a["start_date"],
            a["end_exclusive"],
            a["phase"],
            a["resources"],
        ),
    )


def occupation_conflicts(conn, wanted, exclude=None):
    if not wanted:
        return set()
    first = min(d for _, d in wanted)
    last = max(d for _, d in wanted)
    occupied = conn.execute(
        "SELECT * FROM occupations WHERE day BETWEEN %s AND %s AND booking_id<>%s",
        (first, last, exclude or ""),
    )
    return {(r["resource_id"], r["day"]) for r in occupied} & wanted


def configuration_conflicts(conn, allocations, exclude=None):
    for a in allocations:
        conflict = conn.execute(
            """SELECT 1 FROM allocations other
                                 JOIN bookings b ON b.id=other.booking_id
                                 WHERE b.status='confirmed' AND b.id<>%s
                                   AND other.configuration_id=%s
                                   AND other.start_date<%s AND other.end_exclusive>%s LIMIT 1""",
            (exclude or "", a["configuration_id"], a["end_exclusive"], a["start_date"]),
        ).fetchone()
        if conflict:
            return True
    return False


def ensure_priority(conn, booking, wanted, old_cells=None, allocations=None):
    if allocations and configuration_conflicts(conn, allocations, booking["id"]):
        raise Problem(
            "Este espaço já está reservado no período informado. Nenhuma sala foi reservada parcialmente.",
            409,
        )
    for a in allocations or []:
        earlier = conn.execute(
            """SELECT 1 FROM allocations other JOIN bookings b ON b.id=other.booking_id
                                WHERE b.status='reserved' AND b.queue_number<%s AND b.id<>%s
                                  AND other.configuration_id=%s
                                  AND other.start_date<%s AND other.end_exclusive>%s LIMIT 1""",
            (
                booking["queue_number"],
                booking["id"],
                a["configuration_id"],
                a["end_exclusive"],
                a["start_date"],
            ),
        ).fetchone()
        if earlier:
            raise Problem(
                "Uma solicitação anterior tem prioridade para este espaço e período. Consulte a fila.",
                409,
            )
    if occupation_conflicts(conn, wanted, booking["id"]):
        raise Problem(
            "Há ocupação efetiva em pelo menos um espaço/dia. Nenhuma sala foi reservada parcialmente.",
            409,
        )
    added = wanted - (old_cells or set())
    if not added:
        return
    first = min(day for _, day in added)
    end = max(day for _, day in added) + timedelta(days=1)
    earlier_ids = [
        row["id"]
        for row in conn.execute(
            """SELECT DISTINCT b.id,b.queue_number FROM bookings b
                      JOIN allocations a ON a.booking_id=b.id
                      WHERE b.status='reserved' AND b.queue_number<%s AND b.id<>%s
                        AND a.start_date<%s AND a.end_exclusive>%s
                      ORDER BY b.queue_number""",
            (booking["queue_number"], booking["id"], end, first),
        )
    ]
    if not earlier_ids:
        return
    earlier_allocations = {booking_id: [] for booking_id in earlier_ids}
    for allocation in conn.execute(
        """SELECT booking_id,start_date,end_exclusive,resources FROM allocations
                                      WHERE booking_id=ANY(%s)""",
        (earlier_ids,),
    ):
        earlier_allocations[allocation["booking_id"]].append(allocation)
    earlier_cells = {
        booking_id: cells(items) for booking_id, items in earlier_allocations.items()
    }
    all_days = [day for group in earlier_cells.values() for _, day in group]
    occupied = set()
    if all_days:
        occupied = {
            (row["resource_id"], row["day"])
            for row in conn.execute(
                """SELECT resource_id,day FROM occupations
                         WHERE day BETWEEN %s AND %s AND booking_id<>%s""",
                (min(all_days), max(all_days), booking["id"]),
            )
        }
    for other_cells in earlier_cells.values():
        if other_cells & added and not other_cells & occupied:
            raise Problem(
                "Uma solicitação anterior e disponível tem prioridade sobre esse período. Consulte a fila.",
                409,
            )


def allocation_signature(allocations):
    return sorted(
        (
            a["configuration_id"],
            a["phase"],
            str(a["start_date"]),
            str(a["end_exclusive"]),
            tuple(sorted(a["resources"])),
        )
        for a in allocations
    )


def replace_allocations(conn, booking_id, allocations):
    conn.execute("DELETE FROM allocations WHERE booking_id=%s", (booking_id,))
    for a in allocations:
        conn.execute(
            "INSERT INTO allocations(booking_id,configuration_id,phase,start_date,end_exclusive,resources) VALUES (%s,%s,%s,%s,%s,%s)",
            (
                booking_id,
                a["configuration_id"],
                a["phase"],
                a["start_date"],
                a["end_exclusive"],
                json_value(a["resources"]),
            ),
        )


def save_booking(actor, data, booking_id=None, idempotency_key=None):
    if not isinstance(data, dict):
        raise Problem("Formulário inválido.")
    forbidden = {
        "team_id",
        "created_by",
        "updated_by",
        "queue_number",
        "created_at",
        "updated_at",
    } & data.keys()
    if forbidden:
        raise Problem("Equipe, autoria e prioridade são definidas pelo servidor.", 403)
    request_hash = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
    with write_transaction() as conn:
        if not booking_id:
            if (
                not isinstance(idempotency_key, str)
                or not 8 <= len(idempotency_key) <= 100
            ):
                raise Problem("A requisição precisa de uma chave de salvamento.")
            replay = conn.execute(
                "SELECT * FROM idempotency WHERE user_id=%s AND key=%s",
                (actor["id"], idempotency_key),
            ).fetchone()
            if replay:
                if replay["request_hash"] != request_hash:
                    raise Problem(
                        "A chave de salvamento foi reutilizada com outro conteúdo.", 409
                    )
                return replay["response"]
        before = get_booking(conn, booking_id) if booking_id else None
        if before:
            if not accessible(actor, before) or before["team_id"] != actor["team_id"]:
                raise Problem(
                    "Cada equipe altera apenas suas próprias solicitações.", 403
                )
            ensure_version(before, data)
            if before["status"] == "cancelled":
                raise Problem(
                    "Solicitação cancelada: crie uma nova para preservar o histórico.",
                    409,
                )
        status = data.get("status", "reserved")
        allowed = (
            {"reserved"}
            if not before or before["status"] == "reserved"
            else {"confirmed", "reserved"}
        )
        if actor["can_schedule"] and (not before or before["status"] == "reserved"):
            allowed.add("confirmed")
        if status not in allowed:
            raise Problem(
                "Mudança de situação não permitida. A confirmação depende do responsável pela fila.",
                409,
            )
        allocations = normalize_allocations(
            conn,
            actor,
            data.get("allocations"),
            status,
            allow_unvalidated_confirmation=status == "confirmed"
            and (actor["can_schedule"] or before and before["status"] == "confirmed"),
        )
        if status == "reserved" and (
            not before
            or allocation_signature(allocations)
            != allocation_signature(before["allocations"])
        ):
            if configuration_conflicts(
                conn, allocations, booking_id
            ) or occupation_conflicts(conn, cells(allocations), booking_id):
                raise Problem(
                    "Já existe uma reserva confirmada para este espaço e período.", 409
                )
        if (
            before
            and before["status"] == "confirmed"
            and status == "confirmed"
            and not actor["can_schedule"]
        ):
            if allocation_signature(allocations) != allocation_signature(
                before["allocations"]
            ):
                raise Problem(
                    "Peça ao responsável pela fila para alterar o espaço ou período confirmado.",
                    403,
                )
        title = required_text(data, "title", 180)
        responsible = required_text(data, "responsible", 120)
        notes = data.get("notes", "")
        if not isinstance(notes, str) or len(notes) > 4000:
            raise Problem("Observações devem ter até 4.000 caracteres.")
        old = cells(before["allocations"]) if before else set()
        if before:
            reset_queue = status == "reserved" and (
                before["status"] != "reserved"
                or allocation_signature(allocations)
                != allocation_signature(before["allocations"])
            )
            conn.execute(
                "UPDATE bookings SET title=%s,responsible=%s,notes=%s,status=%s,updated_by=%s,updated_at=now(),version=version+1 WHERE id=%s",
                (title, responsible, notes, status, actor["id"], booking_id),
            )
            if reset_queue:
                conn.execute(
                    "UPDATE bookings SET queue_number=DEFAULT WHERE id=%s",
                    (booking_id,),
                )
        else:
            booking_id = uid()
            conn.execute(
                "INSERT INTO bookings(id,team_id,title,responsible,notes,status,created_by,updated_by) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    booking_id,
                    actor["team_id"],
                    title,
                    responsible,
                    notes,
                    status,
                    actor["id"],
                    actor["id"],
                ),
            )
        replace_allocations(conn, booking_id, allocations)
        after = get_booking(conn, booking_id)
        wanted = cells(allocations)
        if status in ACTIVE:
            ensure_priority(conn, after, wanted, old, allocations)
        conn.execute("DELETE FROM occupations WHERE booking_id=%s", (booking_id,))
        if status in ACTIVE:
            for resource_id, occupied_day in sorted(wanted):
                conn.execute(
                    "INSERT INTO occupations VALUES (%s,%s,%s)",
                    (resource_id, occupied_day, booking_id),
                )
        audit(
            conn,
            actor,
            "booking",
            booking_id,
            "update" if before else "create",
            before,
            after,
        )
        response = serialize(after)
        if not before:
            conn.execute(
                "INSERT INTO idempotency VALUES (%s,%s,%s,%s)",
                (actor["id"], idempotency_key, request_hash, json_value(response)),
            )
        return response


def transition(actor, booking_id, data, action):
    with write_transaction() as conn:
        before = get_booking(conn, booking_id)
        if not accessible(actor, before):
            raise Problem("Solicitação fora do seu escopo.", 403)
        ensure_version(before, data)
        if action == "cancel":
            if before["team_id"] != actor["team_id"]:
                raise Problem(
                    "Cada equipe cancela apenas suas próprias solicitações.", 403
                )
            if before["status"] == "cancelled":
                raise Problem("Solicitação já cancelada.", 409)
            status = "cancelled"
            reason = required_text(data, "reason", 600)
        elif action == "confirm":
            if not actor["can_schedule"]:
                raise Problem(
                    "A confirmação é exclusiva do responsável pela fila.", 403
                )
            if before["status"] != "reserved":
                raise Problem("Esta solicitação não pode ser confirmada.", 409)
            raw = [
                dict(a, end_date=str(a["end_date"]), start_date=str(a["start_date"]))
                for a in before["allocations"]
            ]
            allocations = normalize_allocations(
                conn, actor, raw, "confirmed", allow_unvalidated_confirmation=True
            )
            wanted = cells(allocations)
            ensure_priority(conn, before, wanted, allocations=allocations)
            if allocation_signature(allocations) != allocation_signature(
                before["allocations"]
            ):
                replace_allocations(conn, booking_id, allocations)
            for resource_id, occupied_day in sorted(wanted):
                conn.execute(
                    "INSERT INTO occupations VALUES (%s,%s,%s)",
                    (resource_id, occupied_day, booking_id),
                )
            status = "confirmed"
            reason = "Reserva confirmada pelo responsável da fila para todo o conjunto."
        else:
            raise Problem("Ação inválida.")
        conn.execute(
            "UPDATE bookings SET status=%s,updated_by=%s,updated_at=now(),version=version+1 WHERE id=%s",
            (status, actor["id"], booking_id),
        )
        if status == "cancelled":
            conn.execute("DELETE FROM occupations WHERE booking_id=%s", (booking_id,))
        after = get_booking(conn, booking_id)
        audit(conn, actor, "booking", booking_id, action, before, after, reason)
        return serialize(after)


def filter_bookings(bookings, first, exclusive, resort="all", status="", search=""):
    """Apply display filters without changing the full booking used for occupancy."""

    def normalize(value):
        return "".join(
            char
            for char in unicodedata.normalize("NFD", value.lower())
            if unicodedata.category(char) != "Mn"
        )

    result = []
    for booking in bookings:
        visible_allocations = [
            a
            for a in booking["allocations"]
            if a["start_date"] < exclusive
            and a["end_exclusive"] > first
            and (resort == "all" or (a["resort_id"] or "unassigned") == resort)
        ]
        if not visible_allocations or (status and booking["status"] != status):
            continue
        haystack = " ".join(
            [booking["title"], booking["responsible"], booking["team_name"]]
            + [a["space_name"] for a in visible_allocations]
        )
        if search and normalize(search) not in normalize(haystack):
            continue
        result.append({**booking, "matched_allocations": visible_allocations})
    return result


def list_bookings(actor, start, end, resort="all", status="", search=""):
    first, exclusive = period(start, end)
    conn = get_db()
    configs = {c["id"]: c for c in all_catalog(conn)}
    resources = resources_map(conn)
    bookings = list(
        conn.execute(
            """SELECT b.*,t.name AS team_name,u.name AS creator_name
                                  FROM bookings b
                                  JOIN teams t ON t.id=b.team_id
                                  JOIN users u ON u.id=b.created_by
                                  WHERE EXISTS (
                                      SELECT 1 FROM allocations a
                                      WHERE a.booking_id=b.id
                                        AND a.start_date<%s AND a.end_exclusive>%s
                                  )
                                  ORDER BY b.queue_number""",
            (exclusive, first),
        )
    )
    if not bookings:
        return []
    by_id = {booking["id"]: booking for booking in bookings}
    for booking in bookings:
        booking["allocations"] = []
    for allocation in conn.execute(
        """SELECT a.*,c.name AS space_name,c.resort_id,c.location
                                      FROM allocations a
                                      JOIN configurations c ON c.id=a.configuration_id
                                      WHERE a.booking_id = ANY(%s)
                                      ORDER BY a.id""",
        (list(by_id),),
    ):
        allocation["end_date"] = allocation["end_exclusive"] - timedelta(days=1)
        by_id[allocation["booking_id"]]["allocations"].append(allocation)
    visible = [
        booking
        for booking in bookings
        if accessible(actor, booking, configs, resources)
    ]
    return filter_bookings(visible, first, exclusive, resort, status, search)
