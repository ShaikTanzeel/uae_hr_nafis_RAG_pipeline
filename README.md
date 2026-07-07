# 🇦🇪 UAE HR & Nafis Copilot (Agentic RAG)

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![Framework](https://img.shields.io/badge/framework-LangGraph%20%7C%20LangChain-orange.svg)](https://langchain.com/)
[![Vector DB](https://img.shields.io/badge/Vector%20DB-Qdrant-red.svg)](https://qdrant.tech/)
[![Frontend](https://img.shields.io/badge/frontend-Streamlit-green.svg)](https://streamlit.io/)
[![CI/CD](https://img.shields.io/badge/build-GitHub%20Actions-brightgreen.svg)](https://github.com/features/actions)

A production-grade, compliance-focused **Agentic RAG (Retrieval-Augmented Generation)** application designed to act as an HR Copilot for companies operating in the United Arab Emirates. 

This copilot answers complex legal and regulatory queries based on the **UAE Federal Decree-Law No. 33 of 2021 (Labour Law)**, its **Executive Regulations (Cabinet Resolution No. 1 of 2022)**, and the **Nafis/Emiratisation Cabinet Regulations (Cabinet Regulation No. 43 of 2025)** (including the 10% Emiratisation quotas and AED 108,000+ fines).

---

## 🏗️ System Architecture

This system uses a modular, multi-agent reasoning flow built on **LangChain/LangGraph** with a local **Qdrant** database, persistent caching, and a validation guardrail layer.

```mermaid
graph TD
    User([User Query]) --> QR[Query Rewriter]
    History[(Conversation History)] --> QR
    QR -->|Contextual Search Query| DB[(Qdrant Vector DB)]
    
    subgraph Retrieval Pipeline
        DB -->|Score Thresholding & Deduplication| CR[Context Assembly]
        Cache[(Disk Cache)] <-->|Embedding Cache| DB
    end

    CR -->|Grounded Context| AG[LangGraph Agent]
    AG -->|AST Execution Request| MT[Math Calculator Tool]
    MT -->|Computed Penalty| AG
    
    AG -->|Raw Response| GR[Guardrail & Citation Verification]
    GR -->|Pass/Fail/Warning| UI[Streamlit Frontend]
```

---

## 🌟 Key Production-Grade Features

To transition from a "tutorial prototype" to a **production-ready system**, the following engineering patterns were implemented:

### 1. Agentic Tool Calling (Deterministic Calculations)
Legal queries often involve calculations (e.g., *"We missed our Emiratisation quota by 3 people; what is the fine?"*). Rather than letting the LLM hallucinate math, the agent dynamically identifies calculation needs and calls a safe **Abstract Syntax Tree (AST) Math Calculator Tool** to compute exact penalties.

### 2. Hierarchical Sub-Article Chunking
Instead of embedding full legal articles (which dilutes vector relevance) or arbitrary token splits (which loses context), laws are split using a **two-pass hierarchical chunking** pipeline:
- Articles under 500 characters are kept intact.
- Large articles are parsed down into specific clauses (`1.`, `a.`, `b.`) with overlap windows.
- Each sub-clause is enriched with its parent article's metadata (e.g., `Article (9) — Probation Period`) to maintain semantic boundaries during retrieval.

### 3. Multi-Turn Query Rewriting
To support context-aware conversation (e.g., Q1: *"What is the probation period?"* &rarr; Q2: *"Can the employer extend it?"*), a dedicated LLM query rewriter analyzes the chat history and reframes conversational pronouns into standalone search queries before vector matching.

### 4. Database Versioning & Zero-Downtime Migration
To prevent service interruption during data ingestions:
- Collection versions are auto-detected (e.g., `v1`, `v2`).
- A background builder compiles the new collection version.
- An **atomic alias swap** redirects the application query path to the new version.
- Outdated versions are cleaned up automatically.

### 5. Input Sanitization & Citation Verification Guardrails
A dual-layer guardrail protects the system:
- **Input Guard:** Sanitizes and blocks prompt injection payloads.
- **Output Guard:** Compares LLM citations against the actual retrieved database context to flag hallucinated article numbers before rendering the response to the user.

### 6. Embedding Caching & Structured Observability
- **Disk Caching:** Caches Google Gemini embedding API requests locally, preventing redundant API cost and network overhead on identical chunks.
- **Trace ID Injection:** Injects a unique 8-character Trace ID into every log event across the UI, Agent, and database interactions, facilitating standard production debugging.

---

## 📂 Codebase Organization

```
UAE HR & Nafis Copilot/
├── .github/workflows/       
│   └── test.yml                 # Automated CI/CD execution workflow
├── data/                        # Source PDF legislative files
├── docs/                        # Project roadmap, audits, and trackers
├── scripts/                     # Developer and deployment utilities
│   ├── find_article_headers.py  # Map PDF index layout
│   ├── inspect_pdfs.py          # Character extraction inspector
│   ├── list_models.py           # Model endpoint enumerator
│   └── upload_dataset.py        # LangSmith gold standard sync
├── src/                         # Core production codebase
│   ├── app.py                   # Streamlit Frontend UI
│   ├── agent.py                 # Multi-turn LangGraph agent
│   ├── caching.py               # Diskcache layer
│   ├── database.py              # Qdrant client & alias manager
│   ├── guardrails.py            # Injection detection & citation grounding
│   ├── ingestion.py             # Hierarchical clause splitter
│   ├── logging_config.py        # Structured logging configuration
│   ├── schemas.py               # Pydantic data contracts
│   └── tools.py                 # AST calculation tool
├── tests/                       # Automated test suites
│   ├── test_suite.py            # 19-loop integration and boundary suite
│   ├── eval_retrieval.py        # Standalone recall/MRR calculator
│   └── evaluations.py           # LangSmith evaluators
├── .gitignore                   
└── requirements.txt             
```

---

## 🚀 Setup and Installation

### 1. Prerequisites
- Python 3.10 or 3.11
- API Keys: **Google Gemini API Key** (Embeddings), **Groq API Key** or **OpenAI API Key** (Reasoning Engine)

### 2. Installation
Clone the repository:
```bash
git clone https://github.com/ShaikTanzeel/uae_hr_nafis_RAG_pipeline.git
cd uae_hr_nafis_RAG_pipeline
```

Create and activate a virtual environment:
```bash
python -m venv venv
# Windows PowerShell:
.\venv\Scripts\Activate.ps1
# Linux/macOS:
source venv/bin/activate
```

Install dependencies:
```bash
pip install -r requirements.txt
```

### 3. Environment Variables
Create a `.env` file in the root directory:
```env
# Vector Database
QDRANT_HOST=localhost
QDRANT_PORT=6333

# LLM Providers (Specify keys for models you wish to use)
GEMINI_API_KEY=your_gemini_api_key
GROQ_API_KEY=your_groq_api_key
OPENAI_API_KEY=your_openai_api_key

# Observability (Optional)
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your_langsmith_api_key
LANGCHAIN_PROJECT=uae-hr-copilot
```

---

## 💻 Running the Application

### 1. Ingest Data & Initialize Vector Database
Ensure the legislative PDF documents are placed in `./data`. Ingest the documents and construct the versioned Qdrant indexes by running:
```bash
python -m src.database
```
*Note: This parses, chunks, caches embeddings, builds versioned collections, and activates the alias.*

### 2. Start the Streamlit Application
Launch the web interface:
```bash
streamlit run src/app.py
```
*The app will automatically spin up on `http://localhost:8501`.*

---

## 🧪 Testing & Evaluation

The codebase comes equipped with comprehensive local verification testing and LangSmith integration.

### Local Integration Test Suite
To evaluate the agent against **19 complex boundary scenarios** (such as sick leave tier splits, probation notices, and circumvention penalties):
```bash
python tests/test_suite.py
```

### Retrieval Evaluation
Evaluate the vector database precision and recall independently:
```bash
python tests/eval_retrieval.py
```

---

## 🛡️ License

This project is licensed under the MIT License - see the LICENSE file for details.
