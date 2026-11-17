"""Priority Document service.

Manages the central Priority Document containing admin-verified customer Q&A pairs
with timestamps. Ensures questions answered by the admin are stored here,
timestamped, and given highest precedence during retrieval unless a newer
policy document is published after the timestamp.
"""
from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.document import Document
from app.services.ingestion import ingest_document

PRIORITY_DOC_FILENAME = "priority_document.txt"
PRIORITY_DOC_TITLE = "Priority Document — Verified Customer Q&A"
PRIORITY_DOC_VERSION = "PRIORITY"


def _get_priority_doc_path() -> Path:
    backend_root = Path(__file__).parent.parent.parent
    path = backend_root / "data" / "policies" / PRIORITY_DOC_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def parse_priority_entries(text: str) -> list[dict[str, Any]]:
    """Parse structured Q&A entries from priority document text."""
    pattern = re.compile(
        r'\[TIMESTAMP:\s*([^\]]+)\]\s*\nQUESTION:\s*(.+?)\nADMIN ANSWER:\s*(.+?)(?=\n-+\n|\Z)',
        re.DOTALL
    )
    entries: list[dict[str, Any]] = []
    for match in pattern.finditer(text):
        ts_str = match.group(1).strip()
        q = match.group(2).strip()
        a = match.group(3).strip()

        # Try parsing ISO/UTC datetime
        dt = None
        for fmt in ("%Y-%m-%d %H:%M:%S UTC", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                clean_ts = ts_str.replace("UTC", "").strip()
                dt = datetime.strptime(clean_ts, fmt).replace(tzinfo=timezone.utc)
                break
            except Exception:
                continue

        entries.append({
            "timestamp_str": ts_str,
            "timestamp_dt": dt or datetime.now(timezone.utc),
            "question": q,
            "answer": a,
            "raw": match.group(0),
        })
    return entries


async def get_or_create_priority_document() -> Document:
    """Get the priority document DB record or create it if missing."""
    doc_path = _get_priority_doc_path()
    if not doc_path.exists():
        header = (
            "================================================================================\n"
            "MERIDIAN NATIONAL BANK (MNB) — PRIORITY KNOWLEDGE BASE\n"
            "ADMIN VERIFIED CUSTOMER Q&A & POLICY CLARIFICATIONS\n"
            "STATUS: ACTIVE | PRIORITY LEVEL: HIGHEST\n"
            "================================================================================\n\n"
        )
        doc_path.write_text(header, encoding="utf-8")

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Document).where(
                (Document.original_filename == PRIORITY_DOC_FILENAME) |
                (Document.version_label == PRIORITY_DOC_VERSION)
            )
        )
        doc = result.scalar_one_or_none()
        if not doc:
            doc = Document(
                title=PRIORITY_DOC_TITLE,
                description="Central Priority Knowledge Base containing admin-verified answers to customer questions.",
                original_filename=PRIORITY_DOC_FILENAME,
                file_path=str(doc_path.resolve()),
                file_type="txt",
                status="published",
                version_label=PRIORITY_DOC_VERSION,
                effective_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                chunk_count=0,
            )
            db.add(doc)
            await db.commit()
            await db.refresh(doc)

            # Ingest initial
            await ingest_document(doc.id)
            await db.refresh(doc)
        else:
            # Ensure file path is resolved
            if not os.path.exists(doc.file_path) or doc.file_path != str(doc_path.resolve()):
                doc.file_path = str(doc_path.resolve())
                await db.commit()
                await db.refresh(doc)

        return doc


async def append_to_priority_doc(question: str, answer: str, timestamp_str: str | None = None) -> Document:
    """Append a customer question, admin answer, and timestamp to the Priority Document.
    
    Re-ingests the Priority Document immediately so new chunks are active.
    """
    doc_path = _get_priority_doc_path()
    # Ensure base file exists
    await get_or_create_priority_document()

    if not timestamp_str:
        timestamp_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    entry = (
        f"\n[TIMESTAMP: {timestamp_str}]\n"
        f"QUESTION: {question.strip()}\n"
        f"ADMIN ANSWER: {answer.strip()}\n"
        f"--------------------------------------------------------------------------------\n"
    )

    # Append to file
    with open(doc_path, "a", encoding="utf-8") as f:
        f.write(entry)

    # Fetch DB document
    doc = await get_or_create_priority_document()

    # Re-ingest chunks immediately
    await ingest_document(doc.id)

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Document).where(Document.id == doc.id))
        updated_doc = result.scalar_one()
        updated_doc.file_size_bytes = doc_path.stat().st_size
        updated_doc.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(updated_doc)
        print(f"[OK] Priority Document updated with new Q&A! Total chunks: {updated_doc.chunk_count}")
        return updated_doc
