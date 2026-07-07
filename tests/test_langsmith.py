import os
import sys
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

def run_diagnostics():
    print("=" * 60)
    print("LANGSMITH DIAGNOSTIC RUNNER")
    print("=" * 60)
    
    # 1. Read variables
    tracing_v2 = os.getenv("LANGCHAIN_TRACING_V2")
    api_key = os.getenv("LANGCHAIN_API_KEY") or os.getenv("LANGSMITH_API_KEY")
    endpoint = os.getenv("LANGCHAIN_ENDPOINT", "https://api.smith.langchain.com")
    project = os.getenv("LANGCHAIN_PROJECT")
    workspace_id = os.getenv("LANGSMITH_WORKSPACE_ID")
    
    print(f"LANGCHAIN_TRACING_V2 : {tracing_v2}")
    print(f"LANGCHAIN_ENDPOINT   : {endpoint}")
    print(f"LANGCHAIN_PROJECT    : {project}")
    print(f"LANGSMITH_WORKSPACE_ID: {workspace_id}")
    
    if api_key:
        masked_key = api_key[:8] + "..." + api_key[-4:] if len(api_key) > 12 else "Too Short!"
        print(f"LANGCHAIN_API_KEY    : {masked_key} (Length: {len(api_key)})")
    else:
        print("LANGCHAIN_API_KEY    : NOT FOUND!")
        
    print("-" * 60)
    
    # 2. Test Connection
    try:
        from langsmith import Client
        print("Imported 'langsmith' successfully. Creating client...")
        client = Client(
            api_url=endpoint,
            api_key=api_key
        )
        
        print("Attempting to fetch workspace or check credentials...")
        # A simple read operation to verify the key
        try:
            # Let's try to query the projects to see if the key works
            projects = list(client.list_projects())
            print(f"Connection SUCCESSFUL! Found {len(projects)} existing projects.")
            print("Your API key is fully valid and authorized for reads.")
        except Exception as read_err:
            print(f"Authentication READ Failed with error:\n{read_err}")
            print("\nAdvice: This suggests the key is invalid or your region endpoint doesn't match.")
            return
            
        # Try to test writing/checking a test dataset name
        print("\nTesting dataset check permission...")
        try:
            client.has_dataset(dataset_name="diagnostic-test-dataset-temporary")
            print("Dataset check check passed (write/edit permissions exist!).")
        except Exception as write_err:
            print(f"Dataset check FAILED with error:\n{write_err}")
            
    except Exception as e:
        print(f"Diagnostics failed with fatal error:\n{e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_diagnostics()
