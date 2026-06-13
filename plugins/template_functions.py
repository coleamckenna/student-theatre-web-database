import os
import sys
from pathlib import Path

from datasette import hookimpl

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from catalog.plugin_support import catalog_id_for  # noqa: E402


@hookimpl
def extra_template_vars(datasette):
    meta = datasette.metadata() or {}
    cid = catalog_id_for(datasette)
    catalog_block = meta.get("catalog") if isinstance(meta.get("catalog"), dict) else {}
    sqlite_name = catalog_block.get("sqlite_file", f"{cid}.sqlite")


    return {
        "metadata": meta,
        "site_title": meta.get("title", "Student Theatre Catalog"),
        "catalog_id": cid,
        "sqlite_filename": sqlite_name
    }

