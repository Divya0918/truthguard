"""
Document ingestion service.

Pipeline:
  1. Extract text (TXT/MD: direct; PDF: pdfplumber; DOCX: python-docx)
  2. Chunk text into ~500-word overlapping segments
  3. Generate embeddings per chunk
  4. Store DocumentChunk records with embedding JSON
  5. Update Document status → 'published'

Each public function manages its own database session to avoid
transaction-scope conflicts when called from the startup lifespan hook.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
import app.models  # ensure all models (User, Document, etc.) are registered on Base.metadata
from app.models.document import Document, DocumentChunk
from app.services.embedding import embedding_service


# ─── Text extraction ──────────────────────────────────────
def _extract_txt(path: str) -> str:
    return Path(path).read_text(encoding="utf-8", errors="replace")


def _extract_pdf(path: str) -> str:
    try:
        import pdfplumber  # type: ignore
        pages = []
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    pages.append(text)
        return "\n\n".join(pages)
    except ImportError:
        return f"[PDF extraction requires pdfplumber]\n{Path(path).name}"
    except Exception as e:
        return f"[PDF extraction error: {e}]"


def _extract_docx(path: str) -> str:
    try:
        from docx import Document as DocxDoc  # type: ignore
        doc = DocxDoc(path)
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    except ImportError:
        return f"[DOCX extraction requires python-docx]\n{Path(path).name}"
    except Exception as e:
        return f"[DOCX extraction error: {e}]"


def extract_text(file_path: str, file_type: str) -> str:
    ft = file_type.lower()
    if ft in ("txt", "md"):
        return _extract_txt(file_path)
    elif ft == "pdf":
        return _extract_pdf(file_path)
    elif ft == "docx":
        return _extract_docx(file_path)
    else:
        try:
            return _extract_txt(file_path)
        except Exception:
            return ""


# ─── Chunking ─────────────────────────────────────────────
def _split_chunks(text: str, chunk_size: int = 500, overlap: int = 80) -> list[dict]:
    """Split text into chunks. Supports explicit multi-page documents with PAGE breaks."""
    # Check if document has explicit page delimiters like [PAGE 1 OF 2] or [PAGE 2 OF 2]
    page_matches = list(re.finditer(r'\[PAGE\s+(\d+)\s+OF\s+(\d+)(?::\s*([^\]]+))?\]', text, re.IGNORECASE))
    if len(page_matches) >= 2:
        chunks = []
        for i, match in enumerate(page_matches):
            page_num = match.group(1)
            subtitle = match.group(3) or f"Section {page_num}"
            start_pos = match.start()
            end_pos = page_matches[i + 1].start() if i + 1 < len(page_matches) else len(text)
            page_text = text[start_pos:end_pos].strip()
            chunks.append({
                "chunk_index": i,
                "content": page_text,
                "section_title": f"Page {page_num}: {subtitle.strip()}",
                "word_count": len(page_text.split()),
            })
        return chunks

    paragraphs = [p.strip() for p in re.split(r'\n{2,}', text) if p.strip()]

    chunks: list[dict] = []
    current_words: list[str] = []
    current_section = "Main"
    chunk_index = 0

    for para in paragraphs:
        # Detect section headings
        if re.match(r'^(#+\s|[A-Z][A-Z\s]{3,}:?\s*$|\d+\.\s+[A-Z])', para):
            current_section = para[:80]

        para_words = para.split()

        for word in para_words:
            current_words.append(word)
            if len(current_words) >= chunk_size:
                chunks.append({
                    "chunk_index": chunk_index,
                    "content": " ".join(current_words),
                    "section_title": current_section,
                    "word_count": len(current_words),
                })
                chunk_index += 1
                current_words = current_words[-overlap:]

    # Remainder
    if len(current_words) > 20:
        chunks.append({
            "chunk_index": chunk_index,
            "content": " ".join(current_words),
            "section_title": current_section,
            "word_count": len(current_words),
        })

    return chunks


# ─── Main ingestion function ──────────────────────────────
async def ingest_document(doc_id: str, _unused_db: AsyncSession | None = None) -> None:
    """Full ingestion pipeline: extract → chunk → embed → store.

    Always opens its own database session to avoid transaction conflicts.
    The _unused_db parameter exists for backward compatibility but is ignored.
    """
    async with AsyncSessionLocal() as db:
        # Fetch document
        result = await db.execute(select(Document).where(Document.id == doc_id))
        doc = result.scalar_one_or_none()
        if not doc:
            raise ValueError(f"Document {doc_id} not found")

        # Mark as processing
        doc.status = "processing"
        doc.processing_error = None
        await db.commit()
        await db.refresh(doc)

        try:
            # Handle clarification pseudo-documents
            if doc.file_path.startswith("clarification:"):
                doc.status = "published"
                await db.commit()
                return

            if not os.path.exists(doc.file_path):
                # Attempt to find the file in standard locations
                fname = Path(doc.file_path).name
                backend_root = Path(__file__).parent.parent.parent
                candidates = [
                    backend_root / "data" / "policies" / fname,
                    backend_root / "data" / "uploads" / fname,
                    Path("data/policies") / fname,
                    Path("data/uploads") / fname,
                ]
                resolved_path = None
                for cand in candidates:
                    if cand.exists():
                        resolved_path = str(cand.resolve())
                        break

                if resolved_path:
                    doc.file_path = resolved_path
                else:
                    raise FileNotFoundError(f"File not found: {doc.file_path}")

            # 1. Extract text
            text = extract_text(doc.file_path, doc.file_type)
            if not text.strip():
                raise ValueError("Extracted text is empty")

            # 2. Chunk
            raw_chunks = _split_chunks(text)
            if not raw_chunks:
                raise ValueError("No chunks generated from text")

            # 3. Delete existing chunks (idempotent re-ingestion)
            await db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == doc_id))
            await db.flush()

            # 4. Embed + store
            texts = [c["content"] for c in raw_chunks]
            embeddings = await embedding_service.encode(texts)

            for chunk_data, emb in zip(raw_chunks, embeddings):
                chunk = DocumentChunk(
                    document_id=doc_id,
                    chunk_index=chunk_data["chunk_index"],
                    content=chunk_data["content"],
                    section_title=chunk_data.get("section_title"),
                    word_count=chunk_data.get("word_count", 0),
                    embedding_json=json.dumps(emb),
                    document_title=doc.title,
                    effective_date=doc.effective_date,
                    version_label=doc.version_label,
                )
                db.add(chunk)

            await db.flush()

            # 5. Mark published
            from datetime import datetime, timezone
            doc.status = "published"
            doc.chunk_count = len(raw_chunks)
            doc.published_at = datetime.now(timezone.utc)
            await db.commit()

        except Exception as exc:
            doc.status = "rejected"
            # Strip non-ASCII chars to avoid Windows charmap encoding errors
            err_msg = str(exc).encode("ascii", errors="replace").decode("ascii")
            doc.processing_error = err_msg[:500]
            try:
                await db.commit()
            except Exception:
                await db.rollback()
            raise


# ─── Seed pre-loaded documents ────────────────────────────
async def ingest_all_policies(db: AsyncSession) -> None:
    """Ingest all pre-loaded policy .txt files from data/policies/ (idempotent).

    Uses independent sessions per document to avoid transaction conflicts.
    """
    policies_dir = Path("data/policies")
    if not policies_dir.exists():
        # Try relative to the backend root
        policies_dir = Path(__file__).parent.parent.parent / "data" / "policies"
    if not policies_dir.exists():
        print("[WARN] data/policies/ not found — skipping policy seeding")
        return

    txt_files = sorted(policies_dir.glob("*.txt"))
    print(f"[INFO] Found {len(txt_files)} policy files to check")

    for txt_file in txt_files:
        try:
            # Each check uses a fresh session to avoid stale transaction issues
            doc_id = None
            async with AsyncSessionLocal() as check_db:
                result = await check_db.execute(
                    select(Document).where(Document.original_filename == txt_file.name)
                )
                existing = result.scalar_one_or_none()
                if existing and existing.status == "published" and existing.chunk_count > 0 and os.path.exists(existing.file_path):
                    print(f"[SKIP] {txt_file.name} (already published with {existing.chunk_count} chunks)")
                    continue

                if existing:
                    existing.file_path = str(txt_file.resolve())
                    existing.status = "pending"
                    await check_db.commit()
                    doc_id = existing.id

            if not doc_id:
                # Derive a clean title
                raw_stem = txt_file.stem
                parts = raw_stem.split("_")
                pol_num = parts[1] if len(parts) > 1 and parts[1].isdigit() else "00"
                title_words = " ".join(p for p in parts[2:]).replace("_", " ").title()
                doc_title = f"{title_words} (MNB-{pol_num})" if title_words else raw_stem.replace("_", " ").title()

                # Insert document in its own session then ingest
                async with AsyncSessionLocal() as insert_db:
                    doc = Document(
                        title=doc_title,
                        description=f"Pre-loaded synthetic banking policy: {txt_file.name}",
                        original_filename=txt_file.name,
                        file_path=str(txt_file.resolve()),
                        file_type="txt",
                        status="pending",
                        version_label="v1.0",
                        effective_date="2024-01-01",
                    )
                    insert_db.add(doc)
                    await insert_db.commit()
                    await insert_db.refresh(doc)
                    doc_id = doc.id

            print(f"[INFO] Ingesting: {txt_file.name} -> {doc_id}")
            # ingest_document uses its own session
            await ingest_document(doc_id)
            print(f"[OK]   Published: {txt_file.name}")

        except Exception as exc:
            print(f"[ERROR] Failed to ingest {txt_file.name}: {exc}")
