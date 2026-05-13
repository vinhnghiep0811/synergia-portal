"""Shared fixtures for integration tests (fully ephemeral)."""

import hashlib
import json
import math
import sqlite3
import unittest
import uuid

from app.services.llm_extraction_service import LLMExtractionService
from app.services.pdf_parse_service import build_fingerprint, detect_doi


class FakeQueue:
    """Simple in-process queue for integration tests."""

    def __init__(self) -> None:
        self._jobs: list[dict] = []

    def enqueue(self, stage: str, payload: dict) -> dict:
        job = {
            "id": str(len(self._jobs) + 1),
            "stage": stage,
            "payload": payload,
        }
        self._jobs.append(job)
        return job

    def pop_next(self) -> dict | None:
        if not self._jobs:
            return None
        return self._jobs.pop(0)

    @property
    def size(self) -> int:
        return len(self._jobs)


class FakeStorageService:
    """In-memory storage (cleared each test)."""

    def __init__(self) -> None:
        self._objects: dict[str, bytes] = {}

    def upload_pdf(self, filename: str, content: bytes) -> str:
        object_name = f"{uuid.uuid4().hex}_{filename}"
        storage_path = f"s3://papers/{object_name}"
        self._objects[storage_path] = content
        return storage_path

    def download(self, storage_path: str) -> bytes:
        if storage_path not in self._objects:
            raise FileNotFoundError(storage_path)
        return self._objects[storage_path]

    def list_paths(self) -> list[str]:
        return sorted(self._objects.keys())


class WorkflowHarness:
    """Ephemeral workflow harness backed by SQLite in-memory."""

    def __init__(self) -> None:
        self.db = sqlite3.connect(":memory:")
        self.db.row_factory = sqlite3.Row
        self.queue = FakeQueue()
        self.storage = FakeStorageService()
        self._init_schema()

    def _init_schema(self) -> None:
        self.db.executescript(
            """
            CREATE TABLE papers (
              id TEXT PRIMARY KEY,
              filename TEXT NOT NULL,
              storage_path TEXT NOT NULL,
              status TEXT NOT NULL,
              doi TEXT,
              fingerprint TEXT,
              canonical_key TEXT,
              duplicate_of TEXT
            );

            CREATE TABLE canonicals (
              canonical_key TEXT PRIMARY KEY,
              canonical_type TEXT NOT NULL,
              doi TEXT,
              fingerprint TEXT,
              extraction_json TEXT,
              citation_score REAL NOT NULL DEFAULT 0
            );

            CREATE TABLE chunks (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              canonical_key TEXT NOT NULL,
              section_type TEXT NOT NULL,
              content TEXT NOT NULL,
              embedding_json TEXT
            );

            CREATE TABLE extraction_cache (
              canonical_key TEXT PRIMARY KEY,
              payload_json TEXT NOT NULL
            );

            CREATE TABLE citations (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              source_key TEXT NOT NULL,
              target_key TEXT NOT NULL,
              weight REAL NOT NULL
            );
            """
        )
        self.db.commit()

    def upload_pdf(self, filename: str, content: bytes, max_size_bytes: int = 20 * 1024 * 1024) -> str:
        if not filename or not filename.lower().endswith(".pdf"):
            raise ValueError("Only .pdf files are supported")
        if not content:
            raise ValueError("Empty content")
        if len(content) > max_size_bytes:
            raise ValueError("File too large")
        if not content.startswith(b"%PDF"):
            raise ValueError("Invalid PDF content")

        paper_id = str(uuid.uuid4())
        storage_path = self.storage.upload_pdf(filename, content)
        self.db.execute(
            "INSERT INTO papers (id, filename, storage_path, status) VALUES (?, ?, ?, ?)",
            (paper_id, filename, storage_path, "uploaded"),
        )
        self.db.commit()
        return paper_id

    def enqueue_stage(self, stage: str, payload: dict) -> dict:
        return self.queue.enqueue(stage, payload)

    def parse_and_map(self, paper_id: str, extracted_text: str) -> dict:
        doi = detect_doi(extracted_text)
        fingerprint = build_fingerprint(extracted_text)
        canonical_key = doi or fingerprint
        canonical_type = "DOI" if doi else "FINGERPRINT"

        existing = self.db.execute(
            "SELECT canonical_key FROM canonicals WHERE canonical_key = ?",
            (canonical_key,),
        ).fetchone()
        if not existing:
            self.db.execute(
                """
                INSERT INTO canonicals (canonical_key, canonical_type, doi, fingerprint)
                VALUES (?, ?, ?, ?)
                """,
                (canonical_key, canonical_type, doi, fingerprint),
            )

        self.db.execute(
            """
            UPDATE papers
            SET status = ?, doi = ?, fingerprint = ?, canonical_key = ?
            WHERE id = ?
            """,
            ("parsed", doi, fingerprint, canonical_key, paper_id),
        )
        self.db.commit()
        return {
            "paper_id": paper_id,
            "doi": doi,
            "fingerprint": fingerprint,
            "canonical_key": canonical_key,
            "canonical_type": canonical_type,
        }

    def build_structure(self, canonical_key: str, markdown_text: str) -> int:
        blocks = [b.strip() for b in markdown_text.split("\n\n") if b.strip()]
        for idx, block in enumerate(blocks):
            section_type = "abstract" if idx == 0 else "body"
            self.db.execute(
                """
                INSERT INTO chunks (canonical_key, section_type, content)
                VALUES (?, ?, ?)
                """,
                (canonical_key, section_type, block),
            )
        self.db.commit()
        return len(blocks)

    def run_llm_extraction(self, canonical_key: str, raw_result: dict) -> dict:
        service = object.__new__(LLMExtractionService)
        if not service._has_expected_extraction_schema(raw_result):
            raise ValueError("Invalid extraction schema")

        normalized = service._normalize_result(raw_result, pages=[], input_text="")
        payload = json.dumps(normalized)

        self.db.execute(
            "UPDATE canonicals SET extraction_json = ? WHERE canonical_key = ?",
            (payload, canonical_key),
        )
        self.db.execute(
            """
            INSERT INTO extraction_cache (canonical_key, payload_json)
            VALUES (?, ?)
            ON CONFLICT(canonical_key) DO UPDATE SET payload_json = excluded.payload_json
            """,
            (canonical_key, payload),
        )
        self.db.commit()
        return normalized

    def get_cached_extraction(self, canonical_key: str) -> dict | None:
        row = self.db.execute(
            "SELECT payload_json FROM extraction_cache WHERE canonical_key = ?",
            (canonical_key,),
        ).fetchone()
        if not row:
            return None
        return json.loads(row["payload_json"])

    def create_embeddings(self, canonical_key: str) -> int:
        rows = self.db.execute(
            "SELECT id, content FROM chunks WHERE canonical_key = ? ORDER BY id",
            (canonical_key,),
        ).fetchall()

        for row in rows:
            vector = self._embed_text(row["content"])
            self.db.execute(
                "UPDATE chunks SET embedding_json = ? WHERE id = ?",
                (json.dumps(vector), row["id"]),
            )

        self.db.commit()
        return len(rows)

    def semantic_search(self, query: str, top_k: int = 3) -> list[dict]:
        query_vec = self._embed_text(query)
        rows = self.db.execute(
            "SELECT id, canonical_key, content, embedding_json FROM chunks WHERE embedding_json IS NOT NULL"
        ).fetchall()

        scored: list[dict] = []
        for row in rows:
            emb = json.loads(row["embedding_json"])
            score = self._cosine(query_vec, emb)
            scored.append(
                {
                    "chunk_id": row["id"],
                    "canonical_key": row["canonical_key"],
                    "content": row["content"],
                    "score": score,
                }
            )

        scored.sort(key=lambda item: item["score"], reverse=True)
        return scored[:top_k]

    def add_citation(self, source_key: str, target_key: str, weight: float) -> None:
        self.db.execute(
            "INSERT INTO citations (source_key, target_key, weight) VALUES (?, ?, ?)",
            (source_key, target_key, weight),
        )
        self.db.commit()

    def score_citation_graph(self, target_key: str) -> float:
        row = self.db.execute(
            "SELECT COALESCE(SUM(weight), 0) AS total FROM citations WHERE target_key = ?",
            (target_key,),
        ).fetchone()
        total = float(row["total"])
        self.db.execute(
            "UPDATE canonicals SET citation_score = ? WHERE canonical_key = ?",
            (total, target_key),
        )
        self.db.commit()
        return total

    def mark_duplicate(self, paper_id: str, original_paper_id: str) -> None:
        self.db.execute(
            "UPDATE papers SET duplicate_of = ?, status = ? WHERE id = ?",
            (original_paper_id, "duplicate", paper_id),
        )
        self.db.commit()

    def canonical_count(self) -> int:
        row = self.db.execute("SELECT COUNT(*) AS total FROM canonicals").fetchone()
        return int(row["total"])

    def paper(self, paper_id: str) -> sqlite3.Row:
        row = self.db.execute("SELECT * FROM papers WHERE id = ?", (paper_id,)).fetchone()
        if row is None:
            raise KeyError(paper_id)
        return row

    def chunks_for(self, canonical_key: str) -> list[sqlite3.Row]:
        return self.db.execute(
            "SELECT * FROM chunks WHERE canonical_key = ? ORDER BY id",
            (canonical_key,),
        ).fetchall()

    def close(self) -> None:
        self.db.close()

    def _embed_text(self, text: str) -> list[float]:
        lower = text.lower()
        method_signal = float(lower.count("method") + lower.count("algorithm"))
        data_signal = float(lower.count("dataset") + lower.count("benchmark"))
        citation_signal = float(lower.count("citation") + lower.count("reference"))
        if method_signal == 0 and data_signal == 0 and citation_signal == 0:
            digest = hashlib.sha256(text.encode("utf-8")).digest()
            method_signal = digest[0] / 255
            data_signal = digest[1] / 255
            citation_signal = digest[2] / 255
        return [method_signal, data_signal, citation_signal]

    @staticmethod
    def _cosine(a: list[float], b: list[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(y * y for y in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)


class IntegrationEphemeralTestCase(unittest.TestCase):
    """Base class: fresh ephemeral queue/storage/db per test."""

    def setUp(self) -> None:
        self.workflow = WorkflowHarness()

    def tearDown(self) -> None:
        self.workflow.close()
