from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SearchMatch:
    hash: str
    path: str
    description: str


@dataclass(frozen=True)
class SearchResult:
    query: str
    root: str
    matches: list[SearchMatch]


class Searcher:
    def search(
        self,
        conn: sqlite3.Connection,
        *,
        input_dir: Path,
        query: str,
    ) -> SearchResult:
        root = str(input_dir.resolve())
        if not root.endswith("\\"):
            root_prefix = root + "\\"
        else:
            root_prefix = root

        terms = self._split_terms(query)
        if not terms:
            raise ValueError("Query must not be empty.")

        where_parts: list[str] = []
        params: list[str] = []
        for term in terms:
            where_parts.append("d.description LIKE ?")
            params.append(f"%{term}%")

        # Only keep images under input_dir (including subdirectories)
        where_sql = " OR ".join(where_parts)
        sql = (
            "SELECT f.hash AS hash, f.path AS path, d.description AS description "
            "FROM IMAGE_FILE f "
            "JOIN IMAGE_METADATA m ON m.hash = f.hash "
            "JOIN DESCRIPTION d ON d.id = m.description_fk "
            "WHERE f.path = ? OR f.path LIKE ? "
            f"AND ({where_sql}) "
            "ORDER BY f.path ASC"
        )

        rows = conn.execute(sql, [root, root_prefix + "%", *params]).fetchall()
        matches = [SearchMatch(hash=row["hash"], path=row["path"], description=row["description"]) for row in rows]
        return SearchResult(query=query, root=root, matches=matches)

    def _split_terms(self, query: str) -> list[str]:
        parts = [p.strip() for p in query.split()]
        parts = [p for p in parts if p]
        seen: set[str] = set()
        unique: list[str] = []
        for p in parts:
            key = p.lower()
            if key in seen:
                continue
            seen.add(key)
            unique.append(p)
        return unique
