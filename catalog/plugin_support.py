"""Shared helpers for Datasette plugins (local dev and Worker bundle)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _add_catalog_context_path() -> None:
    for sub in ("data", "catalog"):
        candidate = ROOT / sub
        if (candidate / "catalog_context.py").is_file():
            path = str(candidate)
            if path not in sys.path:
                sys.path.insert(0, path)
            return


def catalog_id_for(datasette) -> str:
    meta = datasette.metadata() or {}
    block = meta.get("catalog")
    if isinstance(block, dict) and block.get("id"):
        return str(block["id"])
    if isinstance(block, str):
        return block
    config_py = ROOT / "catalog" / "config.py"
    if config_py.is_file():
        sys.path.insert(0, str(ROOT / "catalog"))
        from config import catalog_id  # noqa: WPS433

        return catalog_id()
    return "catalog"

