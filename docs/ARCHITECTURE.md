# IP-SAKTI Architecture

## Phase 1 — Working MVP
Browser UI → FastAPI → RAG engine → answer + citations.

## Phase 2 — Advanced RAG
1. Parse trusted documents.
2. Chunk by legal section rather than arbitrary length.
3. Create multilingual embeddings.
4. Store vectors in FAISS, Chroma or pgvector.
5. Retrieve with hybrid keyword + vector search.
6. Rerank retrieved passages.
7. Generate answers only from retrieved evidence.
8. Return source, section/page and confidence metadata.

## Phase 3 — Knowledge Graph
Connect entities such as:
- formulation
- medicinal plant
- traditional knowledge
- patent
- trademark
- geographical indication
- regulation
- authority
- treaty

## Phase 4 — Agentic orchestration
A router can select IP, regulatory, ABS, prior-art or multilingual workflows. Each agent should retain citations and provenance.

## Phase 5 — Production
Add authentication, authorization, rate limiting, secure secrets, audit logs, monitoring, privacy controls, tests and source/version governance.
