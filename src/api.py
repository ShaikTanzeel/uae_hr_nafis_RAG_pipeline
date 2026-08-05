"""
api.py — FastAPI Backend Bridge for UAE HR & Nafis Copilot

Exposes the existing Python RAG agent as a REST API so the new
Next.js frontend can communicate with it. The existing Streamlit
frontend (src/app.py) is completely untouched.

Endpoints:
    POST /api/chat   — Run a chat turn through the LangGraph agent
    GET  /api/health — System health: Qdrant connection & vector count
    GET  /api/laws   — List of legal corpus documents

Run with:
    uvicorn src.api:app --reload --port 8000
"""

import os
import sys
from dotenv import load_dotenv

# Ensure project root is on the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

from src.agent import run_agent_turn
from src.schemas import AgentResponse

# ─── FastAPI App ──────────────────────────────────────────────────────────────
app = FastAPI(
    title="UAE HR & Nafis Copilot API",
    description=(
        "REST API bridging the Next.js frontend to the LangGraph + Qdrant "
        "backend. Wraps run_agent_turn() and exposes structured JSON responses."
    ),
    version="1.0.0",
)

# ─── CORS ─────────────────────────────────────────────────────────────────────
# Allow the Next.js dev server (port 3000) and any production domain.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        # Add your production domain here when deploying
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Request / Response Models ────────────────────────────────────────────────

class ChatMessage(BaseModel):
    """A single message in the conversation history."""
    role: str  # "user" | "assistant" | "tool"
    content: Optional[str] = None
    tool_calls: Optional[list] = None
    tool_call_id: Optional[str] = None
    citations: Optional[list] = None


class ChatRequest(BaseModel):
    """Request body for POST /api/chat."""
    query: str
    history: list[ChatMessage] = []


class CitationOut(BaseModel):
    article_number: str
    source_document: str


class ChatResponse(BaseModel):
    """Response body from POST /api/chat."""
    answer: str
    citations: list[CitationOut]
    articles_used: list[str]
    confidence: float
    cannot_verify: bool
    injection_blocked: bool
    retrieved_context: str
    history: list[dict]


class HealthResponse(BaseModel):
    status: str
    qdrant_connected: bool
    collection_name: Optional[str] = None
    vector_count: Optional[int] = None
    model: str
    embedding_model: str


# ─── Endpoints ────────────────────────────────────────────────────────────────

@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Run a single user query through the full RAG pipeline:
      Phase A: Qdrant vector retrieval
      Phase B: LangGraph agent reasoning + AST math tool
      Phase C: Guardrail citation verification
    """
    try:
        # Convert Pydantic ChatMessage objects to plain dicts
        history_dicts = [msg.model_dump(exclude_none=True) for msg in request.history]

        result = run_agent_turn(request.query, history_dicts)

        structured: AgentResponse = result["structured"]

        return ChatResponse(
            answer=result["answer"],
            citations=[
                CitationOut(
                    article_number=c.article_number,
                    source_document=c.source_document
                )
                for c in structured.citations
            ],
            articles_used=structured.articles_used,
            confidence=structured.confidence,
            cannot_verify=structured.cannot_verify,
            injection_blocked=result.get("injection_blocked", False),
            retrieved_context=result.get("retrieved_context", ""),
            history=result["history"],
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Agent execution failed: {str(e)}"
        )


@app.get("/api/health", response_model=HealthResponse)
async def health():
    """
    Returns backend health status including Qdrant connectivity.
    The frontend uses this to show the 'System Status' sidebar panel.
    """
    try:
        from src.database import get_qdrant_client, COLLECTION_ALIAS
        client = get_qdrant_client()
        collection_info = client.get_collection(COLLECTION_ALIAS)
        vector_count = getattr(collection_info, "points_count", getattr(collection_info, "vectors_count", 0))

        return HealthResponse(

            status="ok",
            qdrant_connected=True,
            collection_name=COLLECTION_ALIAS,
            vector_count=vector_count,
            model="gpt-4o-mini",
            embedding_model="gemini-embedding-001",
        )
    except Exception as e:
        return HealthResponse(
            status="degraded",
            qdrant_connected=False,
            model="gpt-4o-mini",
            embedding_model="gemini-embedding-001",
        )


@app.get("/api/laws")
async def list_laws():
    """
    Returns the list of legal corpus documents the system is grounded in.
    Used by the sidebar 'Legal Corpus' section in the frontend.
    """
    return {
        "documents": [
            {
                "id": "uae_labour_law_2021",
                "title": "Federal Decree-Law No. (33) of 2021",
                "description": "UAE Labour Relations Law",
                "short": "Federal Decree-Law No. 33",
            },
            {
                "id": "cabinet_resolution_2022",
                "title": "Cabinet Resolution No. (1) of 2022",
                "description": "Executive Regulations of the Labour Law",
                "short": "Cabinet Resolution No. 1",
            },
            {
                "id": "nafis_regulation_2025",
                "title": "Cabinet Regulation No. (43) of 2025",
                "description": "Nafis & Emiratisation Penalties",
                "short": "Nafis Regulation No. 43",
            },
        ]
    }


if __name__ == "__main__":
    import uvicorn
    # Restrict file watcher to 'src' so logs/cache_dir don't trigger infinite reload loops
    uvicorn.run("src.api:app", host="127.0.0.1", port=8000, reload=True, reload_dirs=["src"])

