"""
repair_qdrant_alias.py — Audit/repair script for the Qdrant collection alias
(Phase 1 task E: "fix the Qdrant naming mix-up").

WHY THIS EXISTS:
`src/database.py` uses a Blue/Green versioning scheme: real data lives in versioned
collections (uae_hr_laws_v1, uae_hr_laws_v2, ...), and a stable alias (uae_hr_laws)
points at whichever version is "live". `swap_alias_to_active()` is supposed to leave
exactly one versioned collection behind after every re-ingestion — but if that cleanup
step ever fails partway (e.g. a crash between the alias swap and the delete loop), an
old, stale versioned collection could be left orphaned on disk. If anything ever queries
a collection by its literal name instead of through the alias, it could silently read
stale/outdated legal text without anyone noticing — hence "quietly serving outdated
results".

WHAT THIS SCRIPT CHECKS:
1. Lists every uae_hr_laws_v* collection that actually exists in Qdrant.
2. Reports what the uae_hr_laws alias currently points to (or flags if missing).
3. Flags orphaned collections: versioned collections that exist but are NOT the one
   the alias points to.
4. Flags a dangling alias: alias exists but points at a collection that no longer exists.

This script is READ-ONLY by default (--fix is required to actually delete orphans).

USAGE:
    python -m scripts.data.repair_qdrant_alias            # report only, no changes
    python -m scripts.data.repair_qdrant_alias --fix       # also delete orphaned collections
"""

import argparse
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.database import get_qdrant_client, COLLECTION_ALIAS


def audit_alias(client, alias_name: str) -> dict:
    """
    Returns a dict describing the current state:
      {
        "all_versions": [...],          # every uae_hr_laws_v* collection that exists
        "alias_target": str | None,     # collection the alias currently points to
        "alias_is_dangling": bool,      # alias points at a collection that doesn't exist
        "orphans": [...],               # versioned collections NOT pointed to by the alias
      }
    """
    prefix = f"{alias_name}_v"

    collections_res = client.get_collections()
    all_versions = sorted(
        c.name for c in collections_res.collections if c.name.startswith(prefix)
    )

    alias_target = None
    aliases_res = client.get_aliases()
    for alias in aliases_res.aliases:
        if alias.alias_name == alias_name:
            alias_target = alias.collection_name
            break

    alias_is_dangling = alias_target is not None and alias_target not in all_versions

    if alias_target is None:
        orphans = list(all_versions)
    else:
        orphans = [v for v in all_versions if v != alias_target]

    return {
        "all_versions": all_versions,
        "alias_target": alias_target,
        "alias_is_dangling": alias_is_dangling,
        "orphans": orphans,
    }


def print_report(state: dict, alias_name: str) -> None:
    print("=" * 65)
    print(f"QDRANT ALIAS AUDIT — '{alias_name}'")
    print("=" * 65)

    print(f"\nVersioned collections found ({len(state['all_versions'])}):")
    if state["all_versions"]:
        for v in state["all_versions"]:
            marker = " <- alias target" if v == state["alias_target"] else ""
            print(f"  - {v}{marker}")
    else:
        print("  (none)")

    print(f"\nAlias '{alias_name}' points to: {state['alias_target'] or '(MISSING — no alias set)'}")

    if state["alias_is_dangling"]:
        print(f"\n[X] PROBLEM: Alias points to '{state['alias_target']}', which does NOT exist.")
        print("    The app would fail to query anything until this is fixed —")
        print("    re-run ingestion (fill_qdrant.py) to recreate a valid collection and alias.")
    elif state["alias_target"] is None and state["all_versions"]:
        print("\n[X] PROBLEM: No alias is set, but versioned collections exist.")
        print("    Data may be present but unreachable through the app's normal query path.")
    elif state["alias_target"] is None:
        print("\n[i] No data ingested yet — nothing to check.")
    else:
        print("\n[OK] Alias correctly points to an existing collection.")

    if state["orphans"]:
        print(f"\n[!] ORPHANED collections found ({len(state['orphans'])}):")
        for o in state["orphans"]:
            print(f"  - {o}  (not referenced by the alias — likely leftover from an interrupted swap)")
        print("    These are quietly consuming disk space and, if ever queried directly")
        print("    by name instead of through the alias, would serve stale/outdated results.")
    else:
        print("\n[OK] No orphaned collections — exactly one version exists and it's the active one.")

    print("=" * 65)


def fix_orphans(client, orphans: list) -> None:
    for name in orphans:
        print(f"Deleting orphaned collection '{name}'...")
        client.delete_collection(name)
    print(f"Deleted {len(orphans)} orphaned collection(s).")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Actually delete orphaned collections found by the audit (default: report only).",
    )
    args = parser.parse_args()

    client = get_qdrant_client()
    state = audit_alias(client, COLLECTION_ALIAS)
    print_report(state, COLLECTION_ALIAS)

    if state["orphans"] and args.fix:
        print()
        fix_orphans(client, state["orphans"])
        print("\nRe-checking after fix...")
        state_after = audit_alias(client, COLLECTION_ALIAS)
        print_report(state_after, COLLECTION_ALIAS)
    elif state["orphans"]:
        print("\nRun again with --fix to delete the orphaned collection(s) above.")


if __name__ == "__main__":
    main()
