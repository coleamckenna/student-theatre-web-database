import sys
from pathlib import Path

from datasette import hookimpl

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from catalog.plugin_support import catalog_id_for  # noqa: E402


@hookimpl
def menu_links(datasette, actor, request):
    async def inner():
        cid = catalog_id_for(datasette)
        links = [
            {"href": datasette.urls.path("/"), "label": "Home"},
            {"href": datasette.urls.path(f"/{cid}/productions"), "label": "Browse"},
            {"href": datasette.urls.path("/about"), "label": "About"},
            {
                "href": datasette.urls.path(f"/{cid}/{cid}.db"),
                "label": "Download data",
            },
        ]
        return links

    return inner
