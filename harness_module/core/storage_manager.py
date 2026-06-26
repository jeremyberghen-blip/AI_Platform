import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

import aiosqlite


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


SESSION_REGISTRY_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    session_id              TEXT PRIMARY KEY,
    character_id            TEXT NOT NULL,
    model_id                TEXT,
    started_at              TEXT NOT NULL,
    closed_at               TEXT,
    message_count           INTEGER DEFAULT 0,
    total_prompt_tokens     INTEGER DEFAULT 0,
    total_completion_tokens INTEGER DEFAULT 0
);
"""

IMAGE_CATALOG_SCHEMA = """
CREATE TABLE IF NOT EXISTS images (
    image_id         TEXT PRIMARY KEY,
    character_id     TEXT NOT NULL,
    session_id       TEXT NOT NULL,
    filename         TEXT NOT NULL,
    prompt           TEXT NOT NULL,
    negative_prompt  TEXT,
    model            TEXT NOT NULL,
    loras            TEXT,
    controlnet_type  TEXT,
    controlnet_weight REAL,
    seed             INTEGER,
    cfg              REAL,
    steps            INTEGER,
    sampler          TEXT,
    width            INTEGER,
    height           INTEGER,
    character_tags   TEXT,
    style_tags       TEXT,
    rating           INTEGER,
    notes            TEXT,
    created_at       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS lora_registry (
    lora_id              TEXT PRIMARY KEY,
    name                 TEXT NOT NULL,
    filename             TEXT NOT NULL,
    base_model           TEXT NOT NULL,
    trigger_word         TEXT,
    recommended_strength REAL DEFAULT 0.8,
    description          TEXT,
    character_tag        TEXT,
    created_at           TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS prompt_templates (
    template_id TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    category    TEXT NOT NULL,
    content     TEXT NOT NULL,
    notes       TEXT DEFAULT '',
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS workflows (
    workflow_id   TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    description   TEXT DEFAULT '',
    workflow_json TEXT NOT NULL,
    base_model    TEXT,
    tags          TEXT DEFAULT '[]',
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS training_runs (
    run_id        TEXT PRIMARY KEY,
    lora_name     TEXT NOT NULL,
    base_model    TEXT NOT NULL,
    trainer       TEXT NOT NULL,
    dataset_path  TEXT,
    steps         INTEGER,
    learning_rate REAL,
    network_rank  INTEGER,
    trigger_word  TEXT,
    output_path   TEXT,
    notes         TEXT,
    started_at    TEXT NOT NULL,
    completed_at  TEXT
);
"""


class StorageManager:
    def __init__(self, storage_path: Path) -> None:
        self.storage_path = storage_path
        self._registry_dbs: dict[str, aiosqlite.Connection] = {}
        self._media_db: aiosqlite.Connection | None = None

    async def init(self) -> None:
        self.storage_path.mkdir(parents=True, exist_ok=True)
        (self.storage_path / "sessions").mkdir(exist_ok=True)
        (self.storage_path / "captures").mkdir(exist_ok=True)
        (self.storage_path / "registry").mkdir(exist_ok=True)
        (self.storage_path / "media").mkdir(exist_ok=True)

        self._media_db = await aiosqlite.connect(self.storage_path / "registry" / "media_catalog.db")
        await self._media_db.executescript(IMAGE_CATALOG_SCHEMA)
        await self._media_db.commit()

    async def _registry_for(self, character_id: str) -> aiosqlite.Connection:
        if character_id not in self._registry_dbs:
            db_path = self.storage_path / "registry" / f"{character_id}.db"
            conn = await aiosqlite.connect(db_path)
            await conn.execute(SESSION_REGISTRY_SCHEMA)
            await conn.commit()
            self._registry_dbs[character_id] = conn
        return self._registry_dbs[character_id]

    # --- Session log ---

    async def write_message(self, character_id: str, session_id: str, seq: int, role: str,
                             content: str, tokens: int | None = None, latency_ms: int | None = None) -> None:
        log_dir = self.storage_path / "sessions" / character_id / session_id
        log_dir.mkdir(parents=True, exist_ok=True)
        entry = {
            "seq": seq,
            "role": role,
            "content": content,
            "timestamp": _now_iso(),
        }
        if tokens is not None:
            entry["tokens"] = tokens
        if latency_ms is not None:
            entry["latency_ms"] = latency_ms

        log_path = log_dir / "log.jsonl"
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._append_jsonl, log_path, entry)

    def _append_jsonl(self, path: Path, entry: dict) -> None:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

    async def write_telemetry(self, character_id: str, session_id: str, telemetry: dict) -> None:
        log_dir = self.storage_path / "sessions" / character_id / session_id
        log_dir.mkdir(parents=True, exist_ok=True)
        path = log_dir / "telemetry.jsonl"
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._append_jsonl, path, {**telemetry, "timestamp": _now_iso()})

    async def write_session_metadata(self, session_data: dict) -> None:
        character_id = session_data["character_id"]
        session_id = session_data["session_id"]
        log_dir = self.storage_path / "sessions" / character_id / session_id
        log_dir.mkdir(parents=True, exist_ok=True)
        path = log_dir / "metadata.json"
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, path.write_text, json.dumps(session_data, indent=2))

    # --- Session registry ---

    async def upsert_session(self, session_data: dict) -> None:
        db = await self._registry_for(session_data["character_id"])
        await db.execute(
            """INSERT INTO sessions
               (session_id, character_id, model_id, started_at, closed_at,
                message_count, total_prompt_tokens, total_completion_tokens)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(session_id) DO UPDATE SET
                 closed_at = excluded.closed_at,
                 message_count = excluded.message_count,
                 total_prompt_tokens = excluded.total_prompt_tokens,
                 total_completion_tokens = excluded.total_completion_tokens""",
            (
                session_data["session_id"],
                session_data["character_id"],
                session_data.get("model_id"),
                session_data["started_at"],
                session_data.get("closed_at"),
                session_data.get("message_count", 0),
                session_data.get("total_prompt_tokens", 0),
                session_data.get("total_completion_tokens", 0),
            ),
        )
        await db.commit()

    async def list_sessions(self, character_id: str, limit: int = 50, offset: int = 0) -> list[dict]:
        db = await self._registry_for(character_id)
        async with db.execute(
            "SELECT * FROM sessions ORDER BY started_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ) as cursor:
            rows = await cursor.fetchall()
            cols = [d[0] for d in cursor.description]
            return [dict(zip(cols, row)) for row in rows]

    async def read_session_log(self, character_id: str, session_id: str) -> list[dict]:
        path = self.storage_path / "sessions" / character_id / session_id / "log.jsonl"
        if not path.exists():
            return []
        loop = asyncio.get_event_loop()
        lines = await loop.run_in_executor(None, path.read_text)
        return [json.loads(line) for line in lines.splitlines() if line.strip()]

    async def write_thought(
        self,
        character_id: str,
        session_id: str,
        seq: int,
        thought: str,
        trigger_seq: int | None = None,
    ) -> None:
        log_dir = self.storage_path / "sessions" / character_id / session_id
        log_dir.mkdir(parents=True, exist_ok=True)
        entry: dict = {"seq": seq, "thought": thought, "timestamp": _now_iso()}
        if trigger_seq is not None:
            entry["trigger_seq"] = trigger_seq
        path = log_dir / "thoughts.jsonl"
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._append_jsonl, path, entry)

    async def read_thoughts(self, character_id: str, session_id: str) -> list[dict]:
        path = self.storage_path / "sessions" / character_id / session_id / "thoughts.jsonl"
        if not path.exists():
            return []
        loop = asyncio.get_event_loop()
        lines = await loop.run_in_executor(None, path.read_text)
        return [json.loads(line) for line in lines.splitlines() if line.strip()]

    # --- Media catalog ---

    async def insert_image(self, image_data: dict) -> None:
        assert self._media_db is not None
        await self._media_db.execute(
            """INSERT INTO images
               (image_id, character_id, session_id, filename, prompt, negative_prompt,
                model, loras, controlnet_type, controlnet_weight, seed, cfg, steps, sampler,
                width, height, character_tags, style_tags, rating, notes, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                image_data["image_id"], image_data["character_id"], image_data["session_id"],
                image_data["filename"], image_data["prompt"], image_data.get("negative_prompt"),
                image_data["model"], json.dumps(image_data.get("loras", [])),
                image_data.get("controlnet_type"), image_data.get("controlnet_weight"),
                image_data.get("seed"), image_data.get("cfg"), image_data.get("steps"),
                image_data.get("sampler"), image_data.get("width"), image_data.get("height"),
                json.dumps(image_data.get("character_tags", [])),
                json.dumps(image_data.get("style_tags", [])),
                image_data.get("rating"), image_data.get("notes"), _now_iso(),
            ),
        )
        await self._media_db.commit()

    async def list_images(self, character_id: str | None = None,
                          limit: int = 50, offset: int = 0) -> list[dict]:
        assert self._media_db is not None
        if character_id:
            query = "SELECT * FROM images WHERE character_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?"
            params = (character_id, limit, offset)
        else:
            query = "SELECT * FROM images ORDER BY created_at DESC LIMIT ? OFFSET ?"
            params = (limit, offset)
        async with self._media_db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            cols = [d[0] for d in cursor.description]
            results = []
            for row in rows:
                d = dict(zip(cols, row))
                for field in ("loras", "character_tags", "style_tags"):
                    if d.get(field):
                        d[field] = json.loads(d[field])
                    else:
                        d[field] = []
                results.append(d)
            return results

    async def update_image_rating(self, image_id: str, rating: int) -> None:
        assert self._media_db is not None
        await self._media_db.execute("UPDATE images SET rating = ? WHERE image_id = ?", (rating, image_id))
        await self._media_db.commit()

    async def update_image_notes(self, image_id: str, notes: str) -> None:
        assert self._media_db is not None
        await self._media_db.execute("UPDATE images SET notes = ? WHERE image_id = ?", (notes, image_id))
        await self._media_db.commit()

    # --- Lora registry ---

    async def insert_lora(self, lora_data: dict) -> None:
        assert self._media_db is not None
        await self._media_db.execute(
            """INSERT INTO lora_registry
               (lora_id, name, filename, base_model, trigger_word, recommended_strength,
                description, character_tag, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                lora_data["lora_id"], lora_data["name"], lora_data["filename"],
                lora_data["base_model"], lora_data.get("trigger_word"),
                lora_data.get("recommended_strength", 0.8),
                lora_data.get("description", ""), lora_data.get("character_tag"), _now_iso(),
            ),
        )
        await self._media_db.commit()

    async def list_loras(self) -> list[dict]:
        assert self._media_db is not None
        async with self._media_db.execute("SELECT * FROM lora_registry ORDER BY created_at DESC") as cursor:
            rows = await cursor.fetchall()
            cols = [d[0] for d in cursor.description]
            return [dict(zip(cols, row)) for row in rows]

    # --- Prompt templates ---

    async def insert_prompt_template(self, data: dict) -> None:
        assert self._media_db is not None
        await self._media_db.execute(
            "INSERT INTO prompt_templates (template_id, name, category, content, notes, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (data["template_id"], data["name"], data["category"], data["content"], data.get("notes", ""), _now_iso()),
        )
        await self._media_db.commit()

    async def list_prompt_templates(self, category: str | None = None) -> list[dict]:
        assert self._media_db is not None
        if category:
            query = "SELECT * FROM prompt_templates WHERE category = ? ORDER BY name"
            params = (category,)
        else:
            query = "SELECT * FROM prompt_templates ORDER BY category, name"
            params = ()
        async with self._media_db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            cols = [d[0] for d in cursor.description]
            return [dict(zip(cols, row)) for row in rows]

    # --- Workflows ---

    async def insert_workflow(self, data: dict) -> None:
        assert self._media_db is not None
        now = _now_iso()
        await self._media_db.execute(
            """INSERT INTO workflows (workflow_id, name, description, workflow_json, base_model, tags, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (data["workflow_id"], data["name"], data.get("description", ""),
             json.dumps(data["workflow_json"]), data.get("base_model"),
             json.dumps(data.get("tags", [])), now, now),
        )
        await self._media_db.commit()

    async def list_workflows(self) -> list[dict]:
        assert self._media_db is not None
        async with self._media_db.execute("SELECT * FROM workflows ORDER BY updated_at DESC") as cursor:
            rows = await cursor.fetchall()
            cols = [d[0] for d in cursor.description]
            results = []
            for row in rows:
                d = dict(zip(cols, row))
                if d.get("tags"):
                    d["tags"] = json.loads(d["tags"])
                else:
                    d["tags"] = []
                d.pop("workflow_json", None)
                results.append(d)
            return results

    async def get_workflow(self, workflow_id: str) -> dict | None:
        assert self._media_db is not None
        async with self._media_db.execute("SELECT * FROM workflows WHERE workflow_id = ?", (workflow_id,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            cols = [d[0] for d in cursor.description]
            d = dict(zip(cols, row))
            d["workflow_json"] = json.loads(d["workflow_json"])
            d["tags"] = json.loads(d.get("tags") or "[]")
            return d

    async def close(self) -> None:
        for db in self._registry_dbs.values():
            await db.close()
        if self._media_db:
            await self._media_db.close()
