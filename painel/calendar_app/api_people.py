"""HTTP endpoints for account administration and access history."""
from flask import Blueprint, g, request

from .auth import login_required
from .people import access_history, create_person, delete_person, list_people, update_access

bp = Blueprint('api_people', __name__, url_prefix='/api')


@bp.get('/users')
@login_required
def users_get():
    return {'users': list_people(g.user)}


@bp.post('/users')
@login_required
def users_add():
    return create_person(g.user, request.get_json()), 201


@bp.put('/users/<user_id>')
@login_required
def users_edit(user_id):
    return update_access(g.user, user_id, request.get_json())


@bp.delete('/users/<user_id>')
@login_required
def users_delete(user_id):
    return delete_person(g.user, user_id, request.get_json())


@bp.get('/audit/auth')
@login_required
def auth_audit():
    return access_history(g.user)
