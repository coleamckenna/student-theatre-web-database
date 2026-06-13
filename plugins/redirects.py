import sys
from pathlib import Path

from datasette import hookimpl
from datasette.utils.asgi import Response

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from catalog.plugin_support import catalog_id_for  # noqa: E402


def redirect_to_root(request):
    entity_id = request.url_vars["id"]
    return Response.redirect(f"/{entity_id}", status=301)


@hookimpl
def register_routes(datasette):
    cid = catalog_id_for(datasette)
    tables = ("productions", "people", "organisations", "venues")
    return [
        (rf"^/{cid}/{table}/(?P<id>[^/]+)$", redirect_to_root) for table in tables
    ]

