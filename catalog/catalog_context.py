"""Shared catalog context builders for Datasette plugins and static export."""

from __future__ import annotations

import sqlite3
from collections import defaultdict

ENTITY_TABLES = (
    ("production", "productions"),
    ("person", "people"),
    ("organisation", "organisations"),
    ("venue", "venues"),
)


def row_to_dict(row) -> dict:
    return {k: row[k] for k in row.keys()}


def merge_cast(credits: list[dict]) -> list[dict]:
    by_person: dict[str, dict] = {}
    for row in credits:
        person_id = row["person_id"]
        if person_id not in by_person:
            by_person[person_id] = {
                "person_id": person_id,
                "display_name": row["display_name"] or person_id,
                "roles": [],
            }
        role = row.get("role")
        if role and role not in by_person[person_id]["roles"]:
            by_person[person_id]["roles"].append(role)

    merged = [
        {
            "person_id": entry["person_id"],
            "display_name": entry["display_name"],
            "roles": "; ".join(entry["roles"]),
        }
        for entry in by_person.values()
    ]
    merged.sort(key=lambda entry: entry["display_name"].lower())
    return merged


def production_context(conn: sqlite3.Connection, slug: str) -> dict:
    rows = conn.execute("SELECT * FROM productions WHERE id = ?", (slug,)).fetchall()
    context = {
        "entity_type": "production",
        "entity_id": slug,
        "not_found": False,
        "slug_collision": False,
        "entity": row_to_dict(rows[0]),
    }
    context["cast"] = merge_cast(
        [
            row_to_dict(r)
            for r in conn.execute(
                """
                SELECT
                    pp.person_id,
                    pp.role,
                    COALESCE(p.first_credited_as, pp.credited_as, pp.person_id)
                        AS display_name
                FROM production_people pp
                LEFT JOIN people p ON p.id = pp.person_id
                WHERE pp.production_id = ?
                ORDER BY display_name, pp.role
                """,
                (slug,),
            )
        ]
    )
    context["organisations"] = [
        row_to_dict(r)
        for r in conn.execute(
            """
            SELECT o.id, o.name
            FROM production_organisations po
            JOIN organisations o ON o.id = po.organisation_id
            WHERE po.production_id = ?
            ORDER BY o.name
            """,
            (slug,),
        )
    ]
    context["venues"] = [
        row_to_dict(r)
        for r in conn.execute(
            """
            SELECT v.id, v.name
            FROM production_venues pv
            JOIN venues v ON v.id = pv.venue_id
            WHERE pv.production_id = ?
            ORDER BY v.name
            """,
            (slug,),
        )
    ]
    context["materials"] = [
        row_to_dict(r)
        for r in conn.execute(
            """
            SELECT m.id, m.material_type, m.source
            FROM production_materials pm
            JOIN materials m ON m.id = pm.material_id
            WHERE pm.production_id = ?
            ORDER BY m.id
            """,
            (slug,),
        )
    ]
    files_by_material = {material["id"]: [] for material in context["materials"]}
    if files_by_material:
        for row in conn.execute(
            """
            SELECT mf.material_id, mf.media_url, mf.page_note, mf.file_type
            FROM production_materials pm
            JOIN material_files mf ON mf.material_id = pm.material_id
            WHERE pm.production_id = ?
            ORDER BY mf.material_id, mf.sort_order
            """,
            (slug,),
        ):
            file_row = row_to_dict(row)
            material_id = file_row.pop("material_id")
            files_by_material[material_id].append(file_row)
    context["files_by_material"] = files_by_material
    return context


def person_context(conn: sqlite3.Connection, slug: str, entity: dict) -> dict:
    return {
        "entity_type": "person",
        "entity": entity,
        "entity_id": slug,
        "not_found": False,
        "slug_collision": False,
        "credits": [
            row_to_dict(r)
            for r in conn.execute(
                """
                SELECT pp.production_id, pp.role, pp.credited_as,
                       p.title, p.year
                FROM production_people pp
                JOIN productions p ON p.id = pp.production_id
                WHERE pp.person_id = ?
                ORDER BY p.year, p.title
                """,
                (slug,),
            )
        ],
    }


def organisation_context(conn: sqlite3.Connection, slug: str, entity: dict) -> dict:
    return {
        "entity_type": "organisation",
        "entity": entity,
        "entity_id": slug,
        "not_found": False,
        "slug_collision": False,
        "productions": [
            row_to_dict(r)
            for r in conn.execute(
                """
                SELECT p.id, p.title, p.year
                FROM production_organisations po
                JOIN productions p ON p.id = po.production_id
                WHERE po.organisation_id = ?
                ORDER BY p.year, p.title
                """,
                (slug,),
            )
        ],
    }


def venue_context(conn: sqlite3.Connection, slug: str, entity: dict) -> dict:
    return {
        "entity_type": "venue",
        "entity": entity,
        "entity_id": slug,
        "not_found": False,
        "slug_collision": False,
        "productions": [
            row_to_dict(r)
            for r in conn.execute(
                """
                SELECT p.id, p.title, p.year
                FROM production_venues pv
                JOIN productions p ON p.id = pv.production_id
                WHERE pv.venue_id = ?
                ORDER BY p.year, p.title
                """,
                (slug,),
            )
        ],
    }


ENTITY_CONTEXT_BUILDERS = {
    "production": lambda conn, slug, entity: production_context(conn, slug),
    "person": person_context,
    "organisation": organisation_context,
    "venue": venue_context,
}


def resolve_entity_context(conn: sqlite3.Connection, slug: str) -> dict:
    matches = []
    for entity_type, table in ENTITY_TABLES:
        rows = conn.execute(f"SELECT * FROM {table} WHERE id = ?", (slug,)).fetchall()
        if rows:
            matches.append((entity_type, row_to_dict(rows[0])))

    if len(matches) > 1:
        return {
            "not_found": False,
            "slug_collision": True,
            "entity_id": slug,
            "collision_types": [entity_type for entity_type, _ in matches],
        }

    if len(matches) == 1:
        entity_type, entity = matches[0]
        builder = ENTITY_CONTEXT_BUILDERS[entity_type]
        return builder(conn, slug, entity)

    return {"not_found": True, "entity_id": slug, "slug_collision": False}


def homepage_context(conn: sqlite3.Connection) -> dict:
    productions = conn.execute(
        "SELECT id, title, year FROM productions ORDER BY year, title"
    ).fetchall()
    stats_row = conn.execute(
        """
        SELECT
            (SELECT COUNT(*) FROM productions) AS production_count,
            (SELECT COUNT(*) FROM people) AS people_count,
            (SELECT COUNT(*) FROM materials) AS material_count,
            (SELECT COUNT(*) FROM material_files) AS file_count
        """
    ).fetchone()
    return {
        "homepage_productions": [row_to_dict(r) for r in productions],
        "stats": row_to_dict(stats_row),
    }


def all_entity_slugs(conn: sqlite3.Connection) -> list[str]:
    slugs: list[str] = []
    for _entity_type, table in ENTITY_TABLES:
        for row in conn.execute(f"SELECT id FROM {table} ORDER BY id"):
            slugs.append(row[0])
    return slugs


def slug_collision_map(conn: sqlite3.Connection) -> dict[str, list[str]]:
    slug_tables: dict[str, list[str]] = defaultdict(list)
    for entity_type, table in ENTITY_TABLES:
        for row in conn.execute(f"SELECT id FROM {table}"):
            slug_tables[row[0]].append(entity_type)
    return {
        slug: types for slug, types in slug_tables.items() if len(types) > 1
    }

