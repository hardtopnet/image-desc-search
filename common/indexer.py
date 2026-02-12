from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from dataclasses import dataclass
import base64
from ollama import GenerateResponse

from common import constants
from common.logging import Logging
from common.ollama_handler import OllamaHandler
from .core_types import OverwriteMode
from .db import migrate
from .image_meta import FileMetadata, ImageMetadata

@dataclass(frozen=True)
class IndexWarning:
    path: str
    message: str

@dataclass(frozen=True)
class IndexError:
    path: str
    message: str

@dataclass(frozen=True)
class IndexResult:
    indexed: int
    skipped: int
    warnings: list[IndexWarning]
    errors: list[IndexError]

class Indexer():
    def __init__(self, ollama_handler: OllamaHandler | None = None):
        self.client = ollama_handler.client if ollama_handler else None

    def generate_description(
        self,
        *,
        image_path: Path,
        model: str,
        prompt: str = constants.DEFAULT_PROMPT,
    ) -> str:
        assert self.client is not None, "Ollama client is not initialized."

        image_b64 = self._image_file_to_base64(image_path)
        resp = self.client.generate(
            model=model,
            prompt=prompt or "",
            images=[image_b64],
            keep_alive=0,
        )
        
        text = resp.response if isinstance(resp, GenerateResponse) else None
        if not isinstance(text, str) or not text.strip():
            raise RuntimeError("Invalid response from Ollama generate.")
        return text.strip()
    
    def index_paths(
        self,
        conn: sqlite3.Connection,
        paths: list[Path],
        *,
        overwrite: OverwriteMode,
        model: str,
        thumbnails_only: bool = False,
        logger: IndexLogger | None = None,
    ) -> IndexResult:
        indexed = 0
        skipped = 0
        warnings: list[IndexWarning] = []
        errors: list[IndexError] = []

        for path in paths:
            try:
                conn.execute("BEGIN")
                changed, ws = self._index_one(conn, path, overwrite=overwrite, model=model, update_thumbnails=thumbnails_only, logger=logger)
                conn.commit()

                warnings.extend(ws)
                if changed:
                    indexed += 1
                else:
                    skipped += 1
            except Exception as ex:
                try:
                    conn.rollback()
                except Exception:
                    pass
                errors.append(IndexError(path=str(path), message=str(ex)))

        result = IndexResult(indexed=indexed, skipped=skipped, warnings=warnings, errors=errors)
        if logger is not None:
            logger.on_summary(result)
        return result

    def _index_one(
        self,
        conn: sqlite3.Connection,
        image_path: Path,
        *,
        overwrite: OverwriteMode,
        model: str,
        update_thumbnails: bool = False,
        logger: IndexLogger | None = None,
    ) -> tuple[bool, list[IndexWarning]]:
        migrate(conn)

        fm, im = ImageMetadata.build_image_metadata(image_path)

        created, existing_desc_fk, addedThumbnail = self._ensure_image_metadata(conn, im, update_thumbnails)
        if update_thumbnails and addedThumbnail and logger is not None:
            logger.on_thumbnail_added(IndexLogEvent(path=str(image_path), description=image_path.name))

        file_changed, warnings = self._upsert_file_row(conn, fm, im)

        if not update_thumbnails and self._should_generate_description(overwrite, existing_desc_fk):
            description = self.generate_description(image_path=image_path, model=model)
            desc_id = self._insert_description(conn, description=description, keywords_json=None)
            self._set_image_description_fk(conn, image_hash=im.sha256, description_id=desc_id)
            if logger is not None:
                logger.on_description(IndexLogEvent(path=str(image_path), description=description))

        return created or file_changed, warnings

    def _ensure_image_metadata(self, conn: sqlite3.Connection, im: ImageMetadata, update_thumbnails: bool) -> tuple[bool, int | None, bool]:
        """
        Returns (metadata_created, existing_description_fk, thumbnail_added)
        """
        row = conn.execute(
            "SELECT description_fk, thumbnail FROM IMAGE_METADATA WHERE hash = ?",
            (im.sha256,),
        ).fetchone()

        if row is None and not update_thumbnails:
            conn.execute(
                "INSERT INTO IMAGE_METADATA(hash, size_bytes, res_w, res_h, thumbnail, description_fk) VALUES(?, ?, ?, ?, ?, NULL)",
                (im.sha256, im.size_bytes, im.res_w, im.res_h, im.thumbnail),
            )
            return True, None, True

        addedThumbnail = False
        if row["thumbnail"] is None and im.thumbnail is not None:
            conn.execute(
                "UPDATE IMAGE_METADATA SET thumbnail = ? WHERE hash = ?",
                (im.thumbnail, im.sha256),
            )
            addedThumbnail = True

        return False, row["description_fk"], addedThumbnail

    def _get_file_row(self, conn: sqlite3.Connection, path: str) -> sqlite3.Row | None:
        return conn.execute(
            "SELECT id, path, hash, size_bytes, created_at_utc, modified_at_utc FROM IMAGE_FILE WHERE path = ?",
            (path,),
        ).fetchone()

    def _upsert_file_row(self, conn: sqlite3.Connection, fm: FileMetadata, im: ImageMetadata) -> tuple[bool, list[IndexWarning]]:
        warnings: list[IndexWarning] = []
        existing = self._get_file_row(conn, str(fm.path))

        if existing is None:
            conn.execute(
                "INSERT INTO IMAGE_FILE(path, hash, size_bytes, created_at_utc, modified_at_utc) VALUES(?, ?, ?, ?, ?)",
                (str(fm.path), im.sha256, fm.size_bytes, fm.created_at_utc, fm.modified_at_utc),
            )
            return True, warnings

        if existing["hash"] != im.sha256:
            conn.execute(
                "UPDATE IMAGE_FILE SET hash = ?, size_bytes = ?, created_at_utc = ?, modified_at_utc = ? WHERE id = ?",
                (im.sha256, fm.size_bytes, fm.created_at_utc, fm.modified_at_utc, existing["id"]),
            )
            return True, warnings

        if existing["created_at_utc"] != fm.created_at_utc or existing["modified_at_utc"] != fm.modified_at_utc:
            conn.execute(
                "UPDATE IMAGE_FILE SET size_bytes = ?, created_at_utc = ?, modified_at_utc = ? WHERE id = ?",
                (fm.size_bytes, fm.created_at_utc, fm.modified_at_utc, existing["id"]),
            )
            warnings.append(IndexWarning(path=str(fm.path), message="File timestamps changed without content change."))

        return False, warnings

    def _should_generate_description(self, overwrite: OverwriteMode, existing_fk: int | None) -> bool:
        if existing_fk is None:
            return True
        if overwrite == "always":
            return True
        if overwrite == "never":
            return False
        if overwrite == "older":
            return True # placeholder until we store timestamps on DESCRIPTION
        return False

    def _image_file_to_base64(self, path: Path) -> str:
        return base64.b64encode(path.read_bytes()).decode("ascii")

    def _utc_now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def _insert_description(self, conn: sqlite3.Connection, *, description: str, keywords_json: str | None) -> int:
        cur = conn.execute(
            "INSERT INTO DESCRIPTION(description, keywords_json, created_at_utc) VALUES(?, ?, ?)",
            (description, keywords_json, self._utc_now_iso()),
        )
        if cur.lastrowid is None:
            raise RuntimeError("Failed to retrieve inserted DESCRIPTION id.")
        return int(cur.lastrowid)

    def _set_image_description_fk(self, conn: sqlite3.Connection, *, image_hash: str, description_id: int) -> None:
        conn.execute(
            "UPDATE IMAGE_METADATA SET description_fk = ? WHERE hash = ?",
            (description_id, image_hash),
        )


@dataclass(frozen=True)
class IndexLogEvent:
    path: str
    description: str

class IndexLogger:
    _logging: Logging

    def __init__(self, logging: Logging):
        self._logging = logging

    def on_description(self, event: IndexLogEvent) -> None:
        return

    def on_summary(self, result: IndexResult) -> None:
        return
    
    def on_thumbnail_added(self, event: IndexLogEvent) -> None:
        return

class ConsoleIndexLogger(IndexLogger):
    def __init__(self, logging: Logging):
        super().__init__(logging)
    
    def on_description(self, event: IndexLogEvent) -> None:
        self._logging.out(event.path)
        self._logging.out(event.description)
        self._logging.out("")

    def on_summary(self, result: IndexResult) -> None:
        self._logging.out(f"Indexed: {result.indexed}, skipped: {result.skipped}, warnings: {len(result.warnings)}, errors: {len(result.errors)}")

    def on_thumbnail_added(self, event: IndexLogEvent) -> None:
        self._logging.out(f"Thumbnail added: {event.path}")