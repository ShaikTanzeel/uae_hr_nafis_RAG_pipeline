"""
fill_qdrant.py — Populate the Qdrant Vector Database with UAE Labour Laws

WHAT THIS SCRIPT DOES:
1. Reads all PDF legal documents from the data/ folder.
2. Performs hierarchical chunking (splits large laws into articles & sub-clauses).
3. Generates 3,072-dimensional Gemini embeddings (with local disk caching).
4. Populates the Qdrant vector database at settings.QDRANT_URL (Dockerized
   Qdrant server as of Phase 1 task B2 — no longer the local-disk ./qdrant_db folder).
5. Updates the database alias so the app can query the fresh legal articles.

USAGE:
    python scripts/data/fill_qdrant.py

    Requires the Qdrant container to be up first: `docker compose up -d`
"""

import os
import sys

# Add project root directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database import ingest_laws, get_qdrant_client, COLLECTION_ALIAS


def main():
    print("=" * 65)
    print("UAE HR & NAFIS COPILOT -- QDRANT DATABASE POPULATOR")
    print("=" * 65)
    print("\n[Step 1/3] Scanning data/ directory for source PDF laws...")

    data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
    if not os.path.exists(data_dir):
        print(f"[X] Error: Data directory not found at '{data_dir}'")
        return

    pdf_files = [f for f in os.listdir(data_dir) if f.lower().endswith(".pdf")]
    print(f"   Found {len(pdf_files)} legal PDF document(s):")
    for pdf in pdf_files:
        print(f"   - {pdf}")

    print("\n[Step 2/3] Chunking legal articles & generating embeddings...")
    print("   (Disk cache is active -- previously processed embeddings will load instantly)\n")

    try:
        # Run full ingestion pipeline (force_recreate=True builds fresh version & swaps alias)
        collection_name, total_chunks = ingest_laws(force_recreate=True)

        print("\n[Step 3/3] Verifying collection in Qdrant...")
        client = get_qdrant_client()
        info = client.get_collection(COLLECTION_ALIAS)
        vector_count = getattr(info, "points_count", getattr(info, "vectors_count", 0))

        print("\n" + "=" * 65)
        print("SUCCESS! QDRANT DATABASE POPULATED SUCCESSFULLY")
        print("=" * 65)
        print(f"* Active Collection Alias : {COLLECTION_ALIAS}")
        print(f"* Target Collection       : {collection_name}")
        print(f"* Total Indexed Chunks   : {total_chunks}")
        print(f"* Qdrant Vector Count    : {vector_count}")
        print("=" * 65)
        print("\nYou can now start the backend with:")
        print("  python scripts/run_backend.py\n")


    except Exception as e:
        print(f"\n[X] Ingestion failed: {e}")
        import traceback
        traceback.print_exc()



if __name__ == "__main__":
    main()
