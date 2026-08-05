import json

def summarize():
    try:
        with open("scratch/langsmith_results.json", "r", encoding="utf-8") as f:
            data = json.load(f)
            
        print(f"Total runs analyzed: {len(data)}")
        
        # Filter for leaf runs that have queries
        query_runs = [r for r in data if r.get("inputs") and "query" in r["inputs"]]
        print(f"Total user query runs: {len(query_runs)}")
        
        failed_count = 0
        for idx, r in enumerate(query_runs, 1):
            query = r["inputs"]["query"]
            output = r.get("outputs", {}).get("answer", "") if r.get("outputs") else ""
            scores = r.get("scores", {})
            comments = r.get("comments", {})
            
            # Check if any score is less than 0.8
            has_failure = any(score < 0.8 for score in scores.values())
            
            if has_failure:
                failed_count += 1
                print(f"\n--- FAILED QUERY #{failed_count} ---")
                print(f"Query: {query}")
                print(f"Scores: {scores}")
                print("Comments/Rationale:")
                for k, comm in comments.items():
                    if scores.get(k, 1.0) < 0.8:
                        print(f"  - {k}: {comm}")
                print(f"Answer:\n{output[:300]}...")
                
        print(f"\nSummary: {failed_count} / {len(query_runs)} query runs failed or had sub-optimal scores.")
    except Exception as e:
        print(f"Error parsing results: {e}")

if __name__ == "__main__":
    summarize()
