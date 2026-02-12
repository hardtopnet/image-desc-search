from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

class DbError(Exception):
    pass

@dataclass(frozen=True)
class DbPaths:
    db_path: Path

def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    return conn

def migrate(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS DESCRIPTION (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            description TEXT NOT NULL,
            keywords_json TEXT NULL,
            created_at_utc TEXT NOT NULL
        );
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS IMAGE_METADATA (
            hash TEXT PRIMARY KEY,
            size_bytes INTEGER NOT NULL,
            res_w INTEGER NULL,
            res_h INTEGER NULL,
            thumbnail BLOB NULL,
            description_fk INTEGER NULL,
            FOREIGN KEY (description_fk) REFERENCES DESCRIPTION(id)
        );
        """
    )

    # Backward-compatible migration: add missing columns when upgrading.
    cols = {row[1] for row in conn.execute("PRAGMA table_info(IMAGE_METADATA);").fetchall()}
    if "thumbnail" not in cols:
        conn.execute("ALTER TABLE IMAGE_METADATA ADD COLUMN thumbnail BLOB NULL;")

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS IMAGE_FILE (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            path TEXT NOT NULL UNIQUE,
            hash TEXT NOT NULL,
            size_bytes INTEGER NOT NULL,
            created_at_utc TEXT NOT NULL,
            modified_at_utc TEXT NOT NULL,
                FOREIGN KEY (hash) REFERENCES IMAGE_METADATA(hash)
        );
        """
    )

    conn.execute("CREATE INDEX IF NOT EXISTS idx_image_file_hash ON IMAGE_FILE(hash);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_image_metadata_desc ON IMAGE_METADATA(description_fk);")
