"""HTTP endpoints for requests, availability, the calendar and CSV."""
import csv
import io

from flask import Blueprint, Response, g, request

from .auth import login_required
from .bookings import (
    LABELS, accessible, get_booking, list_bookings, save_booking, transition,
)
from .calendar_queries import availability_snapshot, calendar_snapshot
from .common import Problem, serialize
from .db import get_db

bp = Blueprint('api_schedule', __name__, url_prefix='/api')


def query():
    resort = request.args.get('resort', 'all')
    if resort not in ('all', 'cs', 'rq', 'unassigned'):
        raise Problem('Filtro de empreendimento inválido.')
    status = request.args.get('status', '')
    if status and status not in LABELS:
        raise Problem('Situação inválida.')
    return {
        'start': request.args.get('from', '2026-01-01'),
        'end': request.args.get('to', '2028-12-31'),
        'resort': resort,
        'status': status,
        'search': request.args.get('search', '')[:200],
    }


@bp.get('/bookings')
@login_required
def booking_list():
    return serialize({'bookings': list_bookings(g.user, **query())})


@bp.get('/bookings/<booking_id>')
@login_required
def booking_get(booking_id):
    booking = get_booking(get_db(), booking_id)
    if not accessible(g.user, booking):
        raise Problem('Solicitação fora do seu escopo.', 403)
    history = list(get_db().execute(
        '''SELECT a.*,u.name AS actor_name FROM audit a
           LEFT JOIN users u ON u.id=a.actor_id
           WHERE entity_type='booking' AND entity_id=%s ORDER BY a.id DESC''',
        (booking_id,),
    ))
    return serialize({'booking': booking, 'history': history})


@bp.post('/bookings')
@login_required
def booking_create():
    booking = save_booking(
        g.user, request.get_json(),
        idempotency_key=request.headers.get('Idempotency-Key'),
    )
    return booking, 201


@bp.put('/bookings/<booking_id>')
@login_required
def booking_update(booking_id):
    return save_booking(g.user, request.get_json(), booking_id)


@bp.post('/bookings/<booking_id>/confirm')
@login_required
def booking_confirm(booking_id):
    return transition(g.user, booking_id, request.get_json(), 'confirm')


@bp.post('/bookings/<booking_id>/cancel')
@login_required
def booking_cancel(booking_id):
    return transition(g.user, booking_id, request.get_json(), 'cancel')


@bp.get('/availability')
@login_required
def availability():
    return availability_snapshot(g.user, query())


@bp.get('/calendar')
@login_required
def calendar():
    return calendar_snapshot(g.user, query())


def safe_cell(value):
    text = str(value or '')
    if text.lstrip().startswith(('=', '+', '-', '@')):
        text = "'" + text
    return text


@bp.get('/reports.csv')
@login_required
def report_csv():
    output = io.StringIO()
    writer = csv.writer(output, delimiter=';', lineterminator='\r\n', quoting=csv.QUOTE_ALL)
    writer.writerow(['Solicitação','Evento','Empreendimento','Espaço','Fase','Início','Último dia','Situação','Equipe','Responsável'])
    resort_names = {'cs': 'Costa do Sauípe', 'rq': 'Rio Quente', None: 'Empreendimento a identificar'}
    phase_names = {'setup': 'Montagem', 'event': 'Evento', 'teardown': 'Desmontagem'}
    for booking in list_bookings(g.user, **query()):
        for allocation in booking['matched_allocations']:
            row = [
                booking['id'], booking['title'], resort_names[allocation['resort_id']],
                allocation['space_name'], phase_names[allocation['phase']],
                str(allocation['start_date']), str(allocation['end_date']),
                LABELS[booking['status']], booking['team_name'], booking['responsible'],
            ]
            writer.writerow([safe_cell(v) for v in row])
    return Response(
        '\ufeff' + output.getvalue(), content_type='text/csv; charset=utf-8',
        headers={'Content-Disposition': 'attachment; filename="calendario-salas.csv"'},
    )
