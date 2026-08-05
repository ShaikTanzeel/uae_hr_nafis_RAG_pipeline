"""
reset_locks.py — Clear Lock Files & Stale Processes

WHAT THIS SCRIPT DOES:
Removes any leftover lock files in ./qdrant_db if a process crashed,
allowing you to start the server cleanly.

USAGE:
    python scripts/reset_locks.py
"""

import os
import sys
import glob

def main():
    print("=" * 60)
    print("RELEASING QDRANT LOCK FILES")
    print("=" * 60)

    qdrant_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "qdrant_db")

    if not os.path.exists(qdrant_dir):
        print("No qdrant_db directory found.")
        return

    # Find lock files inside qdrant_db
    lock_files = glob.glob(os.path.join(qdrant_dir, "**", "*.lock"), recursive=True) + \
                 glob.glob(os.path.join(qdrant_dir, "*.lock"))

    if not lock_files:
        print("✓ No stuck lock files found inside ./qdrant_db")
    else:
        for lock_file in lock_files:
            try:
                os.remove(lock_file)
                print(f"✓ Removed stale lock file: {os.path.basename(lock_file)}")
            except Exception as e:
                print(f"⚠️ Could not remove {lock_file}: {e}")

    print("Done. You can now start the server or run ingestion.")

if __name__ == "__main__":
    main()
