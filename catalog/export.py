#!/usr/bin/env python3
"""Export catalog SQLite database to instance CSV files."""

from __future__ import annotations

import argparse
import csv
import os
import sqlite3
import sys
from pathlib import Path

_PKG = Path(__file__).resolve().parent
sys.path.insert(0, str(_PKG))
from config import catalog_csv_dir, load_instance, sqlite_path  # noqa: E402

ROOT = _PKG.parent


def export_csv(db_path: Path, catalog_dir: Path) -> None:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    productions = conn.execute(
        "SELECT * FROM productions ORDER BY year, title"
    ).fetchall()
    organisations = conn.execute(
        "SELECT * FROM organisations ORDER BY name"
    ).fetchall()
    venues = conn.execute("SELECT * FROM venues ORDER BY name").fetchall()
    production_people = conn.execute(
        """
        SELECT pp.*, p.given_name, p.family_name
        FROM production_people pp
        JOIN people p ON p.id = pp.person_id
        ORDER BY pp.production_id, pp.credited_as, pp.role
        """
    ).fetchall()

    prod_orgs: dict[str, list[str]] = {}
    for row in conn.execute(
        "SELECT production_id, organisation_id FROM production_organisations ORDER BY production_id, organisation_id"
    ):
        prod_orgs.setdefault(row[0], []).append(row[1])

    prod_venues = {
        row[0]: row[1]
        for row in conn.execute(
            "SELECT production_id, venue_id FROM production_venues"
        )
    }

    materials = {
        row["id"]: row
        for row in conn.execute("SELECT * FROM materials ORDER BY id")
    }
    prod_materials: dict[str, list[str]] = {}
    for row in conn.execute(
        "SELECT production_id, material_id FROM production_materials ORDER BY production_id, material_id"
    ):
        prod_materials.setdefault(row[0], []).append(row[1])

    material_files = conn.execute(
        """
        SELECT material_id, file_type, media_url, page_note, sort_order
        FROM material_files
        ORDER BY material_id, sort_order
        """
    ).fetchall()
    conn.close()

    catalog_dir.mkdir(parents=True, exist_ok=True)

    with open(catalog_dir / "productions.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "Production ID",
                "title",
                "year",
                "month",
                "start_date",
                "end_date",
                "date_edited",
                "information source",
                "Notes on production",
                "Confidence",
                "organisation",
                "venue",
            ]
        )
        for row in productions:
            writer.writerow(
                [
                    row["id"],
                    row["title"],
                    row["year"],
                    row["month"],
                    row["start_date"],
                    row["end_date"],
                    row["date_edited"],
                    row["source"],
                    row["notes"],
                    row["confidence"],
                    "; ".join(prod_orgs.get(row["id"], [])),
                    prod_venues.get(row["id"], ""),
                ]
            )

    with open(catalog_dir / "organisations.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["organisation ID", "name", "alias"])
        for row in organisations:
            writer.writerow([row["id"], row["name"], row["alias"] or ""])

    with open(catalog_dir / "venues.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "Venue ID",
                "Name",
                "Campus",
                "City",
                "State",
                "Country",
                "latitude",
                "longitude",
                "capacity",
                "notes",
            ]
        )
        for row in venues:
            writer.writerow(
                [
                    row["id"],
                    row["name"],
                    row["campus"] or "",
                    row["city"] or "",
                    row["state"] or "",
                    row["country"] or "",
                    row["latitude"] if row["latitude"] is not None else "",
                    row["longitude"] if row["longitude"] is not None else "",
                    row["capacity"] if row["capacity"] is not None else "",
                    row["notes"] or "",
                ]
            )

    with open(catalog_dir / "people.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "Person ID",
                "Associated Production ID",
                "First Name",
                "Last Name",
                "Credited as",
                "Role",
                "Character/Instrument",
                "notes about person",
            ]
        )
        for row in production_people:
            writer.writerow(
                [
                    row["person_id"],
                    row["production_id"],
                    row["given_name"],
                    row["family_name"],
                    row["credited_as"],
                    row["role"],
                    row["character"] or "",
                    row["notes"] or "",
                ]
            )

    with open(catalog_dir / "materials.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "Material ID",
                "Related Production",
                "Material Type",
                "date_added",
                "Copyright Status",
                "Source",
                "Media URL",
                "Notes",
                "File Type",
            ]
        )
        files_by_material: dict[str, list] = {}
        for row in material_files:
            files_by_material.setdefault(row[0], []).append(row)

        for material_id, material in materials.items():
            files = files_by_material.get(material_id, [])
            linked_productions = [
                prod_id
                for prod_id, mats in prod_materials.items()
                if material_id in mats
            ]
            if not files:
                writer.writerow(
                    [
                        material_id,
                        linked_productions[0] if linked_productions else "",
                        material["material_type"],
                        material["date_added"] or "",
                        material["copyright_status"] or "",
                        material["source"] or "",
                        "",
                        "",
                        "",
                    ]
                )
                continue
            for prod_id in linked_productions:
                for file_row in files:
                    writer.writerow(
                        [
                            material_id,
                            prod_id,
                            material["material_type"],
                            material["date_added"] or "",
                            material["copyright_status"] or "",
                            material["source"] or "",
                            file_row[2],
                            file_row[3] or "",
                            file_row[1] or "",
                        ]
                    )

    print(f"Exported {db_path} -> {catalog_dir}")
    print(f"  productions: {len(productions)}")
    print(f"  organisations: {len(organisations)}")
    print(f"  venues: {len(venues)}")
    print(f"  people credits: {len(production_people)}")
    print(f"  materials: {len(materials)}")
    print(f"  material files: {len(material_files)}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export catalog SQLite to instance CSV files"
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to instance.yaml (or set CATALOG_INSTANCE)",
    )
    parser.add_argument("--db", type=Path, default=None)
    parser.add_argument(
        "--catalog",
        type=Path,
        default=None,
        help="Write CSV files to this directory",
    )
    args = parser.parse_args()

    if args.config:
        os.environ["CATALOG_INSTANCE"] = str(args.config.resolve())
        load_instance.cache_clear()

    db_path = args.db or sqlite_path(ROOT)
    catalog_dir = args.catalog or catalog_csv_dir()

    if not db_path.is_file():
        print(f"Error: database not found: {db_path}", file=sys.stderr)
        return 1

    export_csv(db_path, catalog_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
