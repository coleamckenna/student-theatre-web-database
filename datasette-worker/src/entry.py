"""Read-only Datasette ASGI app for Cloudflare Workers."""

from __future__ import annotations

from pathlib import Path

import yaml
from datasette.app import Datasette
from workers import WorkerEntrypoint

import asgi

ROOT = Path(__file__).resolve().parent
METADATA_PATH = ROOT / "metadata.public.yaml"


def _sqlite_path() -> Path:
    matches = sorted(ROOT.glob("*.sqlite"))
    if not matches:
        raise FileNotFoundError(f"No SQLite database bundled in {ROOT}")
    return matches[0]


def _load_metadata() -> dict:
    return yaml.safe_load(METADATA_PATH.read_text(encoding="utf-8"))


def _create_datasette() -> Datasette:
    # Workers forbid os.urandom at import time; Datasette defaults to secrets.token_hex().
    return Datasette(
        immutables=[str(_sqlite_path())],
        metadata=_load_metadata(),
        template_dir=str(ROOT / "templates"),
        plugins_dir=str(ROOT / "plugins"),
        static_mounts=[("static", str(ROOT / "static"))],
        secret="catalog-readonly",
        settings={"num_sql_threads": 0},
        cors=True,
        cache_headers=True,
    )


_ds: Datasette | None = None
_app = None


def _get_app():
    global _ds, _app
    if _app is None:
        _ds = _create_datasette()
        _app = _ds.app()
    return _app


class Default(WorkerEntrypoint):
    async def fetch(self, request):
        return await asgi.fetch(_get_app(), request, self.env)
