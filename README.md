# IP-SAKTI SAHAYAK
## AI-Powered Intellectual Property & Regulatory Guidance for Ayurveda

**Smart India Hackathon 2026 — PS 26045**  
**Ministry of Ayush | All India Institute of Ayurveda | Software**

IP-SAKTI SAHAYAK is a multilingual, source-grounded RAG platform for Ayurveda-focused intellectual-property and regulatory guidance. It is designed for researchers, practitioners, innovators, startups/MSMEs, students, cultivators and IP professionals.

> **Important:** This is an information and research assistant, not legal advice. Production use requires authoritative-source validation, professional review, security testing, privacy controls and continuous corpus maintenance.

---

## 1. SIH 2026 Problem Statement — PS 26045

**Title:** *IP-SAKTI Sahayak — a multilingual, RAG-based (source-cited) AI assistant for Intellectual Property and regulatory guidance in Ayurveda, across national and international regimes.*

**Organization:** Ministry of Ayush  
**Department:** All India Institute of Ayurveda  
**Category:** Software

### Problem background

Ayurveda combines codified classical knowledge, community-held traditional knowledge and products derived from biological resources. Protecting and commercialising an Ayurvedic formulation or innovation can require decisions across patents, geographical indications, trademarks, copyright, designs, trade secrets, plant-related rights, biodiversity/Access and Benefit Sharing (ABS), traditional knowledge, prior art and product regulation.

The central difficulty is that information is distributed across statutes, rules, standards, treaties, registries, notifications and other authoritative sources. Product classification also matters: an Ayurveda product may fall into different regulatory categories, each with different implications. National and international requirements can also differ.

### Core problem

The required assistant should help users:

1. Understand an Ayurveda/IP question.
2. Identify relevant formulation/product context.
3. Route the question across IP and regulatory domains.
4. Keep **India** and **International** guidance separate.
5. Retrieve current, versioned evidence.
6. Produce plain-language answers grounded in that evidence.
7. Show supporting sources and confidence/evidence information.
8. Abstain when evidence is insufficient.
9. Provide multilingual access.
10. Provide a path to human IP facilitation.
11. Apply privacy, security and audit controls.

### Expected solution

The project architecture therefore provides for:

- Curated, version-tracked statutes, rules, treaties, standards, registries and case/reference material.
- RAG retrieval with mandatory source citations.
- India/International jurisdiction switching.
- IP-type routing plus formulation classification.
- ABS-compliance assistance.
- TKDL/traditional-knowledge/prior-art pointers where legally and technically available.
- Confidence/evidence indicators.
- Safe abstention.
- Human facilitator escalation.
- Multilingual delivery, including future national-language and voice layers.
- Privacy, audit and security guardrails.
- A staged path from citation-grounded RAG to knowledge graph and agentic multi-source reasoning.

---

## 2. Why the problem matters

An Ayurveda innovator may need to answer several connected questions at once:

> What is my formulation? How is it regulated? Which IP route may be relevant? Are biological-resource/ABS considerations involved? What changes if I operate outside India?

This is a **multi-domain evidence and reasoning problem**, not merely generic chatbot Q&A.

The project workflow is:

**Question → Classification → Retrieval → Evidence validation → Jurisdiction-aware reasoning → Cited answer → Confidence/abstention → Human escalation**

---

## 3. Core challenges

### Fragmented information
Relevant evidence can be distributed across IP databases, statutes, Ayurveda standards, biodiversity sources, traditional-knowledge resources, international treaties, registries and notifications.

### Product classification
IP guidance cannot be separated from how the underlying Ayurveda formulation/product is regulated.

### Jurisdiction separation
Indian requirements must not be silently mixed with requirements from other countries or international systems.

### Hallucination and stale-law risk
An LLM can produce plausible but unsupported legal claims or outdated provisions. Retrieval, source metadata and validation are therefore central.

### Multilingual access
Translation must preserve technical meaning, citations and source references.

### Safe boundaries
The system should not impersonate a lawyer or regulator. Unsupported or high-risk questions should trigger an appropriate limitation and escalation path.

---

## 4. Proposed solution

### User layer
- Login/register
- Language selection
- Text and future voice input
- India/International switch
- Query interface
- Answer, sources and confidence display
- Human-assistance path

### Intelligence layer
- Query classification
- Formulation/product classification
- IP-domain routing
- Jurisdiction routing
- Hybrid retrieval
- Reranking
- Evidence pack creation
- Grounded generation
- Citation validation
- Safe abstention

### Knowledge layer
- Versioned documents
- Source authority
- Jurisdiction
- Effective date/version
- Section/article/rule
- Language
- Source URL/reference
- Content hash
- Access/licensing metadata

---

## 5. End-to-end workflow

~~~mermaid
flowchart TD
 A[User] --> B[Language + Jurisdiction]
 B --> C[Question / Voice]
 C --> D[Query Understanding]
 D --> E[Formulation Classification]
 E --> F[IP + Regulatory Routing]
 F --> G[Hybrid Retrieval]
 G --> H[Evidence + Re-ranking]
 H --> I{Enough evidence?}
 I -->|Yes| J[Grounded Reasoning]
 J --> K[Citation + Safety Validation]
 K --> L[Localized Answer + Sources + Confidence]
 I -->|No| M[Safe Abstention]
 M --> N[More Information / Human Facilitator]
 L --> N
~~~

---

## 6. Architecture

~~~mermaid
flowchart TB
 UI[Web Interface] --> API[FastAPI]
 API --> AUTH[Authentication / RBAC]
 API --> ROUTER[Query Router]
 ROUTER --> CLASS[Formulation Classifier]
 ROUTER --> IP[IP Type Router]
 ROUTER --> JURIS[Jurisdiction Router]
 CLASS --> RET[Hybrid Retrieval]
 IP --> RET
 JURIS --> RET
 RET --> VEC[(Vector Store)]
 RET --> META[(Metadata DB)]
 RET --> KG[(Knowledge Graph)]
 VEC --> EVID[Evidence Layer]
 META --> EVID
 KG --> EVID
 EVID --> LLM[Reasoning / LLM]
 LLM --> VAL[Citation + Safety Validator]
 VAL --> OUT[Answer + Sources + Confidence]
 VAL --> ABST[Safe Abstention]
 ABST --> HUMAN[Human IP Facilitator]
 OUT --> UI
~~~

---

## 7. RAG pipeline

~~~mermaid
flowchart LR
 S[Authoritative Sources] --> ING[Ingestion]
 ING --> PROC[PDF/HTML/OCR Processing]
 PROC --> CHUNK[Cleaning + Chunking]
 CHUNK --> META[Metadata]
 META --> EMB[Embeddings]
 EMB --> VDB[(Vector DB)]
 META --> MDB[(Metadata DB)]
 Q[User Query] --> REWRITE[Query Rewrite]
 REWRITE --> RET[Hybrid Retrieval]
 VDB --> RET
 MDB --> RET
 RET --> RERANK[Reranking]
 RERANK --> PACK[Evidence Pack]
 PACK --> GEN[Grounded Generation]
 GEN --> CHECK[Citation Validator]
 CHECK --> ANSWER[Final Answer]
~~~

### Important metadata

Each source record should ideally contain:

- Source ID
- Document title
- Authority
- Jurisdiction
- Domain
- Document type
- Effective date
- Version
- Section/article/rule
- URL/reference
- Retrieval timestamp
- Content hash
- Language
- Access restrictions
- Confidence/trust class

---

## 8. Differentiation from existing solutions

The differentiation is the **combination and orchestration** of domain-specific capabilities, rather than a claim that no other system has any individual feature.

| Capability | Generic assistant | IP-SAKTI design |
|---|---|---|
| Ayurveda-specific IP context | General | Core |
| Source-grounded RAG | Variable | Core |
| Version-aware corpus | Often absent | Core requirement |
| India vs International | May mix | Explicit separation |
| Formulation classification | Usually absent | Dedicated route |
| IP-type routing | General | Dedicated |
| ABS helper | Usually absent | Dedicated |
| TK/prior-art pointer | Usually absent | Dedicated |
| Citation visibility | Variable | Required |
| Confidence/evidence signal | Variable | Required |
| Safe abstention | Variable | Required |
| Human escalation | Usually absent | Planned workflow |
| Multilingual UI/query/answer | Variable | Core direction |
| Knowledge graph | Uncommon | Roadmap |
| Agentic multi-source orchestration | Uncommon | Roadmap |

---

## 9. Core innovation

### 1. Evidence-first AI
The answer is treated as an evidence-backed product, not free-form text.

### 2. Formulation-to-IP reasoning
The system first understands the product/formulation context before routing IP/regulatory guidance.

### 3. Jurisdiction-aware reasoning
India and international evidence are intentionally separated.

### 4. Citation-aware generation
Production answers should be traceable to retrieved evidence.

### 5. Safe abstention
Insufficient evidence should result in abstention rather than invented authority.

### 6. Human-in-the-loop
AI supports research and triage while important decisions remain reviewable by qualified people.

### 7. Knowledge graph roadmap
Formulations, ingredients, biological resources, IP rights, regulations, jurisdictions and sources can become linked entities.

---

## 10. Knowledge domains

~~~text
IP-SAKTI Knowledge Layer
├── Intellectual Property
│   ├── Patents
│   ├── Trademarks
│   ├── GI
│   ├── Copyright
│   ├── Designs
│   ├── Trade Secrets
│   └── Plant-related rights
├── Ayurveda / Product Regulation
│   ├── Classical formulations
│   ├── Proprietary / non-classical products
│   ├── New-drug considerations
│   ├── Phytopharmaceuticals
│   ├── Food / nutraceutical
│   └── Cosmetics
├── Biodiversity / ABS
├── Traditional Knowledge / TKDL pointers
├── India: Acts / Rules / Notifications / Registries
└── International: Treaties / Filing Systems / Jurisdictions
~~~

---

## 11. User journey

~~~mermaid
sequenceDiagram
 participant U as User
 participant UI as UI
 participant API as FastAPI
 participant R as Retrieval
 participant V as Validator
 participant L as LLM
 U->>UI: Select language
 U->>UI: Select jurisdiction
 U->>UI: Ask question
 UI->>API: Structured request
 API->>R: Retrieve evidence
 R-->>API: Ranked evidence
 API->>L: Evidence-grounded prompt
 L-->>V: Draft + citations
 V->>V: Validate evidence
 V-->>API: Answer or Abstain
 API-->>UI: Localized result
 UI-->>U: Answer + sources + confidence
~~~

---

## 12. Long-term impact

**Researchers:** faster first-level discovery of relevant IP/regulatory information.

**Startups and MSMEs:** reduced information barriers during product development and commercialisation.

**Practitioners:** easier access to structured explanations.

**Traditional-knowledge stakeholders:** improved visibility of traditional-knowledge and prior-art considerations.

**IP professionals:** structured research and triage support.

**Institutions:** maintainable, versioned knowledge infrastructure.

~~~mermaid
flowchart LR
 TK[Traditional Knowledge] --> KNOW[Trusted Knowledge Layer]
 RES[Research] --> KNOW
 REG[Regulations + IP Records] --> KNOW
 KNOW --> AI[IP-SAKTI Intelligence]
 AI --> R[Researchers]
 AI --> I[Innovators]
 AI --> S[Startups/MSMEs]
 AI --> P[Practitioners]
 AI --> IP[IP Professionals]
 R --> IMP[Responsible Innovation]
 I --> IMP
 S --> IMP
 P --> IMP
 IP --> IMP
~~~

---

## 13. Technology stack

### Current repository
- HTML / CSS / JavaScript
- Python
- FastAPI
- Pydantic
- Uvicorn
- Modular frontend JavaScript
- Replaceable RAG service boundary

### Planned production stack
- PostgreSQL
- pgvector / Chroma / FAISS
- Multilingual embeddings
- Reranking
- OCR/document processing
- Validated LLM/local model
- Knowledge graph
- Authentication/RBAC
- Audit logging
- Secret management
- Evaluation harness
- Monitoring

---

## 14. Repository structure

~~~text
IP-Sakti/
├── frontend/
│   ├── index.html
│   ├── ip-sakti.html
│   ├── css/
│   └── js/
├── backend/
│   ├── main.py
│   ├── rag_engine.py
│   └── requirements.txt
├── data/
├── docs/
├── tests/
├── .gitignore
├── SECURITY.md
└── README.md
~~~

Generated indexes, private uploads, local databases, environments and secrets must remain outside version control.

---

## 15. Local setup

### Backend

~~~powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --reload --host 127.0.0.1 --port 8001
~~~

Backend: http://127.0.0.1:8001  
Health: http://127.0.0.1:8001/health

### Frontend

~~~powershell
cd frontend
python -m http.server 5500
~~~

Open: http://127.0.0.1:5500

---

## 16. Security and sensitive files

Never commit:

- .env and production configuration
- API keys, tokens or passwords
- Private keys/certificates
- Database credentials
- Real authentication data
- Personal or confidential documents
- Restricted/proprietary datasets
- Local vector indexes
- Local database files
- Logs containing personal information
- Browser/session credentials
- Virtual environments

Use environment variables or a secret manager.

~~~env
LLM_API_KEY=replace_me
DATABASE_URL=replace_me
JWT_SECRET=replace_me
~~~

The real .env remains local.

See [SECURITY.md](SECURITY.md).

---

## 17. Privacy-by-design

1. Collect only necessary user data.
2. Avoid retaining sensitive queries unless required.
3. Separate authentication data from query/knowledge data.
4. Encrypt sensitive data.
5. Apply access controls and audit logs.
6. Define retention/deletion rules.
7. Use synthetic/de-identified development data.
8. Never expose secrets in browser code.
9. Validate source licensing before ingestion.
10. Review privacy and security before production deployment.

---

## 18. Evaluation

### Retrieval
- Recall@k
- Precision@k
- Source relevance
- Version correctness

### Answer
- Factual correctness
- Completeness
- Groundedness
- Citation correctness

### Safety
- Abstention accuracy
- Out-of-scope detection
- Unsupported-claim rate
- Hallucination rate

### Multilingual
- Translation accuracy
- Technical terminology preservation
- Citation preservation
- UI consistency

### Performance
- Query latency
- Retrieval latency
- Concurrent-user handling
- Index update time

---

## 19. Roadmap

~~~mermaid
flowchart LR
 A[MVP: Citation-grounded RAG] --> B[Advanced RAG]
 B --> C[Knowledge Graph]
 C --> D[Agentic Orchestration]
 D --> E[Multilingual + Voice]
 E --> F[Production Connectors]
 F --> G[Institutional Deployment]
~~~

### Phase 1
Curated corpus, retrieval, citations, confidence and abstention.

### Phase 2
Hybrid search, metadata filters, query rewriting, reranking, parent-document retrieval and version validation.

### Phase 3
Entity extraction and a regulatory/IP/formulation knowledge graph.

### Phase 4
Specialised agents for IP research, formulation classification, ABS, TK/prior art, international comparison and citation verification.

### Phase 5
Indian-language retrieval/UI, translation, speech-to-text and text-to-speech.

### Phase 6
Secure authentication, RBAC, audit logs, monitoring, source update pipelines and human-facilitator workflows.

---

## 20. Current prototype status

The repository currently provides a lightweight frontend/backend foundation and a replaceable RAG boundary. The current rag_engine.py contains demonstration response behaviour and is **not** represented as a production legal/regulatory knowledge engine.

Production readiness requires authoritative corpus validation, source/licensing review, robust retrieval, multilingual embeddings, citation validation, evaluation datasets, secure authentication, privacy controls, monitoring and professional review.

---

## 21. Responsible-use disclaimer

IP-SAKTI SAHAYAK is an AI-assisted information and research platform. It does not replace an IP professional, advocate, regulatory authority, qualified Ayurveda professional, official registry, official legal text or professional legal/regulatory advice.

Always verify important decisions against the current authoritative source.

---

## 22. References

- Smart India Hackathon: https://www.sih.gov.in/
- SIH 2026 Problem Statements: https://www.sih.gov.in/sih2026PS
- Ministry of Ayush: https://ayush.gov.in/
- All India Institute of Ayurveda: https://aiia.gov.in/
- IP India: https://ipindia.gov.in/
- India Code: https://www.indiacode.nic.in/
- WIPO: https://www.wipo.int/
- Traditional Knowledge Digital Library: https://tkdl.res.in/

---

## Vision

> **From fragmented information to evidence-grounded Ayurveda innovation.**

The long-term vision is a trusted digital knowledge and decision-support layer connecting Ayurveda knowledge, research, IP protection, regulatory understanding and responsible commercialisation.
