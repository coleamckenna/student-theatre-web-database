"""Load instance configuration (catalog id, paths, institution stubs)."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INSTANCE = ROOT / "config" / "instance.example.yaml"


def instance_path() -> Path:
    raw = os.environ.get("CATALOG_INSTANCE", "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return DEFAULT_INSTANCE


def instance_root() -> Path:
    return instance_path().parent.parent


@lru_cache(maxsize=1)
def load_instance() -> dict[str, Any]:
    path = instance_path()
    if not path.is_file():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def catalog_id() -> str:
    return str(load_instance().get("catalog", {}).get("id", "catalog"))


def sqlite_filename() -> str:
    return str(load_instance().get("catalog", {}).get("sqlite_file", "catalog.sqlite"))


def sqlite_path(root: Path | None = None) -> Path:
    if instance_path().is_file():
        return instance_root() / sqlite_filename()
    return (root or ROOT) / sqlite_filename()


def catalog_csv_dir() -> Path:
    inst = load_instance()
    rel = inst.get("paths", {}).get("catalog_csv")
    if rel:
        path = Path(rel)
        if path.is_absolute():
            return path
        return (instance_root() / rel).resolve()
    return instance_root() / "catalog"


def metadata_path(public: bool = False) -> Path:
    inst = load_instance()
    key = "metadata_public" if public else "metadata"
    rel = inst.get("paths", {}).get(key)
    if rel:
        path = Path(rel)
        if path.is_absolute():
            return path
        return (instance_root() / rel).resolve()
    config_dir = instance_path().parent
    name = "metadata.public.yaml" if public else "metadata.yaml"
    candidate = config_dir / name
    if candidate.is_file():
        return candidate
    return ROOT / name


def content_pages_dir() -> Path:
    inst = load_instance()
    rel = inst.get("paths", {}).get("content_pages")
    if rel:
        path = Path(rel)
        if path.is_absolute():
            return path
        return (instance_root() / rel).resolve()
    return instance_root() / "content" / "pages"


def institution() -> dict[str, Any]:
    return dict(load_instance().get("institution", {}))


def worker_config() -> dict[str, Any]:
    return dict(load_instance().get("workers", {}))


def theme_config() -> dict[str, Any]:
    return dict(load_instance().get("theme", {}))


def css_filename() -> str:
    return str(theme_config().get("css_file", "catalog.css"))
