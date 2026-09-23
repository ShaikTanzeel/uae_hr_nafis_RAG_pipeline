import os
import sys
from dotenv import load_dotenv

# Add the project root directory to Python's path so we can run scripts from anywhere
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.test_suite import TEST_CASES
from langsmith import Client

# Load environment variables (API keys)
load_dotenv()

def upload_to_langsmith():
    print("Initializing LangSmith client...")
    client = Client()
    
    dataset_name = "uae-hr-compliance-suite"
    
    # If dataset already exists, delete it so we have a clean upload of the fixed test cases
    try:
        if client.has_dataset(dataset_name=dataset_name):
            print(f"Dataset '{dataset_name}' already exists. Deleting to upload fresh cases...")
            client.delete_dataset(dataset_name=dataset_name)
    except Exception as e:
        print(f"Note: Could not check/delete dataset (this is normal if it is the first run): {e}")

    print(f"Creating new dataset '{dataset_name}' in LangSmith...")
    dataset = client.create_dataset(
        dataset_name=dataset_name,
        description="Ground truth compliance test cases for UAE Labour Law and Nafis Emiratisation rules."
    )
    
    inputs = []
    outputs = []
    
    for tc in TEST_CASES:
        inputs.append({
            "query": tc["query"],
            "is_multi_turn": tc["is_multi_turn"],
            "setup_queries": tc.get("setup_queries", [])
        })
        outputs.append({
            "expected_citations": tc["expected_citations"],
            "expected_key_phrases": tc["expected_key_phrases"],
            "forbidden_terms": tc["forbidden_terms"],
            "expect_cannot_verify": tc["expect_cannot_verify"],
            "expected_math_tokens": tc["expected_math_tokens"]
        })
        
    print(f"Uploading {len(TEST_CASES)} examples to LangSmith...")
    client.create_examples(
        inputs=inputs,
        outputs=outputs,
        dataset_id=dataset.id
    )
    
    print("\n" + "=" * 60)
    print("SUCCESS: Test cases uploaded to LangSmith!")
    print(f"Go to: https://smith.langchain.com/ to view the '{dataset_name}' dataset.")
    print("=" * 60)

if __name__ == "__main__":
    upload_to_langsmith()
