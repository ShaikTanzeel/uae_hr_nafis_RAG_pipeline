import os
import sys
import time

# Add the project root directory to Python's path so we can import src modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database import search_laws

# ==============================================================================
# RETRIEVAL GROUND TRUTH TEST CASES
#
# Each test case represents a realistic query and the exact legal document
# and article number that contains the correct answer.
# ==============================================================================
RETRIEVAL_TEST_CASES = [
    {
        "id": 1,
        "query": "A company has 3 workers registered under sham Emiratisation. What is the administrative fine we will face?",
        "expected_article": "2",
        "expected_source_snippet": "43",  # Cabinet Regulation No. (43) of 2025
        "description": "Nafis Sham Emiratisation Fine"
    },
    {
        "id": 2,
        "query": "What is the maximum probation period allowed for a new employee under UAE Labour Law?",
        "expected_article": "9",
        "expected_source_snippet": "33",  # Federal Decree by Law No. (33) of 2021
        "description": "Probation Period Limit"
    },
    {
        "id": 3,
        "query": "How many days of sick leave is an employee entitled to per year, and how is the pay split?",
        "expected_article": "31",
        "expected_source_snippet": "33",  # Federal Decree by Law No. (33) of 2021
        "description": "Sick Leave Tiers"
    },
    {
        "id": 4,
        "query": "What are the rules regarding gratuity (end of service benefits) for an employee who has completed 3 years of continuous service?",
        "expected_article": "51",
        "expected_source_snippet": "33",  # Federal Decree by Law No. (33) of 2021
        "description": "End of Service Gratuity"
    },
    {
        "id": 5,
        "query": "A female employee is taking maternity leave. Her monthly salary is AED 18,000. What is her total maternity leave pay entitlement?",
        "expected_article": "30",
        "expected_source_snippet": "33",  # Federal Decree by Law No. (33) of 2021
        "description": "Maternity Leave Pay"
    },
    {
        "id": 6,
        "query": "If we submit incorrect documents to evade Emiratisation systems, what are the Nafis fines?",
        "expected_article": "2",
        "expected_source_snippet": "43",  # Cabinet Regulation No. (43) of 2025
        "description": "Nafis Evasion Fines"
    },
    {
        "id": 7,
        "query": "What is the notice period required to terminate an employee during probation under UAE labor law?",
        "expected_article": "9",
        "expected_source_snippet": "33",  # Federal Decree by Law No. (33) of 2021
        "description": "Probation Dismissal Notice"
    }
]

def evaluate_retrieval():
    print("=" * 70)
    print("  UAE HR & NAFIS COPILOT - STANDALONE RETRIEVAL EVALUATION")
    print("  Evaluating {len(RETRIEVAL_TEST_CASES)} queries directly against Qdrant")
    print("  Metrics: Recall@5 and Mean Reciprocal Rank (MRR)")
    print("=" * 70)

    results = []
    
    for tc in RETRIEVAL_TEST_CASES:
        query = tc["query"]
        expected_art = tc["expected_article"]
        expected_src = tc["expected_source_snippet"]
        
        print(f"\n[Query {tc['id']}] \"{query}\"")
        print(f"  Expecting: Article {expected_art} from document containing '{expected_src}'")
        
        start_time = time.time()
        try:
            # Retrieve top 5 documents from Qdrant
            hits = search_laws(query, limit=5)
            duration = time.time() - start_time
            
            recall_at_5 = 0.0
            reciprocal_rank = 0.0
            found_rank = None
            matched_payload = None
            
            # Look for the ground truth article in the top 3 results
            for idx, hit in enumerate(hits):
                hit_article = str(hit.get("article_number", "")).strip()
                hit_source = hit.get("source", "")
                
                # Check if this hit matches our expected article number and source document
                if hit_article == expected_art and expected_src in hit_source:
                    recall_at_5 = 1.0
                    reciprocal_rank = 1.0 / (idx + 1)
                    found_rank = idx + 1
                    matched_payload = hit
                    break
            
            results.append({
                "id": tc["id"],
                "description": tc["description"],
                "query": query,
                "duration": duration,
                "recall_at_5": recall_at_5,
                "reciprocal_rank": reciprocal_rank,
                "found_rank": found_rank,
                "hits": hits
            })
            
            # Print the results of this specific query
            if recall_at_5 > 0:
                print(f"  Result   : FOUND at Rank {found_rank} (Score: {matched_payload['score']:.4f}) in {duration:.2f}s")
                print(f"  Title    : {matched_payload.get('article_title', 'No Title')}")
            else:
                print(f"  Result   : NOT FOUND in Top 5 ({duration:.2f}s)")
                print("  Top retrieved items were:")
                for idx, hit in enumerate(hits):
                    print(f"    {idx+1}. Article {hit.get('article_number')} from {hit.get('source')} (Score: {hit.get('score'):.4f})")
                    
        except Exception as e:
            print(f"  CRASHED: {e}")
            results.append({
                "id": tc["id"],
                "description": tc["description"],
                "query": query,
                "duration": 0.0,
                "recall_at_5": 0.0,
                "reciprocal_rank": 0.0,
                "found_rank": None,
                "hits": []
            })
            
        # Small delay to prevent hitting embedding API rate limits
        time.sleep(1.0)

    # ==============================================================================
    # COMPUTE AGGREGATE METRICS
    # ==============================================================================
    total_queries = len(results)
    avg_recall = sum(r["recall_at_5"] for r in results) / total_queries if total_queries else 0.0
    mrr = sum(r["reciprocal_rank"] for r in results) / total_queries if total_queries else 0.0
    avg_duration = sum(r["duration"] for r in results) / total_queries if total_queries else 0.0

    # Print summary table
    print("\n" + "=" * 80)
    print("  RETRIEVAL EVALUATION SUMMARY")
    print("=" * 80)
    print(f"{'ID':<3} | {'Description':<25} | {'Status':<10} | {'Rank':<6} | {'Recall@5':<8} | {'RR':<6} | {'Latency':<8}")
    print("-" * 80)
    for r in results:
        status = "FOUND" if r["recall_at_5"] > 0 else "MISSING"
        rank_str = str(r["found_rank"]) if r["found_rank"] else "-"
        print(f"{r['id']:<3} | {r['description']:<25} | {status:<10} | {rank_str:<6} | {r['recall_at_5']:<8.1f} | {r['reciprocal_rank']:<6.3f} | {r['duration']:<7.2f}s")
    print("-" * 80)
    print(f"{'AVERAGE / OVERALL':<42} | {avg_recall:<8.3f} | {mrr:<6.3f} | {avg_duration:<7.2f}s")
    print("=" * 80)
    
    # Save a markdown report to retrieval_report.md
    report_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "retrieval_report.md"
    )
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# Standalone Retrieval Evaluation Report\n\n")
        f.write(f"**Evaluation Date:** {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"**Vector Database:** Qdrant (Local Disk Mode)\n")
        f.write(f"**Embedding Model:** gemini-embedding-001\n\n")
        
        f.write("## Key Metrics Summary\n\n")
        f.write(f"* **Average Recall@5:** {avg_recall:.3f} (Ideal: 1.0)\n")
        f.write(f"* **Mean Reciprocal Rank (MRR):** {mrr:.3f} (Ideal: 1.0)\n")
        f.write(f"* **Average Search Latency:** {avg_duration:.2f} seconds\n\n")
        
        f.write("## Detailed Query Results\n\n")
        f.write("| ID | Description | Query | Status | Found Rank | Recall@5 | Reciprocal Rank | Latency |\n")
        f.write("|----|-------------|-------|--------|------------|----------|-----------------|---------|\n")
        for r in results:
            status = "FOUND" if r["recall_at_5"] > 0 else "MISSING"
            rank_str = str(r["found_rank"]) if r["found_rank"] else "-"
            f.write(f"| {r['id']} | {r['description']} | *\"{r['query']}\"* | {status} | {rank_str} | {r['recall_at_5']:.1f} | {r['reciprocal_rank']:.3f} | {r['duration']:.2f}s |\n")
            
    print(f"\nSaved markdown report to: {report_path}")

if __name__ == "__main__":
    evaluate_retrieval()
