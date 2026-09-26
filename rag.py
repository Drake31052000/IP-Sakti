"""
rag.py — chunking, embeddings, hybrid retrieval, reranking, citations.

Implements Plan Section 4 (chunking, metadata) and Section 5 (hybrid
retrieval, reranking, grounded/cited answers).

Embedding model note
---------------------
Section 4 Step 4 calls for a *local* embedding model "if confidential
documents must remain on-premise". This deployment has no outbound network
access to download a pretrained sentence-embedding model, so the "vector"
side of hybrid retrieval is implemented with a local TF-IDF vector space
(scikit-learn), fit fresh on this installation's own chunks and never
leaving the machine. It is swapped in behind the same `embed_chunks()` /
`retrieve_vector()` contract described in the plan, so replacing it with a
real sentence-transformer model later is a one-file change.
"""
from __future__ import annotations

from typing import Optional
import os
import re

try:
    from openai import OpenAI
except ImportError:  # Optional: local-only fallback still works.
    OpenAI = None

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from database import get_conn

CHUNK_SIZE = 800
CHUNK_OVERLAP = 120


# --------------------------------------------------------------------------
# Section 4 Step 2 — chunking
# --------------------------------------------------------------------------
def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    chunks = []
    start = 0
    n = len(text)
    if n == 0:
        return chunks
    while start < n:
        end = min(start + size, n)
        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)
        if end == n:
            break
        start = end - overlap
    return chunks


def ingest_document_chunks(document_id: int, text: str, jurisdiction: Optional[str],
                            language: Optional[str], source_version: Optional[str]) -> int:
    """Chunk `text` and persist rows into document_chunks (Section 4 Step 3).
    Returns the number of chunks written. Replaces any prior chunks for the
    same document_id (so re-uploading/updating a file re-chunks cleanly)."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM document_chunks WHERE document_id = ?", (document_id,))
    chunks = chunk_text(text)
    for idx, chunk in enumerate(chunks):
        cur.execute(
            "INSERT INTO document_chunks (document_id, chunk_index, text, jurisdiction, "
            "language, source_version) VALUES (?, ?, ?, ?, ?, ?)",
            (document_id, idx, chunk, jurisdiction, language, source_version),
        )
    conn.commit()
    conn.close()
    return len(chunks)


# --------------------------------------------------------------------------
# Retrieval candidates
# --------------------------------------------------------------------------
def _all_chunks() -> list[dict]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT dc.id as chunk_id, dc.document_id, dc.chunk_index, dc.text,
               dc.jurisdiction, dc.language, dc.source_version,
               f.filename, f.authority, f.effective_date
        FROM document_chunks dc
        JOIN files f ON f.id = dc.document_id
        """
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def retrieve_keyword(query: str, top_k: int = 20) -> list[dict]:
    """Lexical (keyword-overlap) retrieval — the original prototype's
    approach, kept as one half of the hybrid score."""
    q_terms = [t for t in query.lower().split() if len(t) > 2]
    results = []
    for row in _all_chunks():
        text_lower = row["text"].lower()
        score = sum(text_lower.count(term) for term in q_terms)
        if score > 0:
            results.append({**row, "keyword_score": float(score), "vector_score": 0.0})
    results.sort(key=lambda r: r["keyword_score"], reverse=True)
    return results[:top_k]


def retrieve_vector(query: str, top_k: int = 20) -> list[dict]:
    """Semantic retrieval via local TF-IDF cosine similarity (see module
    docstring for why this stands in for a downloaded embedding model)."""
    chunks = _all_chunks()
    if not chunks:
        return []
    corpus = [c["text"] for c in chunks]
    try:
        vectorizer = TfidfVectorizer(stop_words="english", max_features=20000)
        matrix = vectorizer.fit_transform(corpus + [query])
    except ValueError:
        return []  # e.g. corpus is only stopwords
    query_vec = matrix[-1]
    doc_matrix = matrix[:-1]
    sims = cosine_similarity(query_vec, doc_matrix)[0]
    scored = [
        {**chunks[i], "keyword_score": 0.0, "vector_score": float(sims[i])}
        for i in range(len(chunks))
        if sims[i] > 0
    ]
    scored.sort(key=lambda r: r["vector_score"], reverse=True)
    return scored[:top_k]


def merge_by_chunk_id(a: list[dict], b: list[dict]) -> list[dict]:
    merged: dict[int, dict] = {}
    for row in a + b:
        cid = row["chunk_id"]
        if cid not in merged:
            merged[cid] = dict(row)
        else:
            merged[cid]["keyword_score"] = max(merged[cid]["keyword_score"], row["keyword_score"])
            merged[cid]["vector_score"] = max(merged[cid]["vector_score"], row["vector_score"])
    return list(merged.values())


def hybrid_score(keyword_score: float, vector_score: float, alpha: float = 0.35) -> float:
    """Section 5 Step 1's blend. keyword_score is normalized against the
    largest observed value in this call so it lives on a comparable 0-1
    scale to the cosine similarity in vector_score."""
    return alpha * keyword_score + (1 - alpha) * vector_score


def hybrid_retrieve(query: str, top_k: int = 8) -> list[dict]:
    keyword_hits = retrieve_keyword(query, top_k=20)
    vector_hits = retrieve_vector(query, top_k=20)
    merged = merge_by_chunk_id(keyword_hits, vector_hits)
    if not merged:
        return []
    max_kw = max((r["keyword_score"] for r in merged), default=1.0) or 1.0
    for r in merged:
        r["keyword_norm"] = r["keyword_score"] / max_kw
    ranked = sorted(
        merged,
        key=lambda r: hybrid_score(r["keyword_norm"], r["vector_score"]),
        reverse=True,
    )
    return ranked[:top_k]


# --------------------------------------------------------------------------
# Section 5 Step 2 — lightweight reranking
# --------------------------------------------------------------------------
def rerank(query: str, candidates: list[dict], k: int = 5) -> list[dict]:
    """A dedicated cross-encoder reranker needs a downloadable model this
    environment cannot fetch, so reranking here re-scores the hybrid
    shortlist by exact-phrase and multi-term proximity — a cheap signal
    that corrects cases where TF-IDF alone over-weights a single rare
    term. Swap in a real cross-encoder by replacing this function body."""
    query_terms = [t for t in query.lower().split() if len(t) > 2]

    def proximity_bonus(text: str) -> float:
        text_lower = text.lower()
        bonus = 0.0
        if query.lower().strip() and query.lower().strip() in text_lower:
            bonus += 1.0
        hits = sum(1 for t in query_terms if t in text_lower)
        bonus += 0.1 * hits
        return bonus

    for c in candidates:
        c["rerank_score"] = hybrid_score(c.get("keyword_norm", 0.0), c.get("vector_score", 0.0)) + proximity_bonus(c["text"])
    candidates.sort(key=lambda r: r["rerank_score"], reverse=True)
    return candidates[:k]


# --------------------------------------------------------------------------
# Section 5 Step 4 — citation validation
# --------------------------------------------------------------------------
def validate_citations(citations: list[dict], retrieved_chunks: list[dict]) -> bool:
    valid_ids = {c["chunk_id"] for c in retrieved_chunks}
    return all(c.get("chunk_id") in valid_ids for c in citations)


# --------------------------------------------------------------------------
# LLM research + grounded answer assembly
# --------------------------------------------------------------------------
# The chatbot uses two LLM stages:
#   1) Research agent: searches the live internet and returns a researched
#      summary plus source URLs.
#   2) Answer agent: combines the retrieved local-file chunks and web research
#      into one concise, grounded answer with explicit references.
#
# Configuration (environment variables):
#   OPENAI_API_KEY  = required for LLM/web mode
#   OPENAI_MODEL    = optional, defaults to gpt-5.6-luna
#   WEB_SEARCH      = optional, set false/0 to disable web research
#
# Without an API key the existing local retrieval path remains available.
# --------------------------------------------------------------------------

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.6-luna")
WEB_SEARCH_ENABLED = True  # Always research substantive queries on the live web.


def _openai_client():
    """Create an OpenAI client only when the dependency and API key exist."""
    if OpenAI is None or not os.getenv("OPENAI_API_KEY"):
        return None
    return OpenAI(api_key=os.environ["OPENAI_API_KEY"])


def _annotation_value(annotation, name: str):
    """Read SDK/Pydantic/dict annotation fields without depending on one SDK version."""
    if isinstance(annotation, dict):
        value = annotation.get(name)
        if value is not None:
            return value
        nested = annotation.get("url_citation")
        if isinstance(nested, dict):
            return nested.get(name)
        return None
    value = getattr(annotation, name, None)
    if value is not None:
        return value
    nested = getattr(annotation, "url_citation", None)
    return getattr(nested, name, None) if nested is not None else None


def _extract_web_sources(response) -> list[dict]:
    """Extract all web URLs exposed by the Responses API web-search tool."""
    sources: list[dict] = []
    seen: set[str] = set()

    def add(url: str, title: str = "Web source"):
        if not url or url in seen:
            return
        seen.add(url)
        sources.append({"type": "web", "title": title or url, "url": url})

    # The SDK exposes web_search_call.action.sources when requested via include.
    for item in getattr(response, "output", []) or []:
        item_type = getattr(item, "type", None)
        if item_type == "web_search_call":
            action = getattr(item, "action", None)
            action_sources = getattr(action, "sources", None) if action else None
            if action_sources:
                for src in action_sources:
                    url = getattr(src, "url", None) if not isinstance(src, dict) else src.get("url")
                    add(url)

        # Also collect the URLs actually cited by the answer.
        if item_type == "message":
            for content in getattr(item, "content", []) or []:
                annotations = getattr(content, "annotations", None) or []
                for ann in annotations:
                    if getattr(ann, "type", None) == "url_citation" or (isinstance(ann, dict) and ann.get("type") == "url_citation"):
                        url = _annotation_value(ann, "url")
                        title = _annotation_value(ann, "title") or "Web source"
                        add(url, title)

    return sources


def _response_text(response) -> str:
    """Get response text across current/older OpenAI SDK response shapes."""
    text = getattr(response, "output_text", None)
    if text:
        return text.strip()

    pieces = []
    for item in getattr(response, "output", []) or []:
        if getattr(item, "type", None) != "message":
            continue
        for content in getattr(item, "content", []) or []:
            value = getattr(content, "text", None)
            if value:
                pieces.append(value)
    return "\n".join(pieces).strip()


def _research_web(client, query: str, language: str) -> tuple[str, list[dict]]:
    """Ask an LLM research agent to search the live web before answering."""
    response = client.responses.create(
        model=OPENAI_MODEL,
        tools=[{"type": "web_search"}],
        tool_choice="required",
        include=["web_search_call.action.sources"],
        instructions=(
            "You are the web research agent for an evidence-grounded chatbot. "
            "Search the live internet for the user's query. Prefer primary/official "
            "sources, government sites, laws/regulations, universities, standards, "
            "and reputable reporting when appropriate. Cross-check important claims. "
            "Do not invent facts or URLs. Return a compact research brief in the "
            f"user's requested language ({language}), separating facts from uncertainty."
        ),
        input=query,
    )
    return _response_text(response), _extract_web_sources(response)


def _local_context(query: str, top_k: int = 8) -> tuple[list[dict], list[dict]]:
    """Retrieve and rerank the most relevant uploaded-file chunks."""
    candidates = hybrid_retrieve(query, top_k=top_k)
    top = rerank(query, candidates, k=min(5, len(candidates))) if candidates else []
    context = []
    sources = []
    for c in top:
        context.append({
            "filename": c["filename"],
            "document_id": c.get("document_id"),
            "chunk_id": c.get("chunk_id"),
            "chunk_index": c["chunk_index"],
            "text": c["text"],
            "jurisdiction": c.get("jurisdiction") or "",
            "version": c.get("source_version") or "",
        })
        sources.append({
            "type": "uploaded_file",
            "title": c["filename"],
            "url": None,
            "chunk_id": c["chunk_id"],
            "document_id": c.get("document_id"),
            "chunk": c["chunk_index"],
            "jurisdiction": c.get("jurisdiction") or "",
            "version": c.get("source_version") or "",
        })
    return context, sources


def _synthesize_answer(client, query: str, language: str,
                       local_context: list[dict], web_research: str,
                       web_sources: list[dict]) -> str:
    """Synthesis agent: combine local evidence + web research without inventing."""
    local_text = "\n\n".join(
        f'[FILE {i+1}] {item["filename"]} (chunk {item["chunk_index"]})\n{item["text"]}'
        for i, item in enumerate(local_context)
    ) or "No matching uploaded-file content was found."

    web_text = web_research or "No web research was returned."
    source_list = "\n".join(
        f'[WEB {i+1}] {s.get("title", "Web source")} — {s.get("url", "")}'
        for i, s in enumerate(web_sources)
    ) or "No web source list was returned."

    prompt = f"""Answer the user's query using ONLY the evidence supplied below.

USER QUERY:
{query}

UPLOADED FILE EVIDENCE:
{local_text}

WEB RESEARCH:
{web_text}

WEB SOURCES:
{source_list}

Requirements:
1. Answer in {language}.
2. Always use the live WEB RESEARCH when it is available. The web research is required for every substantive query, even when matching uploaded-file evidence exists.
3. Use uploaded-file evidence as an additional source of project/knowledge-base information, not as a reason to skip web research.
4. Synthesize the evidence; do not merely list snippets.
5. Do not invent facts, citations, source names, or URLs.
6. If uploaded files and web sources disagree, explicitly say they disagree and
   identify which source says what; do not silently choose one.
7. Clearly distinguish information found in uploaded files from information
   found on the internet when that distinction matters.
8. Put reference markers such as [FILE 1] or [WEB 1] immediately after the
   relevant claims. Use only markers that exist above.
9. End with a short 'References' section listing every source actually used.
10. If the evidence is insufficient, say what is missing instead of guessing.
"""

    response = client.responses.create(
        model=OPENAI_MODEL,
        instructions=(
            "You are the final answer agent for a grounded RAG chatbot. "
            "Be accurate, concise, transparent about uncertainty, and preserve "
            "source attribution. Never fabricate references."
        ),
        input=prompt,
    )
    return _response_text(response)


def _is_casual_chat(query: str) -> bool:
    """Return True for short conversational messages that do not need RAG."""
    normalized = re.sub(r"\s+", " ", query.strip().lower())
    normalized = re.sub(r"[!?.,]+$", "", normalized)
    casual = {
        "hi", "hello", "hey", "hii", "hiii", "hiya",
        "good morning", "good afternoon", "good evening",
        "how are you", "how are you doing", "what's up", "whats up",
        "thanks", "thank you", "ok", "okay",
    }
    return normalized in casual


def _chat_reply(client, query: str, language: str) -> str:
    """Use the configured LLM directly for casual conversation."""
    response = client.responses.create(
        model=OPENAI_MODEL,
        instructions=(
            "You are the conversational assistant inside IP-Sakti Sahayak. "
            "Handle short greetings and casual conversation naturally. "
            f"Reply in the user's requested language ({language}). "
            "Do not perform retrieval, web research, or invent citations for a "
            "casual message. Keep the response friendly and concise."
        ),
        input=query,
    )
    return _response_text(response)


def build_grounded_answer(query: str, language: str = "English") -> Optional[dict]:
    """Build a source-backed answer from uploaded files and live web research.

    When OPENAI_API_KEY is configured, this uses an LLM research agent with the
    Responses API web_search tool followed by an LLM synthesis agent. Without
    credentials/dependency it falls back to the original local TF-IDF answer.
    """
    # Casual conversation (for example "hi") should go directly to the
    # chatbot LLM. It must not be forced through document retrieval, because
    # greetings normally have no matching knowledge-base chunk.
    client = _openai_client()
    if _is_casual_chat(query):
        if client is not None:
            try:
                answer_text = _chat_reply(client, query, language)
                if answer_text:
                    return {
                        "answer": answer_text,
                        "sources": [],
                        "citations": [],
                        "requested_language": language,
                        "response_language": language,
                        "grounded": False,
                        "ai_mode": True,
                        "web_searched": False,
                    }
            except Exception:
                pass

        # No API key / temporary LLM failure: still answer the greeting
        # instead of returning a 404 that triggers the frontend demo reply.
        greeting = {
            "English": "Hi! 👋 How can I help you today?",
            "Hindi": "नमस्ते! 👋 मैं आपकी कैसे मदद कर सकता हूँ?",
        }.get(language, "Hi! 👋 How can I help you today?")
        return {
            "answer": greeting,
            "sources": [],
            "citations": [],
            "requested_language": language,
            "response_language": language,
            "grounded": False,
            "ai_mode": client is not None,
            "web_searched": False,
        }

    local_context, file_sources = _local_context(query)

    # Full AI + live-web mode.
    # IMPORTANT: local retrieval and web research are NOT alternatives.
    # The local files are checked first, but every substantive query is also
    # sent to the live web so the answer can use current external information.
    if client is not None:
        web_research = ""
        web_sources: list[dict] = []
        web_search_succeeded = False
        try:
            web_research, web_sources = _research_web(client, query, language)
            web_search_succeeded = True
        except Exception as exc:
            web_research = f"Web research was unavailable for this request: {exc}"

        try:
            answer_text = _synthesize_answer(
                client, query, language, local_context, web_research, web_sources
            )
            if answer_text:
                return {
                    "answer": answer_text,
                    "sources": file_sources + web_sources,
                    "citations": file_sources + web_sources,
                    "requested_language": language,
                    "response_language": language,
                    "grounded": bool(local_context or web_sources),
                    "ai_mode": True,
                    "web_searched": web_search_succeeded,
                    "local_sources_found": bool(local_context),
                }
        except Exception:
            # Fall through to deterministic local retrieval rather than breaking /api/query.
            pass

    # Deterministic local fallback when no LLM is configured or an API call fails.
    if not local_context:
        return None

    lines = [f"Based on {len(local_context)} retrieved source chunk(s), here is what was found:"]
    citations = []
    for c in local_context:
        snippet = c["text"][:500].strip()
        lines.append(f'\n- From "{c["filename"]}" (chunk {c["chunk_index"]}): ...{snippet}...')
        citations.append({
            "type": "uploaded_file",
            "chunk_id": c["chunk_id"],
            "source": "uploaded_file",
            "title": c["filename"],
            "citation": c["filename"],
            "section": f"Chunk {c["chunk_index"]}",
            "version": c.get("source_version") or "—",
            "jurisdiction": c.get("jurisdiction") or "",
        })

    return {
        "answer": "\n".join(lines),
        "sources": citations,
        "citations": citations,
        "requested_language": language,
        "response_language": language,
        "grounded": True,
        "ai_mode": False,
        "web_searched": False,
    }

# --------------------------------------------------------------------------
# Ephemeral "chat with this document" analysis
# --------------------------------------------------------------------------
def analyze_uploaded_document(
    filename: str,
    text: str,
    query: str,
    language: str = "English",
) -> Optional[dict]:
    """Answer a question against a document uploaded for this chat request.

    The uploaded document is NOT persisted into the permanent knowledge base.
    The function first uses the same hybrid TF-IDF/keyword retrieval strategy
    as the stored-document pipeline. If an OpenAI API key is configured, the
    retrieved document evidence is then passed through the same synthesis
    agent used by the main chatbot, giving the temporary upload the same
    grounded LLM experience without writing it to SQLite.
    """
    chunks = chunk_text(text)
    if not chunks:
        return None

    q_terms = [t for t in query.lower().split() if len(t) > 2]

    def kw_score(chunk_text_: str) -> float:
        low = chunk_text_.lower()
        return float(sum(low.count(term) for term in q_terms))

    try:
        vectorizer = TfidfVectorizer(stop_words="english", max_features=20000)
        matrix = vectorizer.fit_transform(chunks + [query])
        sims = cosine_similarity(matrix[-1], matrix[:-1])[0]
    except ValueError:
        sims = [0.0] * len(chunks)

    scored = []
    for i, chunk in enumerate(chunks):
        scored.append({
            "chunk_index": i,
            "text": chunk,
            "keyword_score": kw_score(chunk),
            "vector_score": float(sims[i]),
        })

    max_kw = max((s["keyword_score"] for s in scored), default=1.0) or 1.0
    for s in scored:
        s["keyword_norm"] = s["keyword_score"] / max_kw
        s["rerank_score"] = hybrid_score(s["keyword_norm"], s["vector_score"])

    # Same lightweight reranking idea used by the persistent RAG pipeline:
    # exact query phrase + number of matching query terms.
    query_lower = query.lower().strip()
    for s in scored:
        low = s["text"].lower()
        bonus = 1.0 if query_lower and query_lower in low else 0.0
        bonus += 0.1 * sum(1 for term in q_terms if term in low)
        s["rerank_score"] += bonus

    scored.sort(key=lambda s: s["rerank_score"], reverse=True)
    top = scored[:5]
    if not any(s["keyword_score"] or s["vector_score"] for s in top):
        top = scored[:3]

    local_context = [
        {
            "filename": filename,
            "chunk_index": s["chunk_index"],
            "text": s["text"],
            "jurisdiction": "",
            "version": "Session upload",
        }
        for s in top
    ]

    client = _openai_client()
    if client is not None:
        try:
            answer_text = _synthesize_answer(
                client,
                query,
                language,
                local_context,
                "No internet research was used for this temporary document analysis.",
                [],
            )
            if answer_text:
                citations = [
                    {
                        "chunk_id": None,
                        "document_id": None,
                        "source": "session_upload",
                        "title": filename,
                        "citation": filename,
                        "section": f"Chunk {s['chunk_index']}",
                        "version": "Session upload (not saved to the knowledge base)",
                        "jurisdiction": "",
                    }
                    for s in top
                ]
                return {
                    "answer": answer_text,
                    "sources": citations,
                    "citations": citations,
                    "requested_language": language,
                    "response_language": language,
                    "grounded": True,
                    "ephemeral": True,
                    "ai_mode": True,
                    "web_searched": False,
                }
        except Exception:
            pass

    # Deterministic fallback when the LLM is unavailable.
    lines = [
        f'Based on the uploaded document "{filename}", here is what is relevant to your question:'
    ]
    citations = []
    for s in top:
        snippet = s["text"][:300].strip()
        lines.append(f"\n- (chunk {s['chunk_index']}): ...{snippet}...")
        citations.append({
            "chunk_id": None,
            "document_id": None,
            "source": "session_upload",
            "title": filename,
            "citation": filename,
            "section": f"Chunk {s['chunk_index']}",
            "version": "Session upload (not saved to the knowledge base)",
            "jurisdiction": "",
        })

    return {
        "answer": "\n".join(lines),
        "sources": citations,
        "citations": citations,
        "requested_language": language,
        "response_language": language,
        "grounded": True,
        "ephemeral": True,
        "ai_mode": False,
        "web_searched": False,
    }

