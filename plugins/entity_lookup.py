import sqlite3
import sys
from pathlib import Path

from datasette import hookimpl

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from catalog.plugin_support import _add_catalog_context_path, catalog_id_for  # noqa: E402

_add_catalog_context_path()
from catalog_context import resolve_entity_context  # noqa: E402

STATIC_PAGES = {"about"}


@hookimpl
def extra_template_vars(template, view_name, request, datasette):
    if view_name != "page":
        return {}

    slug = request.path.strip("/")
    if not slug or slug in STATIC_PAGES or "/" in slug:
        return {}

    db_name = catalog_id_for(datasette)

    async def inner():
        db = datasette.get_database(db_name)
        conn = sqlite3.connect(db.path)
        conn.row_factory = sqlite3.Row
        try:
            return resolve_entity_context(conn, slug)
        finally:
            conn.close()

    return inner
