"""HTTP endpoints for the catalog and its audit trail."""
from flask import Blueprint, g, request

from .auth import login_required
from .catalog import (
    add_resource, all_catalog, classify, config_access, import_catalog,
    resources_map, validate_topology,
)
from .common import in_scope, require_capability, serialize
from .db import get_db

bp = Blueprint('api_catalog', __name__, url_prefix='/api')


@bp.get('/catalog')
@login_required
def catalog_get():
    conn = get_db()
    resources = resources_map(conn)
    configs = [config for config in all_catalog(conn) if config_access(g.user, config, resources)]
    return serialize({
        'configurations': configs,
        'resources': [resource for resource in resources.values()
                      if in_scope(g.user, resource['resort_id'])],
        'source_count': conn.execute('SELECT count(*) AS n FROM source_items').fetchone()['n'],
        'resorts': list(conn.execute('SELECT * FROM resorts ORDER BY id')),
    })


@bp.post('/catalog/classify')
@login_required
def catalog_classify():
    return classify(g.user, request.get_json())


@bp.post('/catalog/<config_id>/topology')
@login_required
def topology(config_id):
    return serialize(validate_topology(g.user, config_id, request.get_json()))


@bp.post('/resources')
@login_required
def resource_add():
    return add_resource(g.user, request.get_json()), 201


@bp.get('/catalog/sources')
@login_required
def sources():
    require_capability(g.user, 'can_catalog')
    return serialize({'items': list(get_db().execute('SELECT * FROM source_items ORDER BY code'))})


@bp.post('/catalog/import')
@login_required
def catalog_import():
    require_capability(g.user, 'can_catalog')
    data = request.get_json()
    return import_catalog(data.get('catalog'), g.user, preview=data.get('confirm') is not True)

@bp.get('/audit/catalog')
@login_required
def catalog_audit():
    require_capability(g.user, 'can_catalog')
    rows = get_db().execute(
        '''SELECT a.*,u.name AS actor_name FROM audit a
           LEFT JOIN users u ON u.id=a.actor_id
           WHERE entity_type IN ('configuration','resource','catalog')
           ORDER BY a.id DESC LIMIT 300'''
    )
    return serialize({'history': list(rows)})
