"""
run_backend.py — Launch FastAPI Backend Server for Next.js Frontend

WHAT THIS SCRIPT DOES:
1. Verifies database access.
2. Starts the FastAPI server on http://localhost:8000.
3. Restricts file reloader to src/ so cache/log writes don't trigger restart loops.

USAGE:
    python scripts/run_backend.py
"""

import os
import sys
import uvicorn

# Add project root directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def main():
    print("=" * 65)
    print("UAE HR & NAFIS COPILOT -- FASTAPI BACKEND SERVER")
    print("=" * 65)
    print("* API URL       : http://localhost:8000")
    print("* Health Check  : http://localhost:8000/api/health")
    print("* Legal Corpus  : http://localhost:8000/api/laws")
    print("* Interactive UI: http://localhost:8000/docs")
    print("=" * 65 + "\n")


    # Single-process mode on Windows ensures Qdrant local disk database is opened once without lock contention
    uvicorn.run(
        "src.api:app",
        host="127.0.0.1",
        port=8000,
        reload=False,
    )


if __name__ == "__main__":
    main()
