# IP-SAKTI SAHAYAK

AI-Powered Intellectual Property & Regulatory Guidance for Ayurveda.

## Structure
- `frontend/` — browser interface
- `backend/` — FastAPI API and RAG-ready engine
- `data/` — documents and knowledge-base instructions
- `docs/` — architecture and implementation notes

## Run
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
```

Open `frontend/index.html` in a browser.

API: http://127.0.0.1:8000
Health: http://127.0.0.1:8000/health

This is an informational system, not legal advice. Production use requires validated sources, authentication, secure secrets, audit logging, and legal review.
