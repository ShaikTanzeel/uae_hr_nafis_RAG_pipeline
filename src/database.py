import os
import sys
import time
import uuid
from dotenv import load_dotenv

# Add the project root directory to Python's path so we can run scripts from anywhere
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from google import genai
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, CreateAlias, CreateAliasOperation, Filter, FieldCondition, MatchValue
from src.config import settings
from src.ingestion import extract_text_from_pdf, split_by_articles
from src.logging_config import get_logger
from src.caching import get_cached_embedding, set_cached_embedding

# Load environment variables (API keys)
load_dotenv()

# Module-level logger — all logs from this file will be tagged 'src.database'
logger = get_logger(__name__)

# 1. Initialize API and DB Clients
gemini_client = genai.Client(api_key=settings.GEMINI_API_KEY)

_qdrant_client_instance = None

# COLLECTION_ALIAS is the stable "nickname" our app uses to query the database.
# The database will automatically route requests to the active versioned collection (e.g. uae_hr_laws_v1)
COLLECTION_ALIAS = settings.COLLECTION_ALIAS

def get_qdrant_client() -> QdrantClient:
    """Returns the active QdrantClient instance (lazy singleton)."""
    global _qdrant_client_instance
    if _qdrant_client_instance is None:
        # Dockerized Qdrant server (Phase 1 task B2) — replaces the old
        # local-disk mode (QdrantClient(path="./qdrant_db")), which locked
        # the DB file to a single process at a time.
        _qdrant_client_instance = QdrantClient(url=settings.QDRANT_URL)
    return _qdrant_client_instance



def get_embeddings(texts: list) -> list:
    """
    Retrieves embeddings for a list of texts.
    First checks the local disk cache. If any texts are missing, calls
    the Gemini Embedding API to fetch them, updates the cache, and returns
    the combined list of vectors in the original input order.
    """
    # 1. Separate inputs into cached and cache-misses
    results = [None] * len(texts)
    missed_indices = []
    missed_texts = []
    
    for i, text in enumerate(texts):
        cached_vector = get_cached_embedding(text)
        if cached_vector is not None:
            results[i] = cached_vector
        else:
            missed_indices.append(i)
            missed_texts.append(text)
            
    # 2. If there are any misses, fetch them from Google Gemini API
    if missed_texts:
        logger.info(f"Cache misses detected! Calling Gemini API for {len(missed_texts)} text snippets...")
        try:
            response = gemini_client.models.embed_content(
                model="gemini-embedding-001",
                contents=missed_texts
            )
            # 3. Save new embeddings back to the disk cache
            for idx, emb in enumerate(response.embeddings):
                orig_index = missed_indices[idx]
                vector = emb.values
                results[orig_index] = vector
                set_cached_embedding(missed_texts[idx], vector)
        except Exception as e:
            logger.error(f"Error calling Gemini Embedding API: {e}")
            raise
            
    return results

def get_embeddings_with_retry(texts: list, max_retries: int = 5, backoff_factor: float = 2.0) -> list:
    """
    Calls get_embeddings with an exponential backoff retry mechanism.
    If we hit a 429 Rate Limit error, the code will wait and try again rather than crashing.
    """
    delay = 2.0  # Start with a 2-second delay
    for attempt in range(max_retries):
        try:
            return get_embeddings(texts)
        except Exception as e:
            # Detect 429 rate limits or resource exhaustion warnings in the error message
            error_str = str(e).lower()
            if "429" in error_str or "resource_exhausted" in error_str or "quota" in error_str:
                logger.warning(f"-> Rate Limit Hit (429). Attempt {attempt + 1}/{max_retries}. Waiting {delay}s before retrying...")
                time.sleep(delay)
                delay *= backoff_factor  # Double the wait time for the next attempt
            else:
                # If it is a different type of error (like authentication), raise it immediately
                raise e
    raise Exception("Exceeded maximum retries for Gemini Embedding API due to rate limits.")


def _get_next_collection_version() -> tuple[str, str | None]:
    """
    Scans the database collections to determine:
    1. The name of the next versioned collection to write to.
    2. The name of the currently active versioned collection (if any).
    """
    try:
        # Get list of all actual collection names in Qdrant
        res = get_qdrant_client().get_collections()
        existing = [c.name for c in res.collections]
    except Exception as e:
        logger.error(f"Error checking collections: {e}")
        existing = []

    # Find the current active version pointed to by our alias
    current_active = None
    try:
        aliases_res = get_qdrant_client().get_aliases()
        for alias in aliases_res.aliases:
            if alias.alias_name == COLLECTION_ALIAS:
                current_active = alias.collection_name
                break
    except Exception:
        pass

    # If there is no active collection, check if there's any uae_hr_laws_vX collection
    versions = []
    prefix = f"{COLLECTION_ALIAS}_v"
    for name in existing:
        if name.startswith(prefix):
            try:
                ver_num = int(name[len(prefix):])
                versions.append(ver_num)
            except ValueError:
                pass

    if not versions:
        return f"{COLLECTION_ALIAS}_v1", current_active

    highest = max(versions)
    return f"{COLLECTION_ALIAS}_v{highest + 1}", current_active


def initialize_database(force_recreate: bool = False) -> str:
    """
    Prepares a collection for database write/read operations.
    
    If force_recreate is False:
        - Ensures a versioned collection exists and the alias points to it.
        - Returns the active collection name.
        
    If force_recreate is True (Blue/Green migration):
        - Creates a brand new collection version (e.g. uae_hr_laws_v2 if v1 is active).
        - Returns this new collection name so data can be ingested in the background.
    """
    next_ver, active_ver = _get_next_collection_version()
    
    # Scenario 1: Normal startup, no recreate requested
    if not force_recreate:
        if active_ver and get_qdrant_client().collection_exists(active_ver):
            logger.info(f"Active collection '{active_ver}' already exists under alias '{COLLECTION_ALIAS}'. Skipping creation.")
            return active_ver
        
        # If the alias points to nothing but v1 exists on disk, restore alias
        v1_name = f"{COLLECTION_ALIAS}_v1"
        if get_qdrant_client().collection_exists(v1_name):
            logger.info(f"Restoring alias '{COLLECTION_ALIAS}' to point to existing '{v1_name}'.")
            get_qdrant_client().update_collection_aliases(
                change_aliases_operations=[
                    CreateAliasOperation(create_alias=CreateAlias(collection_name=v1_name, alias_name=COLLECTION_ALIAS))
                ]
            )
            return v1_name
            
        # Otherwise, fall through and create v1 from scratch
        next_ver = v1_name

    logger.info(f"Preparing collection '{next_ver}' for ingestion...")
    
    # Create the fresh collection version
    get_qdrant_client().create_collection(
        collection_name=next_ver,
        vectors_config=VectorParams(
            size=3072,               # gemini-embedding-001 dimension
            distance=Distance.COSINE
        )
    )
    logger.info(f"Collection version '{next_ver}' created successfully.")
    return next_ver


# Fixed, arbitrary namespace UUID for this project's deterministic point IDs.
# (Generated once with uuid.uuid4() and hardcoded — NOT meant to be regenerated;
# changing this would change every point ID we've ever computed.)
_POINT_ID_NAMESPACE = uuid.UUID("7f3b1c2a-8e4d-4a5b-9c6f-1d2e3a4b5c6d")


def _make_point_id(source: str, article_number: str, sub_chunk_index: int) -> str:
    """
    Builds a deterministic Qdrant point ID (Phase 1 task F) from an article's own
    identity — its source document, article number, and sub-chunk index — instead
    of a plain sequential counter.

    Same inputs always produce the same UUID (safe to re-ingest: overwrites itself,
    not someone else's data). Different inputs practically never collide, regardless
    of what order or batch documents are ingested in — this is what makes incremental,
    per-document uploads (Phase 4) safe.
    """
    fingerprint = f"{source}|{article_number}|{sub_chunk_index}"
    return str(uuid.uuid5(_POINT_ID_NAMESPACE, fingerprint))


def index_articles(articles: list, target_collection: str, batch_size: int = 10):
    """
    Ingests extracted articles into a specific Qdrant collection.
    """
    logger.info(f"Starting ingestion of {len(articles)} articles into collection '{target_collection}'...")

    for i in range(0, len(articles), batch_size):
        batch = articles[i : i + batch_size]
        batch_texts = [item["text"] for item in batch]

        logger.info(f"Processing batch {i//batch_size + 1}: Chunks {i} to {min(i + batch_size, len(articles))}...")

        # 1. Get embedding vectors (with caching support)
        vectors = get_embeddings_with_retry(batch_texts)

        # 2. Build Qdrant points
        points = []
        for idx, item in enumerate(batch):
            # Deterministic ID (Phase 1 task F) — replaces the old sequential
            # `point_id = i + idx`, which collided across separate ingestion calls
            # once documents get added incrementally (Phase 4).
            point_id = _make_point_id(
                source=item["metadata"]["source"],
                article_number=item["metadata"]["article_number"],
                sub_chunk_index=item["metadata"].get("sub_chunk_index", 0),
            )

            point = PointStruct(
                id=point_id,
                vector=vectors[idx],
                payload={
                    "text": item["text"],
                    "source": item["metadata"]["source"],
                    "article_number": item["metadata"]["article_number"],
                    "article_title": item["metadata"]["article_title"],
                    "sub_chunk_index": item["metadata"].get("sub_chunk_index", 0),
                    "parent_article_id": item["metadata"].get("parent_article_id", "Unknown"),
                    "chunk_type": item["metadata"].get("chunk_type", "unknown")
                }
            )
            points.append(point)
            
        # 3. Save to target collection
        get_qdrant_client().upsert(
            collection_name=target_collection,
            points=points
        )
        
        # Sleep to avoid rate limits
        time.sleep(5.0)
        
    logger.info(f"Successfully indexed all {len(articles)} articles into '{target_collection}'!")


def swap_alias_to_active(new_collection: str):
    """
    Atomically updates the alias to point to the new collection,
    then deletes all older collection versions to free up disk space.
    """
    logger.info(f"Swapping alias '{COLLECTION_ALIAS}' to point to new collection '{new_collection}'...")
    
    # 1. Apply the alias shift atomically
    get_qdrant_client().update_collection_aliases(
        change_aliases_operations=[
            CreateAliasOperation(create_alias=CreateAlias(collection_name=new_collection, alias_name=COLLECTION_ALIAS))
        ]
    )
    logger.info(f"Alias '{COLLECTION_ALIAS}' successfully shifted to '{new_collection}'.")
    
    # 2. Delete older versions of the collection
    try:
        res = get_qdrant_client().get_collections()
        for c in res.collections:
            if c.name.startswith(f"{COLLECTION_ALIAS}_v") and c.name != new_collection:
                logger.info(f"Cleaning up legacy collection version: '{c.name}'...")
                get_qdrant_client().delete_collection(c.name)
    except Exception as e:
        logger.warning(f"Error during legacy collection cleanup: {e}")



def ingest_laws(force_recreate: bool = True) -> tuple[str, int]:
    """
    Scans the data/ folder for PDF laws, extracts text, generates hierarchical chunks,
    fetches embeddings (with disk caching), indexes into Qdrant, and updates the alias.
    """
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(project_root, "data")
    pdf_files = [
        f for f in os.listdir(data_dir)
        if f.lower().endswith(".pdf") and not f.startswith("._")
    ]
    
    if not pdf_files:
        raise ValueError(f"No PDF legal documents found in '{data_dir}'.")
        
    all_articles = []
    for pdf_file in pdf_files:
        pdf_path = os.path.join(data_dir, pdf_file)
        text = extract_text_from_pdf(pdf_path)
        chunks = split_by_articles(text, pdf_file)
        all_articles.extend(chunks)
        
    target_coll = initialize_database(force_recreate=force_recreate)
    index_articles(all_articles, target_collection=target_coll)
    swap_alias_to_active(target_coll)
    
    return target_coll, len(all_articles)


def search_laws(query: str, limit: int = 5, score_threshold: float = 0.35) -> list:

    """
    Searches the database for the articles whose meanings are closest to the query.
    Includes score thresholding and parent article deduplication.
    """
    # 1. Convert user's question into query coordinates (vector)
    query_vector = get_embeddings([query])[0]
    
    # Fetch more candidates initially to allow for filtering and deduplication
    fetch_limit = max(8, limit * 2)
    
    # 2. Search Qdrant for the closest vectors using the modern Query API
    search_results = get_qdrant_client().query_points(
        collection_name=COLLECTION_ALIAS,
        query=query_vector,
        limit=fetch_limit
    )
    
    # 3. Format results into simple structures with deduplication
    formatted_results = []
    seen_parents = set()
    
    for point in search_results.points:
        # Filter by score threshold
        if point.score < score_threshold:
            continue
            
        parent_id = point.payload.get("parent_article_id", point.payload.get("article_number"))
        source = point.payload.get("source")
        parent_key = f"{source}_{parent_id}"
        
        # Deduplicate: only keep the highest scoring sub-chunk for a given parent article
        if parent_key in seen_parents:
            continue
            
        seen_parents.add(parent_key)
        
        # Reconstruct the full parent article context surgically
        try:
            # Query Qdrant for all chunks belonging to this parent article
            parent_chunks, _ = get_qdrant_client().scroll(
                collection_name=COLLECTION_ALIAS,
                scroll_filter=Filter(
                    must=[
                        FieldCondition(key="source", match=MatchValue(value=source)),
                        FieldCondition(key="parent_article_id", match=MatchValue(value=parent_id))
                    ]
                ),
                limit=100
            )

            # Sort chunks in their original legal structure order
            parent_chunks_sorted = sorted(parent_chunks, key=lambda x: x.payload.get("sub_chunk_index", 0))
            
            # Combine the texts, stripping duplicate article headers
            clean_clauses = []
            header = ""
            for pc in parent_chunks_sorted:
                pc_text = pc.payload.get("text", "")
                if "---\n" in pc_text:
                    parts = pc_text.split("---\n", 1)
                    header = parts[0] + "---\n"
                    clean_clauses.append(parts[1])
                else:
                    clean_clauses.append(pc_text)
                    
            full_article_text = header + "\n\n".join(clean_clauses)
        except Exception as e:
            logger.warning(f"Failed to expand parent context for {parent_key}: {e}. Falling back to chunk text.")
            full_article_text = point.payload["text"]
            
        formatted_results.append({
            "score": point.score, # Confidence score (higher = closer meaning)
            "text": full_article_text,
            "source": point.payload["source"],
            "article_number": point.payload["article_number"],
            "article_title": point.payload["article_title"],
            "sub_chunk_index": point.payload.get("sub_chunk_index", 0),
            "chunk_type": point.payload.get("chunk_type", "unknown")
        })
        
        if len(formatted_results) >= limit:
            break
            
    return formatted_results

def main():
    # Diagnostic test execution
    data_dir = "./data"
    pdf_files = [f for f in os.listdir(data_dir) if f.endswith(".pdf")]
    
    if not pdf_files:
        logger.error("No legal PDFs found in ./data.")
        return
        
    # Extract all articles
    all_articles = []
    for pdf_file in pdf_files:
        pdf_path = os.path.join(data_dir, pdf_file)
        text = extract_text_from_pdf(pdf_path)
        chunks = split_by_articles(text, pdf_file)
        all_articles.extend(chunks)
        
    # Initialize Qdrant collection and upload
    target_coll = initialize_database(force_recreate=True)
    index_articles(all_articles, target_collection=target_coll)
    swap_alias_to_active(target_coll)
    
    # Test a query search
    logger.info("=" * 50)
    logger.info("DATABASE SEARCH TEST")
    logger.info("=" * 50)
    test_query = "What is the administrative fine for fake Emiratisation?"
    logger.info(f"Query: '{test_query}'")
    
    results = search_laws(test_query, limit=2)
    for idx, res in enumerate(results):
        logger.info(f"Match #{idx+1} (Score: {res['score']:.4f}) | {res['source']} - Article {res['article_number']} ({res['article_title']})")
        logger.info("Snippet: " + "\n".join(res['text'].split("\n")[:5]))
        logger.info("-" * 50)

if __name__ == "__main__":
    main()
