"""
api.py — FastAPI Backend Bridge for UAE HR & Nafis Copilot

Exposes the existing Python RAG agent as a REST API so the new
Next.js frontend can communicate with it. The existing Streamlit
frontend (src/app.py) is completely untouched.

Endpoints:
    POST /api/chat   — Run a chat turn through the LangGraph agent, streamed
                       live to the browser (Server-Sent Events)
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

import json
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional

from src.agent import stream_agent_turn
from src.config import settings
from src.db import async_session_factory
from src.deps import require_admin
from src.models.user import User
from src.routes.auth import router as auth_router
from src.seed import seed_users

# ─── FastAPI App ──────────────────────────────────────────────────────────────
app = FastAPI(
    title="UAE HR & Nafis Copilot API",
    description=(
        "REST API bridging the Next.js frontend to the LangGraph + Qdrant "
        "backend. Wraps stream_agent_turn() and streams live events over SSE."
    ),
    version="2.0.0",
)

# ─── CORS ─────────────────────────────────────────────────────────────────────
# Allow the Next.js dev server (port 3000) and any production domain.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)


@app.on_event("startup")
async def on_startup():
    """PHASE 3 Section C2: create the seed Admin + demo HR User accounts the
    first time the app runs against an empty `users` table. Safe to run on
    every startup — seed_users() only acts when the table is empty."""
    async with async_session_factory() as db:
        await seed_users(db)


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


class HealthResponse(BaseModel):
    status: str
    qdrant_connected: bool
    collection_name: Optional[str] = None
    vector_count: Optional[int] = None
    model: str
    embedding_model: str


# ─── Endpoints ────────────────────────────────────────────────────────────────

@app.post("/api/chat")
async def chat(request: ChatRequest):
    """
    Runs a single user query through the RAG pipeline and streams the result
    back live, using Server-Sent Events (SSE) — a standard way for a server
    to keep a connection open and send small updates as they happen, instead
    of making the browser wait for one big response at the end.

    Every event from stream_agent_turn() (status updates, tool calls, answer
    text arriving word by word, and the final citation/confidence check) is
    forwarded to the browser as its own "data: {...}" line, in order, as soon
    as it happens.
    """
    history_dicts = [msg.model_dump(exclude_none=True) for msg in request.history]

    def event_stream():
        for event in stream_agent_turn(request.query, history_dicts):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


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
            model=settings.GEMINI_CHAT_MODEL,
            embedding_model="gemini-embedding-001",
        )
    except Exception as e:
        return HealthResponse(
            status="degraded",
            qdrant_connected=False,
            model=settings.GEMINI_CHAT_MODEL,
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


@app.get("/api/admin/ping")
async def admin_ping(user: User = Depends(require_admin)):
    """PHASE 3 Section G3: a throwaway stub whose only job is to prove
    require_admin actually blocks non-admins and lets admins through, before
    any real admin route (Document Library, Settings, Users, Audit — later
    phases) is built on top of the same dependency."""
    return {"status": "ok", "admin_email": user.email}


if __name__ == "__main__":
    import uvicorn
    # Restrict file watcher to 'src' so logs/cache_dir don't trigger infinite reload loops
    uvicorn.run("src.api:app", host="127.0.0.1", port=8000, reload=True, reload_dirs=["src"])

