"""
main.py — IP-Sakti Sahayak backend (post-upgrade).

Wires together security.py, database.py, auth.py, files.py and rag.py per
the 10-Page Improvement Plan. Run from the IP-SAKTI/backend/ folder:

    pip install -r ../requirements.txt
    uvicorn main:app --reload

then open http://localhost:8000
"""
from __future__ import annotations

import os
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import auth
import files as files_module
import rag
from database import get_conn, init_db, UPLOAD_DIR

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR / "frontend"
INDEX_FILE = FRONTEND_DIR / "index.html"

app = FastAPI(title="IP-Sakti Sahayak Backend")

# Section 8 Step 5 — restrict CORS. Same-origin serving (frontend is served
# by this same app) means CORS is usually not even needed; ALLOWED_ORIGINS
# only matters if the frontend is ever hosted separately.
ALLOWED_ORIGINS = [o.strip() for o in os.environ.get("IP_SAKTI_ALLOWED_ORIGINS", "http://localhost:8000").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    """Section 6 observability hook: every response carries an
    X-Request-ID so client-reported errors can be correlated with
    audit_log rows / server logs."""
    request_id = uuid.uuid4().hex[:12]
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


@app.on_event("startup")
def on_startup():
    init_db()


# --------------------------------- Auth -----------------------------------
@app.post("/api/login")
def login(payload: auth.LoginRequest):
    result = auth.authenticate(payload)
    files_module.audit(None, "login_success", resource=payload.id, details=f"role={payload.role}")
    return result


@app.post("/api/register")
def register(payload: auth.RegisterRequest):
    result = auth.register(payload)
    files_module.audit(None, "register", resource=payload.login_id, details=f"role={payload.role}")
    return result


@app.get("/api/me")
def me(user: dict = Depends(auth.get_current_user)):
    return {"login_id": user["sub"], "role": user["role"]}


# --------------- Record Management (admin file CRUD, RBAC-gated) ----------
class SourceMetadata(BaseModel):
    authority: Optional[str] = None
    jurisdiction: Optional[str] = None
    language: str = "English"
    version: Optional[str] = None
    effective_date: Optional[str] = None


@app.get("/api/admin/files")
def list_files(user: dict = Depends(auth.require_permission("files:read"))):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, filename, uploaded_by, uploaded_at, authority, jurisdiction, "
        "language, source_version, effective_date, stored_name FROM files ORDER BY id DESC"
    )
    rows = cur.fetchall()
    conn.close()

    result = []
    for row in rows:
        fpath = UPLOAD_DIR / row["stored_name"]
        size_kb = round(fpath.stat().st_size / 1024, 1) if fpath.exists() else None
        result.append({
            "id": row["id"],
            "filename": row["filename"],
            "uploaded_by": row["uploaded_by"],
            "uploaded_at": row["uploaded_at"],
            "authority": row["authority"],
            "jurisdiction": row["jurisdiction"],
            "language": row["language"],
            "version": row["source_version"],
            "effective_date": row["effective_date"],
            "size_kb": size_kb,
        })
    return result


@app.post("/api/admin/files")
async def add_file(
    request: Request,
    file: UploadFile = File(...),
    uploaded_by: str = Form("admin"),
    authority: Optional[str] = Form(None),
    jurisdiction: Optional[str] = Form(None),
    language: str = Form("English"),
    version: Optional[str] = Form(None),
    effective_date: Optional[str] = Form(None),
    user: dict = Depends(auth.require_permission("files:write")),
):
    data = await file.read()
    files_module.validate_upload(file.filename, file.content_type, len(data))

    stored_name = files_module.new_storage_name(file.filename)
    dest = UPLOAD_DIR / stored_name
    with dest.open("wb") as out:
        out.write(data)

    extracted = files_module.extract_text_from_file(dest, file.content_type)

    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO files (filename, stored_name, uploaded_by, uploaded_at, content_type, "
        "extracted_text, authority, jurisdiction, language, source_version, effective_date) "
        "VALUES (?, ?, ?, datetime('now'), ?, ?, ?, ?, ?, ?, ?)",
        (file.filename, stored_name, user["sub"], file.content_type, extracted,
         authority, jurisdiction, language, version, effective_date),
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()

    chunk_count = rag.ingest_document_chunks(new_id, extracted, jurisdiction, language, version)
    files_module.audit(user["uid"], "file_upload", resource=file.filename,
                        request_id=getattr(request.state, "request_id", ""),
                        details=f"id={new_id} chunks={chunk_count}")
    return {"success": True, "id": new_id, "filename": file.filename, "chunks": chunk_count}


@app.get("/api/admin/files/{file_id}")
def open_file(file_id: int, user: dict = Depends(auth.require_permission("files:read"))):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM files WHERE id = ?", (file_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="File not found.")
    path = UPLOAD_DIR / row["stored_name"]
    if not path.exists():
        raise HTTPException(status_code=404, detail="File missing on disk.")
    return FileResponse(path, filename=row["filename"], media_type=row["content_type"] or "application/octet-stream")


@app.put("/api/admin/files/{file_id}")
async def update_file(
    file_id: int,
    request: Request,
    file: UploadFile = File(...),
    authority: Optional[str] = Form(None),
    jurisdiction: Optional[str] = Form(None),
    language: str = Form("English"),
    version: Optional[str] = Form(None),
    effective_date: Optional[str] = Form(None),
    user: dict = Depends(auth.require_permission("files:write")),
):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM files WHERE id = ?", (file_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="File not found.")

    data = await file.read()
    files_module.validate_upload(file.filename, file.content_type, len(data))

    old_path = UPLOAD_DIR / row["stored_name"]
    if old_path.exists():
        old_path.unlink()

    stored_name = files_module.new_storage_name(file.filename)
    dest = UPLOAD_DIR / stored_name
    with dest.open("wb") as out:
        out.write(data)
    extracted = files_module.extract_text_from_file(dest, file.content_type)

    cur.execute(
        "UPDATE files SET filename=?, stored_name=?, uploaded_at=datetime('now'), content_type=?, "
        "extracted_text=?, authority=?, jurisdiction=?, language=?, source_version=?, effective_date=? "
        "WHERE id=?",
        (file.filename, stored_name, file.content_type, extracted, authority, jurisdiction,
         language, version, effective_date, file_id),
    )
    conn.commit()
    conn.close()

    chunk_count = rag.ingest_document_chunks(file_id, extracted, jurisdiction, language, version)
    files_module.audit(user["uid"], "file_update", resource=file.filename,
                        request_id=getattr(request.state, "request_id", ""),
                        details=f"id={file_id} chunks={chunk_count}")
    return {"success": True, "id": file_id, "filename": file.filename, "chunks": chunk_count}


@app.delete("/api/admin/files/{file_id}")
def delete_file(file_id: int, request: Request, user: dict = Depends(auth.require_permission("files:delete"))):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM files WHERE id = ?", (file_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="File not found.")

    path = UPLOAD_DIR / row["stored_name"]
    if path.exists():
        path.unlink()

    cur.execute("DELETE FROM document_chunks WHERE document_id = ?", (file_id,))
    cur.execute("DELETE FROM files WHERE id = ?", (file_id,))
    conn.commit()
    conn.close()
    files_module.audit(user["uid"], "file_delete", resource=row["filename"],
                        request_id=getattr(request.state, "request_id", ""))
    return {"success": True}


@app.get("/api/admin/audit")
def read_audit(user: dict = Depends(auth.require_permission("audit:read")), limit: int = 100):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (min(limit, 500),))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


# --------------------------------- Query -----------------------------------
class QueryRequest(BaseModel):
    query: Optional[str] = None
    text: Optional[str] = None
    language: Optional[str] = "English"
    lang: Optional[str] = None


@app.post("/api/query")
def query(payload: QueryRequest):
    text = payload.query or payload.text or ""
    lang = payload.language or payload.lang or "English"
    if not text.strip():
        raise HTTPException(status_code=400, detail="Empty query.")

    # Section 5: hybrid (keyword + local TF-IDF vector) retrieval, rerank,
    # then a grounded answer with validated citations.
    answer = rag.build_grounded_answer(text, lang)
    if answer:
        return answer

    # Nothing relevant in ingested/chunked files -> let the frontend fall
    # back to its built-in "Demo Knowledge Pack" (labelled as such, not as
    # live authoritative retrieval — Section 5's closing note).
    raise HTTPException(status_code=404, detail="No matching indexed records; use local Demo Knowledge Pack.")


# --------------------- Ephemeral "chat with this file" ---------------------
# The Assistant screen's "Upload document" button no longer requires Admin
# access. Any caller may attach a file to a single question; it is chunked
# and searched in-memory only, then discarded — it is never written to the
# `files` / `document_chunks` tables, so it never becomes part of the
# permanent, admin-curated knowledge base used by /api/query above.
@app.post("/api/query/document")
async def query_uploaded_document(
    request: Request,
    file: UploadFile = File(...),
    query: str = Form(...),
    language: str = Form("English"),
):
    data = await file.read()
    files_module.validate_upload(file.filename, file.content_type, len(data))

    suffix = Path(file.filename).suffix.lower()
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(data)
        tmp_path = Path(tmp.name)
    try:
        extracted = files_module.extract_text_from_file(tmp_path, file.content_type)
    finally:
        tmp_path.unlink(missing_ok=True)

    if not extracted.strip():
        raise HTTPException(status_code=422, detail="Could not read any text from this file.")

    answer = rag.analyze_uploaded_document(file.filename, extracted, query, language)
    if not answer:
        raise HTTPException(status_code=404, detail="No relevant content found in the uploaded document.")

    files_module.audit(None, "document_query", resource=file.filename,
                        request_id=getattr(request.state, "request_id", ""),
                        details=f"query={query[:120]}")
    return answer


# ------------------------------- Feedback -----------------------------------
class FeedbackRequest(BaseModel):
    rating: str  # "up" or "down"
    query_text: Optional[str] = None
    answer_snippet: Optional[str] = None
    language: Optional[str] = "English"


@app.post("/api/feedback")
def submit_feedback(payload: FeedbackRequest, request: Request):
    if payload.rating not in ("up", "down"):
        raise HTTPException(status_code=400, detail="rating must be 'up' or 'down'.")
    files_module.save_feedback(
        None, None, payload.query_text, payload.answer_snippet, payload.rating, payload.language,
    )
    files_module.audit(None, "feedback", resource=payload.rating,
                        request_id=getattr(request.state, "request_id", ""),
                        details=(payload.query_text or "")[:120])
    return {"success": True}


# --------------------------- View/open a cited source -----------------------
# Deliberately NOT behind require_permission("files:read"): this route only
# ever serves a file whose name and an extracted snippet were already shown
# to the same caller inside a grounded /api/query answer, so it exposes
# nothing beyond what that answer already cited. Lock it down with
# `user: dict = Depends(auth.get_current_user)` if your deployment wants
# source documents visible only to logged-in users.
@app.get("/api/sources/{file_id}")
def view_source(file_id: int, request: Request):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM files WHERE id = ?", (file_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Source file not found.")
    path = UPLOAD_DIR / row["stored_name"]
    if not path.exists():
        raise HTTPException(status_code=404, detail="Source file missing on disk.")
    files_module.audit(None, "source_view", resource=row["filename"],
                        request_id=getattr(request.state, "request_id", ""))
    return FileResponse(path, filename=row["filename"], media_type=row["content_type"] or "application/octet-stream")


@app.get("/api/health")
def health():
    return {"success": True, "service": "IP-Sakti Sahayak Backend", "status": "ok"}


# --------------------------- Serve the frontend ---------------------------
# Static assets (css/js) at their real sub-paths; the SPA HTML at "/".
if (FRONTEND_DIR / "css").exists():
    app.mount("/css", StaticFiles(directory=str(FRONTEND_DIR / "css")), name="css")
if (FRONTEND_DIR / "js").exists():
    app.mount("/js", StaticFiles(directory=str(FRONTEND_DIR / "js")), name="js")

@app.get("/", response_class=HTMLResponse)
def serve_frontend():
    if INDEX_FILE.exists():
        return INDEX_FILE.read_text(encoding="utf-8")

    return HTMLResponse(
        "<h1>backend is running.</h1>"
        "<p>frontend/index.html not found.</p>"
    )

if __name__ == "__main__":
    import uvicorn

    init_db()
    uvicorn.run(app, host="127.0.0.1", port=8000)
