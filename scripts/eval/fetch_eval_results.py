import os
import sys
import json
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langsmith import Client

load_dotenv()

def fetch_results():
    client = Client()
    
    project_name = "agent-hardening-run-3fd2b55e"
    print(f"Fetching runs for project/experiment: {project_name}")
    
    try:
        # List all runs in the experiment
        runs = list(client.list_runs(project_name=project_name))
        print(f"Found {len(runs)} runs.")
        
        runs_data = []
        for r in runs:
            # Get feedback/scores for this run
            feedbacks = list(client.list_feedback(run_ids=[r.id]))
            scores = {f.key: f.score for f in feedbacks}
            comments = {f.key: f.comment for f in feedbacks}
            
            runs_data.append({
                "id": str(r.id),
                "name": r.name,
                "inputs": r.inputs,
                "outputs": r.outputs,
                "scores": scores,
                "comments": comments,
                "error": r.error
            })
            
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        output_dir = os.path.join(project_root, "Evaluation")
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, "langsmith_results.json")

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(runs_data, f, indent=2)

        print(f"Successfully saved LangSmith results to {output_path}")
    except Exception as e:
        print(f"Error fetching results: {e}")

if __name__ == "__main__":
    fetch_results()
