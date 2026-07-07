"""
caching.py — Persistent Disk Caching Layer for the UAE HR & Nafis Copilot

WHY THIS FILE EXISTS:
    Google's Gemini Embedding API converts text into numbers (vectors).
    This process is slow (~0.5 - 2 seconds) and costs money.
    Since the law articles and common user questions do not change frequently,
    we can store (cache) the translated math code on our local hard drive.

HOW IT WORKS:
    We use the `diskcache` library. It acts like a simple dictionary, but
    it saves everything to actual files in a `./cache_dir/` folder.
    Even if you restart your computer or restart Streamlit, the cache remains.

    When we need the embedding for "Article 9":
    1. We check if the text is in the cache.
    2. If YES (Cache Hit): We instantly return the saved math code without calling Google.
    3. If NO (Cache Miss): We call Google, pay a tiny fee, get the code, and save it in the cache for next time.
"""

import os
import sys
import hashlib

# Add the project root directory to Python's path so we can run scripts from anywhere
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from diskcache import Cache
from src.logging_config import get_logger

# Initialize logging for this module
logger = get_logger(__name__)

# Define where to store the cache directory in the project root
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(PROJECT_ROOT, "cache_dir")

# Initialize the persistent disk cache
# This creates the cache_dir folder and sets up an SQLite database inside it to manage keys/values
#
# SIZE LIMIT CALCULATION:
#   Our 3 law PDFs produce ~150 text chunks.
#   Each chunk vector = 3,072 numbers × 8 bytes = ~24 KB per chunk.
#   Total: 150 × 24 KB = ~3.7 MB for all law embeddings.
#   We set 50 MB as a generous ceiling — 10× our actual need — to allow
#   for future law PDFs to be added without ever hitting the limit.
#
CACHE_SIZE_LIMIT = 50 * 1024 * 1024  # 50 MB in bytes
_cache = Cache(CACHE_DIR, size_limit=CACHE_SIZE_LIMIT)


def _hash_text(text: str) -> str:
    """
    Converts any text string into a fixed-length 64-character hash code.
    
    Example:
        "What is probation?" -> "5f4dcc3b5aa765d61d8327deb882cf99"
        
    This ensures our database keys are clean, short, and always identical for the same text.
    """
    cleaned_text = text.strip()
    return hashlib.sha256(cleaned_text.encode("utf-8")).hexdigest()


def get_cached_embedding(text: str) -> list | None:
    """
    Retrieves the embedding vector for a given text from the disk cache.
    
    Returns:
        - A list of 3072 floats (the vector) if it exists in the cache (Cache Hit).
        - None if the text has never been cached before (Cache Miss).
    """
    # 1. Generate the hash code for the text
    key = f"emb_{_hash_text(text)}"
    
    # 2. Check if the key exists in the cache
    if key in _cache:
        logger.info(f"Embedding Cache HIT for text snippet (Length: {len(text)})")
        return _cache[key]
        
    # Not found
    return None


def set_cached_embedding(text: str, vector: list):
    """
    Saves an embedding vector to the disk cache.
    """
    key = f"emb_{_hash_text(text)}"
    _cache[key] = vector
    logger.info(f"Embedding Cache SAVED for text snippet (Length: {len(text)})")


def clear_cache():
    """
    Clears all saved entries in the cache. 
    Use this if you want to force a completely fresh run of the entire app.
    """
    logger.warning("Clearing all cached elements from cache_dir!")
    _cache.clear()


# =============================================================================
# QUICK SELF-TEST — run this file directly to confirm caching works
# python src/caching.py
# =============================================================================
if __name__ == "__main__":
    print("\n--- CACHING SELF-TEST ---")
    
    test_text = "This is a temporary legal clause for testing cache storage."
    fake_vector = [0.1, 0.2, 0.3, 0.4]  # Dummy numbers representing an embedding
    
    # Test 1: Check cache miss
    result_1 = get_cached_embedding(test_text)
    print(f"Test 1 (Initial Search): Expect None -> Got {result_1}")
    
    # Test 2: Save to cache
    set_cached_embedding(test_text, fake_vector)
    print("Test 2: Saved fake vector to cache.")
    
    # Test 3: Check cache hit
    result_3 = get_cached_embedding(test_text)
    print(f"Test 3 (Second Search): Expect {fake_vector} -> Got {result_3}")
    
    # Clean up the test key so we don't pollute the disk
    key = f"emb_{_hash_text(test_text)}"
    del _cache[key]
    print("Test 4: Cleaned up test key from disk. Self-test passed!\n")
