#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DW="$ROOT/datasette-worker"
SRC="$DW/src"
PYTHON="${ROOT}/.venv/bin/python"

INSTANCE_CONFIG="${CATALOG_INSTANCE:-$ROOT/config/instance.example.yaml}"
export CATALOG_INSTANCE="$INSTANCE_CONFIG"
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"

if [[ ! -x "$PYTHON" ]]; then
  PYTHON="python3"
fi

SQLITE_PATH="$("$PYTHON" -c "import os; os.environ['CATALOG_INSTANCE']='$INSTANCE_CONFIG'; from catalog.config import sqlite_path; print(sqlite_path())")"
SQLITE_FILE="$(basename "$SQLITE_PATH")"
METADATA_PUBLIC="$("$PYTHON" -c "import os; os.environ['CATALOG_INSTANCE']='$INSTANCE_CONFIG'; from catalog.config import metadata_path; print(metadata_path(public=True))")"
CONTENT_PAGES="$("$PYTHON" -c "import os; os.environ['CATALOG_INSTANCE']='$INSTANCE_CONFIG'; from catalog.config import content_pages_dir; print(content_pages_dir())")"

echo "Building $SQLITE_FILE from catalog CSV..."
"$PYTHON" "$ROOT/catalog/build.py" --config "$INSTANCE_CONFIG"

echo "Bundling datasette-worker assets into src/..."
rm -rf "$SRC/templates" "$SRC/plugins" "$SRC/static" "$SRC/data"
mkdir -p "$SRC/data" "$SRC/catalog" "$SRC/plugins"

cp "$SQLITE_PATH" "$SRC/"
cp "$METADATA_PUBLIC" "$SRC/metadata.public.yaml"
cp -r "$ROOT/templates" "$SRC/"
rm -rf "$SRC/templates/static"
if [[ -d "$CONTENT_PAGES" ]]; then
  mkdir -p "$SRC/templates/pages"
  cp -r "$CONTENT_PAGES/." "$SRC/templates/pages/"
fi
cp -r "$ROOT/static" "$SRC/"
cp "$ROOT/catalog/catalog_context.py" "$SRC/data/"
cp "$ROOT/catalog/__init__.py" "$ROOT/catalog/plugin_support.py" "$SRC/catalog/"

for plugin in entity_lookup.py index_vars.py redirects.py template_functions.py menu_links.py; do
  cp "$ROOT/plugins/$plugin" "$SRC/plugins/"
done

echo "Bundled to $SRC"
echo "  $SQLITE_FILE, metadata.public.yaml, templates/, plugins/, static/, data/catalog_context.py"


