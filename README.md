# 🇦🇪 UAE HR & Nafis Copilot (Agentic RAG)

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![Node 18+](https://img.shields.io/badge/node-18+-green.svg)](https://nodejs.org/)
[![Framework](https://img.shields.io/badge/framework-LangGraph%20%7C%20FastAPI-orange.svg)](https://fastapi.tiangolo.com/)
[![Vector DB](https://img.shields.io/badge/Vector%20DB-Qdrant-red.svg)](https://qdrant.tech/)
[![Frontend](https://img.shields.io/badge/frontend-Next.js-black.svg)](https://nextjs.org/)

A production-grade, compliance-focused **Agentic RAG (Retrieval-Augmented Generation)** application designed to act as an HR Copilot for companies operating in the United Arab Emirates. 

This copilot answers complex legal and regulatory queries based on the **UAE Federal Decree-Law No. 33 of 2021 (Labour Law)**, its **Executive Regulations (Cabinet Resolution No. 1 of 2022)**, and the **Nafis/Emiratisation Cabinet Regulations (Cabinet Regulation No. 43 of 2025)** (including the 10% Emiratisation quotas and AED 108,000+ fines).

---

## 📸 Project Gallery

<p align="center">
  <img src="assets/screenshot-1.png" alt="Chat Interface" width="800">
  <br>
  <em>Modern Next.js Chat Interface with Multi-Turn Memory & Document Preview.</em>
</p>

<p align="center">
  <img src="assets/screenshot-2.png" alt="AST Calculator" width="800">
  <br>
  <em>Dynamic math execution using the built-in AST Calculator tool for exact legal calculations.</em>
</p>

<p align="center">
  <img src="assets/screenshot-3.png" alt="Guardrails" width="800">
  <br>
  <em>Anti-Hallucination & Security Guardrails actively blocking prompt injections and unverified claims.</em>
</p>

---

## 🏗️ System Architecture

This system uses a modular, multi-agent reasoning flow built on **LangChain/LangGraph** with a local **Qdrant** database, persistent caching, and a validation guardrail layer. It is served by a **FastAPI backend** and a modern **Next.js frontend**.

```mermaid
graph TD
    User([User Query]) --> UI[Next.js Frontend]
    UI -->|API Request| API[FastAPI Backend]
    API --> QR[Query Rewriter]
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
    GR -->|Pass/Fail/Warning| API
    API -->|JSON Response| UI
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
- **Anti-Sycophancy Guardrail:** Actively corrects false assumptions in leading user questions to prevent the LLM from hallucinating fake validation.

### 6. Embedding Caching & Structured Observability
- **Disk Caching:** Caches Google Gemini embedding API requests locally, preventing redundant API cost and network overhead on identical chunks.
- **Trace ID Injection:** Injects a unique 8-character Trace ID into every log event across the UI, Agent, and database interactions, facilitating standard production debugging.

---

## 📂 Codebase Organization

```text
UAE HR & Nafis Copilot/
├── data/                        # Source PDF legislative files
├── docs/                        # Project roadmap, audits, and trackers
├── frontend/                    # Next.js React Frontend Application
│   ├── app/                     # Next.js App Router (Pages, Layouts)
│   ├── components/              # UI Components (Chat Interface, Sidebar)
│   └── lib/                     # Frontend utilities and API clients
├── scripts/                     # Developer and deployment utilities
│   ├── eval/                    # Evaluation and LangSmith sync scripts
│   ├── utils/                   # Data inspection utilities
│   └── run_backend.py           # Launch script for the FastAPI server
├── src/                         # Core FastAPI Backend & RAG System
│   ├── api.py                   # FastAPI routes and server logic
│   ├── agent.py                 # Multi-turn LangGraph agent
│   ├── caching.py               # Diskcache layer for embeddings
│   ├── database.py              # Qdrant client & alias manager
│   ├── guardrails.py            # Injection detection & citation grounding
│   ├── ingestion.py             # Hierarchical clause splitter
│   ├── logging_config.py        # Structured logging configuration
│   ├── schemas.py               # Pydantic data contracts
│   └── tools.py                 # AST calculation tool
├── tests/                       # Automated test suites
│   ├── test_suite.py            # Integration and boundary suite
│   ├── eval_retrieval.py        # Standalone recall/MRR calculator
│   └── evaluations.py           # LangSmith evaluators
├── requirements.txt             # Python backend dependencies
└── package.json                 # Frontend Node dependencies (inside /frontend)
```

---

## 🚀 Setup and Installation

### 1. Prerequisites
- Python 3.10+
- Node.js 18+
- API Keys: **Google Gemini API Key** (Embeddings), **OpenAI API Key** or **Groq API Key** (Reasoning Engine)

### 2. Installation
Clone the repository:
```bash
git clone https://github.com/ShaikTanzeel/uae_hr_nafis_RAG_pipeline.git
cd uae_hr_nafis_RAG_pipeline
```

#### Backend Setup
Create and activate a virtual environment:
```bash
python -m venv venv
# Windows PowerShell:
.\venv\Scripts\Activate.ps1
# Linux/macOS:
source venv/bin/activate
```

Install backend dependencies:
```bash
pip install -r requirements.txt
```

#### Frontend Setup
```bash
cd frontend
npm install
cd ..
```

### 3. Environment Variables
Create a `.env` file in the root directory:
```env
# Vector Database
QDRANT_HOST=localhost
QDRANT_PORT=6333

# LLM Providers
GEMINI_API_KEY=your_gemini_api_key
OPENAI_API_KEY=your_openai_api_key

# Observability (Optional)
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your_langsmith_api_key
LANGCHAIN_PROJECT=uae-hr-copilot
```

Create a `.env.local` inside the `frontend` directory:
```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## 💻 Running the Application

### 1. Ingest Data & Initialize Vector Database
Ensure the legislative PDF documents are placed in `./data`. Ingest the documents and construct the versioned Qdrant indexes by running:
```bash
python -m src.database
```

### 2. Start the Backend Server
Launch the FastAPI server (runs on `http://localhost:8000`):
```bash
python scripts/run_backend.py
```

### 3. Start the Next.js Frontend
In a separate terminal window, launch the web application:
```bash
cd frontend
npm run dev
```
*The app will be available at `http://localhost:3000`.*

---

## 🧪 Testing & Evaluation

The codebase comes equipped with comprehensive local verification testing and LangSmith integration.

### Local Integration Test Suite
To evaluate the agent against complex boundary scenarios:
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
