PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS institutions (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS productions (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    year INTEGER,
    month INTEGER,
    start_date TEXT,
    end_date TEXT,
    date_edited TEXT,
    source TEXT,
    notes TEXT,
    confidence TEXT
);

CREATE TABLE IF NOT EXISTS organisations (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    alias TEXT
);

CREATE TABLE IF NOT EXISTS venues (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    campus TEXT,
    city TEXT,
    state TEXT,
    country TEXT,
    latitude REAL,
    longitude REAL,
    capacity INTEGER,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS people (
    id TEXT PRIMARY KEY,
    given_name TEXT,
    family_name TEXT,
    first_credited_as TEXT
);

CREATE TABLE IF NOT EXISTS production_organisations (
    production_id TEXT NOT NULL REFERENCES productions(id),
    organisation_id TEXT NOT NULL REFERENCES organisations(id),
    PRIMARY KEY (production_id, organisation_id)
);

CREATE TABLE IF NOT EXISTS production_venues (
    production_id TEXT NOT NULL REFERENCES productions(id),
    venue_id TEXT NOT NULL REFERENCES venues(id),
    PRIMARY KEY (production_id, venue_id)
);

CREATE TABLE IF NOT EXISTS production_people (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    production_id TEXT NOT NULL REFERENCES productions(id),
    person_id TEXT NOT NULL REFERENCES people(id),
    role TEXT,
    character TEXT,
    credited_as TEXT,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS materials (
    id TEXT PRIMARY KEY,
    material_type TEXT,
    date_added TEXT,
    copyright_status TEXT,
    source TEXT
);

CREATE TABLE IF NOT EXISTS material_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    material_id TEXT NOT NULL REFERENCES materials(id),
    file_type TEXT,
    media_url TEXT NOT NULL,
    page_note TEXT,
    sort_order INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS production_materials (
    production_id TEXT NOT NULL REFERENCES productions(id),
    material_id TEXT NOT NULL REFERENCES materials(id),
    PRIMARY KEY (production_id, material_id)
);
