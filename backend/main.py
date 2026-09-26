from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from rag_engine import answer_query

app = FastAPI(
    title="IP-SAKTI SAHAYAK API",
    version="0.1.0",
    description="RAG-ready IP and Ayurveda regulatory guidance API",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict this in production.
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class QueryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=5000)
    jurisdiction: str = "india"
    language: str = "English"

@app.get("/health")
def health():
    return {"status": "ok", "service": "IP-SAKTI SAHAYAK"}

@app.post("/api/query")
def query_api(request: QueryRequest):
    return answer_query(
        request.query,
        request.jurisdiction,
        request.language,
    )
