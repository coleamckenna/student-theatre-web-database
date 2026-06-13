#!/usr/bin/env python3
"""Build catalog SQLite database from instance CSV files."""

from __future__ import annotations

import argparse
import csv
import os
import re
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

_PKG = Path(__file__).resolve().parent
sys.path.insert(0, str(_PKG))
from config import (  # noqa: E402
    catalog_csv_dir,
    institution,
    load_instance,
    production_typos,
    sqlite_path,
)
from dates import to_iso_date  # noqa: E402

ROOT = _PKG.parent
SCHEMA = _PKG / "schema.sql"


def normalize_production_id(value: str | None) -> str | None:
    if not value:
        return None
    slug = str(value).strip()
    return slug


def first_field(row: dict, *keys: str):
    for key in keys:
        if key in row and row[key] not in (None, ""):
            return row[key]
    return None


def to_int(value) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def clean(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def parse_venue_row(row: dict) -> dict | None:
    venue_id = clean(first_field(row, "Venue ID", "venue id", "id"))
    if not venue_id:
        return None
    venue_id = venue_id.lower()
    return {
        "id": venue_id,
        "name": clean(first_field(row, "Name", "name")) or venue_id,
        "campus": clean(first_field(row, "Campus", "campus")),
        "city": clean(first_field(row, "City", "city")),
        "state": clean(first_field(row, "State", "state")),
        "country": clean(first_field(row, "Country", "country")),
        "capacity": to_int(first_field(row, "capacity", "Capacity")),
        "notes": clean(first_field(row, "notes", "Notes")),
    }


def csv_rows(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = []
        for row in reader:
            if not any(clean(v) for v in row.values()):
                continue
            rows.append({k: (v if v != "" else None) for k, v in row.items()})
        return rows


def load_catalog_csv(
    catalog_dir: Path,
) -> tuple[list[dict], list[dict], list[dict], list[dict], list[dict]]:
    return (
        csv_rows(catalog_dir / "productions.csv"),
        csv_rows(catalog_dir / "materials.csv"),
        csv_rows(catalog_dir / "organisations.csv"),
        csv_rows(catalog_dir / "people.csv"),
        csv_rows(catalog_dir / "venues.csv"),
    )


def check_slug_collisions(
    productions: dict,
    people: dict,
    organisations: dict,
    venues: dict,
) -> list[str]:
    slug_tables: dict[str, list[str]] = defaultdict(list)
    for slug in productions:
        slug_tables[slug].append("productions")
    for slug in people:
        slug_tables[slug].append("people")
    for slug in organisations:
        slug_tables[slug].append("organisations")
    for slug in venues:
        slug_tables[slug].append("venues")
    return [
        f"Slug '{slug}' appears in multiple tables: {', '.join(tables)}"
        for slug, tables in sorted(slug_tables.items())
        if len(tables) > 1
    ]

def filter_crossover(
    allowed_left: set[str],
    allowed_right: set[str],
    *,
    links: set[tuple[str, str]] | None = None,
    credits: list[dict] | None = None,
) -> list[tuple[str, str]] | list[dict]:
    if credits is not None:
        return [
            credit
            for credit in credits
            if credit["production_id"] in allowed_left
            and credit["person_id"] in allowed_right
        ]
    if links is not None:
        return sorted(
            link
            for link in links
            if link[0] in allowed_left and link[1] in allowed_right
        )
    if links is None and credits is None:
        raise ValueError("filter_crossover requires links or credits")

def build_from_rows(
    prod_rows: list[dict],
    material_rows: list[dict],
    org_rows: list[dict],
    people_rows: list[dict],
    venue_rows: list[dict],
    db_path: Path,
) -> bool:
    warnings: list[str] = []

    productions: dict[str, dict] = {}
    production_orgs: set[tuple[str, str]] = set()
    production_venues: set[tuple[str, str]] = set()
    venue_ids_needed: set[str] = set()

    for row in prod_rows:
        prod_id = normalize_production_id(
            row.get("Production ID (use next LTST-YYYY-NNN for that year)")
            or row.get("Production ID")
        )
        if not prod_id:
            warnings.append(f"Skipping production row with no id: {row}")
            continue

        org_field = clean(row.get("organisation"))
        if org_field:
            for org_id in re.split(r"\s*;\s*", org_field):
                org_id = org_id.strip()
                if org_id:
                    production_orgs.add((prod_id, org_id))

        venue_id = clean(row.get("venue"))
        if venue_id:
            venue_id = venue_id.lower()
            production_venues.add((prod_id, venue_id))
            venue_ids_needed.add(venue_id)

        productions[prod_id] = {
            "id": prod_id,
            "title": clean(row.get("title")) or prod_id,
            "year": to_int(row.get("year")),
            "month": to_int(row.get("month")),
            "start_date": to_iso_date(row.get("start_date")),
            "end_date": to_iso_date(row.get("end_date")),
            "date_edited": to_iso_date(row.get("date_edited")),
            "source": clean(row.get("information source")),
            "notes": clean(row.get("Notes on production")),
            "confidence": clean(row.get("Confidence")),
        }

    organisations: dict[str, dict] = {}
    for row in org_rows:
        org_id = clean(row.get("organisation ID"))
        if not org_id:
            continue
        organisations[org_id] = {
            "id": org_id,
            "name": clean(row.get("name")) or org_id,
            "alias": clean(row.get("alias")),
        }

    venues: dict[str, dict] = {}
    for row in venue_rows:
        venue = parse_venue_row(row)
        if venue:
            venues[venue["id"]] = venue

    for venue_id in venue_ids_needed:
        if venue_id not in venues:
            warnings.append(f"Unknown venue '{venue_id}' (not in venues.csv)")

    people: dict[str, dict] = {}
    production_people: list[dict] = []

    for row in people_rows:
        person_id = clean(row.get("Person ID"))
        prod_id = normalize_production_id(row.get("Associated Production ID"))
        if not person_id or not prod_id:
            warnings.append(f"Skipping people row with missing ids: {row}")
            continue

        credited_as = clean(row.get("Credited as"))
        if person_id not in people:
            people[person_id] = {
                "id": person_id,
                "given_name": clean(row.get("First Name")),
                "family_name": clean(row.get("Last Name")),
                "first_credited_as": credited_as or person_id,
            }

        production_people.append(
            {
                "production_id": prod_id,
                "person_id": person_id,
                "role": clean(row.get("Role")),
                "character": clean(row.get("Character/Instrument")),
                "credited_as": credited_as,
                "notes": clean(row.get("notes about person")),
            }
        )

    materials: dict[str, dict] = {}
    material_files: list[dict] = []
    production_materials: set[tuple[str, str]] = set()
    file_sort: dict[str, int] = defaultdict(int)

    for row in material_rows:
        material_id = clean(row.get("Material ID"))
        prod_id = normalize_production_id(row.get("Related Production"))
        if not material_id or not prod_id:
            warnings.append(f"Skipping material row: {row}")
            continue

        if material_id not in materials:
            date_added = to_iso_date(
                first_field(row, "date_added", "Date Added")
            )
            materials[material_id] = {
                "id": material_id,
                "material_type": clean(row.get("Material Type")),
                "date_added": date_added,
                "copyright_status": clean(row.get("Copyright Status")),
                "source": clean(row.get("Source")),
            }
        production_materials.add((prod_id, material_id))

        sort_order = file_sort[material_id]
        file_sort[material_id] += 1
        media_url = clean(row.get("Media URL"))
        if not media_url:
            warnings.append(f"Material file missing URL: {material_id} row {sort_order}")
            continue

        material_files.append(
            {
                "material_id": material_id,
                "file_type": clean(row.get("File Type")),
                "media_url": media_url,
                "page_note": clean(row.get("Notes")),
                "sort_order": sort_order,
            }
        )

    production_ids = set(productions)
    org_ids = set(organisations)
    venue_ids_set = set(venues)

    slug_collisions = check_slug_collisions(productions, people, organisations, venues)
    if slug_collisions:
        print("\nFatal errors (slug collisions):", file=sys.stderr)
        for error in slug_collisions:
            print(f"  - {error}", file=sys.stderr)
        return False

    production_orgs = filter_crossover(production_ids, org_ids, links=production_orgs)
    production_venues = filter_crossover(
        production_ids, venue_ids_set, links=production_venues
    )
    production_materials = filter_crossover(
        production_ids, set(materials), links=production_materials
    )
    production_people = filter_crossover(
        production_ids, set(people), credits=production_people
    )

    if db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA.read_text())

    inst = institution()
    conn.execute(
        "INSERT INTO institutions (id, name) VALUES (?, ?)",
        (inst.get("id", "catalog"), inst.get("name", "Student Theatre Catalog")),
    )

    conn.executemany(
        """INSERT INTO productions
           (id, title, year, month, start_date, end_date, date_edited, source, notes, confidence)
           VALUES (:id, :title, :year, :month, :start_date, :end_date, :date_edited, :source, :notes, :confidence)""",
        productions.values(),
    )

    conn.executemany(
        "INSERT INTO organisations (id, name, alias) VALUES (:id, :name, :alias)",
        organisations.values(),
    )

    conn.executemany(
        """INSERT INTO venues (id, name, campus, city, state, country, capacity, notes)
           VALUES (:id, :name, :campus, :city, :state, :country, :capacity, :notes)""",
        venues.values(),
    )

    conn.executemany(
        "INSERT INTO people (id, given_name, family_name, first_credited_as) VALUES (:id, :given_name, :family_name, :first_credited_as)",
        people.values(),
    )

    conn.executemany(
        "INSERT INTO production_organisations (production_id, organisation_id) VALUES (?, ?)",
        production_orgs,
    )

    conn.executemany(
        "INSERT INTO production_venues (production_id, venue_id) VALUES (?, ?)",
        production_venues,
    )

    conn.executemany(
        """INSERT INTO production_people
           (production_id, person_id, role, character, credited_as, notes)
           VALUES (:production_id, :person_id, :role, :character, :credited_as, :notes)""",
        production_people,
    )

    conn.executemany(
        "INSERT INTO materials (id, material_type, date_added, copyright_status, source) VALUES (:id, :material_type, :date_added, :copyright_status, :source)",
        materials.values(),
    )

    conn.executemany(
        """INSERT INTO material_files (material_id, file_type, media_url, page_note, sort_order)
           VALUES (:material_id, :file_type, :media_url, :page_note, :sort_order)""",
        material_files,
    )

    conn.executemany(
        "INSERT INTO production_materials (production_id, material_id) VALUES (?, ?)",
        production_materials,
    )

    conn.commit()
    conn.close()

    print(f"\nBuilt {db_path}")
    print(f"  productions: {len(productions)}")
    print(f"  organisations: {len(organisations)}")
    print(f"  venues: {len(venues)}")
    print(f"  people: {len(people)}")
    print(f"  production_people: {len(production_people)}")
    print(f"  materials: {len(materials)}")
    print(f"  material_files: {len(material_files)}")

    if warnings:
        print(f"\nWarnings ({len(warnings)}):")
        for w in warnings:
            print(f"  - {w}")

    return True


def build_from_catalog(catalog_dir: Path, db_path: Path) -> bool:
    required = [
        catalog_dir / "productions.csv",
        catalog_dir / "organisations.csv",
        catalog_dir / "people.csv",
        catalog_dir / "materials.csv",
        catalog_dir / "venues.csv",
    ]
    missing = [path for path in required if not path.exists()]
    if missing:
        print("Error: missing catalog CSV files:", file=sys.stderr)
        for path in missing:
            print(f"  - {path}", file=sys.stderr)
        return False

    print(f"Loading catalog from {catalog_dir}")
    prod_rows, material_rows, org_rows, people_rows, venue_rows = load_catalog_csv(
        catalog_dir
    )
    return build_from_rows(
        prod_rows,
        material_rows,
        org_rows,
        people_rows,
        venue_rows,
        db_path,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Build catalog SQLite from instance CSV")
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to instance.yaml (or set CATALOG_INSTANCE)",
    )
    parser.add_argument(
        "--catalog",
        type=Path,
        default=None,
        help="Directory with productions.csv, organisations.csv, people.csv, materials.csv, venues.csv",
    )
    parser.add_argument("--db", type=Path, default=None)
    args = parser.parse_args()

    if args.config:
        os.environ["CATALOG_INSTANCE"] = str(args.config.resolve())
        load_instance.cache_clear()

    catalog_dir = args.catalog or catalog_csv_dir()
    db_path = args.db or sqlite_path(ROOT)
    ok = build_from_catalog(catalog_dir, db_path)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
