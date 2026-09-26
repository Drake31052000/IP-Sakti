"""
files.py — upload validation, safe storage, extraction, and audit logging.

Implements Plan Section 8 Steps 1-3.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import uuid4

from fastapi import HTTPException

from database import get_conn, UPLOAD_DIR

ALLOWED_TYPES = {
    "text/plain",
    "text/csv",
    "text/markdown",
    "application/pdf",
    "application/json",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
# A few browsers/OSes send no content-type or a generic octet-stream for
# .md/.txt files; fall back to checking the extension in that case.
ALLOWED_EXTENSIONS = {".txt", ".md", ".csv", ".json", ".pdf", ".docx"}
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB


def validate_upload(filename: str, content_type: Optional[str], size: int) -> None:
    suffix = Path(filename).suffix.lower()
    type_ok = content_type in ALLOWED_TYPES if content_type else False
    ext_ok = suffix in ALLOWED_EXTENSIONS
    if not (type_ok or ext_ok):
        raise HTTPException(status_code=415, detail="Unsupported file type.")
    if size > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File too large (10 MB limit).")
    if size == 0:
        raise HTTPException(status_code=400, detail="File is empty.")


def new_storage_name(original_filename: str) -> str:
    """Server-generated, unguessable storage name (Section 8 Step 2). The
    original filename is kept only as metadata in the `files` table, never
    used to address the file on disk."""
    suffix = Path(original_filename).suffix.lower()
    return f"{uuid4().hex}{suffix}"


def extract_text_from_file(path: Path, content_type: Optional[str]) -> str:
    """Best-effort text extraction so uploaded files can be chunked/searched.
    Supports .txt/.md/.csv/.json natively; uses PyPDF2/python-docx for PDFs
    and .docx if those optional packages are installed."""
    suffix = path.suffix.lower()
    try:
        if suffix in (".txt", ".md", ".csv", ".json"):
            return path.read_text(encoding="utf-8", errors="ignore")

        if suffix == ".pdf":
            try:
                from PyPDF2 import PdfReader

                reader = PdfReader(str(path))
                return "\n".join((page.extract_text() or "") for page in reader.pages)
            except Exception:
                return ""

        if suffix == ".docx":
            try:
                import docx

                document = docx.Document(str(path))
                return "\n".join(p.text for p in document.paragraphs)
            except Exception:
                return ""
    except Exception:
        return ""
    return ""


# --------------------------------------------------------------------------
# Audit logging (Section 8 Step 3)
# --------------------------------------------------------------------------
def audit(user_id: Optional[int], action: str, resource: str = "", request_id: str = "", details: str = "") -> None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO audit_log (user_id, action, resource, timestamp, request_id, details) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, action, resource, datetime.utcnow().isoformat(timespec="seconds"), request_id, details),
    )
    conn.commit()
    conn.close()


# --------------------------------------------------------------------------
# Answer feedback (frontend "thumbs up / thumbs down" on a query response)
# --------------------------------------------------------------------------
def save_feedback(user_id: Optional[int], role: Optional[str], query_text: Optional[str],
                   answer_snippet: Optional[str], rating: str, language: Optional[str]) -> None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO feedback (user_id, role, query_text, answer_snippet, rating, language) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, role, (query_text or "")[:2000], (answer_snippet or "")[:2000], rating, language),
    )
    conn.commit()
    conn.close()
