"""RAG service boundary.

Replace the demo retrieval below with FAISS/Chroma/pgvector + embeddings
and a validated LLM provider as the project grows.
"""

def answer_query(query: str, jurisdiction: str, language: str) -> dict:
    scope = "India" if jurisdiction.lower() == "india" else "International"
    answer = (
        f"Demo response for {scope} jurisdiction. "
        f"Your question was: {query}\n\n"
        "The RAG pipeline is ready to be connected to a curated corpus "
        "of IP statutes, Ayurveda regulations, treaties, standards and "
        "other authoritative sources."
    )

    return {
        "answer": answer,
        "language": language,
        "jurisdiction": jurisdiction,
        "sources": [
            "Demo source — replace with verified primary legal/regulatory documents.",
        ],
        "confidence": 0.0,
        "mode": "demo",
    }
