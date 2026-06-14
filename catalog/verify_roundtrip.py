#!/usr/bin/env python3
"""Compare two catalog SQLite databases after export/build round-trip."""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

TABLES = [
    "institutions",
    "productions",
    "organisations",
    "venues",
    "people",
    "production_organisations",
    "production_venues",
    "production_people",
    "materials",
    "material_files",
    "production_materials",
]

ENTITY_TABLES = ("productions", "organisations", "venues", "people")

PRODUCTION_PEOPLE_COLUMNS = (
    "production_id",
    "person_id",
    "role",
    "character",
    "credited_as",
    "notes",
)

MATERIAL_FILE_COLUMNS = (
    "material_id",
    "file_type",
    "media_url",
    "page_note",
    "sort_order",
)


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def table_count(conn: sqlite3.Connection, table: str) -> int:
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def entity_ids(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[0] for row in conn.execute(f"SELECT id FROM {table}")}


def link_rows(conn: sqlite3.Connection, table: str, columns: tuple[str, ...]) -> set[tuple]:
    query = f"SELECT {', '.join(columns)} FROM {table} ORDER BY {', '.join(columns)}"
    rows = []
    for row in conn.execute(query):
        rows.append(tuple(normalize(value) for value in row))
    return set(rows)


def normalize(value) -> str | int | float | None:
    if value is None:
        return None
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def compare_counts(source: sqlite3.Connection, rebuilt: sqlite3.Connection) -> list[str]:
    errors: list[str] = []
    for table in TABLES:
        source_count = table_count(source, table)
        rebuilt_count = table_count(rebuilt, table)
        if source_count != rebuilt_count:
            errors.append(
                f"{table}: count {source_count} -> {rebuilt_count}"
            )
    return errors


def compare_entity_ids(source: sqlite3.Connection, rebuilt: sqlite3.Connection) -> list[str]:
    errors: list[str] = []
    for table in ENTITY_TABLES:
        source_ids = entity_ids(source, table)
        rebuilt_ids = entity_ids(rebuilt, table)
        if source_ids != rebuilt_ids:
            missing = sorted(source_ids - rebuilt_ids)
            extra = sorted(rebuilt_ids - source_ids)
            if missing:
                errors.append(f"{table}: missing ids {missing}")
            if extra:
                errors.append(f"{table}: extra ids {extra}")
    return errors


def compare_semantic_rows(
    source: sqlite3.Connection,
    rebuilt: sqlite3.Connection,
    table: str,
    columns: tuple[str, ...],
) -> list[str]:
    source_rows = link_rows(source, table, columns)
    rebuilt_rows = link_rows(rebuilt, table, columns)
    errors: list[str] = []
    if source_rows != rebuilt_rows:
        missing = sorted(source_rows - rebuilt_rows)
        extra = sorted(rebuilt_rows - source_rows)
        if missing:
            errors.append(f"{table}: missing rows ({len(missing)})")
        if extra:
            errors.append(f"{table}: extra rows ({len(extra)})")
    return errors


def verify(source_path: Path, rebuilt_path: Path) -> list[str]:
    if not source_path.is_file():
        return [f"source database not found: {source_path}"]
    if not rebuilt_path.is_file():
        return [f"rebuilt database not found: {rebuilt_path}"]

    source = connect(source_path)
    rebuilt = connect(rebuilt_path)
    try:
        errors: list[str] = []
        errors.extend(compare_counts(source, rebuilt))
        errors.extend(compare_entity_ids(source, rebuilt))

        for table, columns in (
            ("production_organisations", ("production_id", "organisation_id")),
            ("production_venues", ("production_id", "venue_id")),
            ("production_materials", ("production_id", "material_id")),
            ("production_people", PRODUCTION_PEOPLE_COLUMNS),
            ("material_files", MATERIAL_FILE_COLUMNS),
        ):
            errors.extend(compare_semantic_rows(source, rebuilt, table, columns))

        for table in ENTITY_TABLES:
            source_rows = {
                tuple(normalize(row[col]) for col in row.keys())
                for row in source.execute(f"SELECT * FROM {table}")
            }
            rebuilt_rows = {
                tuple(normalize(row[col]) for col in row.keys())
                for row in rebuilt.execute(f"SELECT * FROM {table}")
            }
            if source_rows != rebuilt_rows:
                errors.append(f"{table}: row content differs")

        source_institutions = link_rows(source, "institutions", ("id", "name"))
        rebuilt_institutions = link_rows(rebuilt, "institutions", ("id", "name"))
        if source_institutions != rebuilt_institutions:
            errors.append("institutions: row content differs")

        source_materials = link_rows(
            source,
            "materials",
            ("id", "material_type", "date_added", "copyright_status", "source"),
        )
        rebuilt_materials = link_rows(
            rebuilt,
            "materials",
            ("id", "material_type", "date_added", "copyright_status", "source"),
        )
        if source_materials != rebuilt_materials:
            errors.append("materials: row content differs")

        source_productions = link_rows(
            source,
            "productions",
            (
                "id",
                "title",
                "year",
                "month",
                "start_date",
                "end_date",
                "date_edited",
                "source",
                "notes",
                "confidence",
            ),
        )
        rebuilt_productions = link_rows(
            rebuilt,
            "productions",
            (
                "id",
                "title",
                "year",
                "month",
                "start_date",
                "end_date",
                "date_edited",
                "source",
                "notes",
                "confidence",
            ),
        )
        if source_productions != rebuilt_productions:
            errors.append("productions: row content differs")
    finally:
        source.close()
        rebuilt.close()

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify export/build round-trip between two SQLite databases"
    )
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--rebuilt", type=Path, required=True)
    args = parser.parse_args()

    errors = verify(args.source, args.rebuilt)
    if errors:
        print("Round-trip verification failed:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    print(f"Round-trip OK: {args.source} matches {args.rebuilt}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
