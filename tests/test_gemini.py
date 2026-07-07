import os
from dotenv import load_dotenv
from google import genai

def main():
    # Load environment variables from .env file
    load_dotenv()
    
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY not found in environment variables. Please check your .env file.")
        return
        
    print("Found GEMINI_API_KEY. Initializing Gemini client...")
    
    try:
        # Initialize the modern Gemini API Client
        client = genai.Client(api_key=api_key)
        
        # Test generation of embedding using gemini-embedding-001
        print("Calling gemini-embedding-001 API...")
        response = client.models.embed_content(
            model="gemini-embedding-001",
            contents="Testing the UAE HR Copilot embedding generation pipeline."
        )
        
        # Inspect output
        vector = response.embeddings[0].values
        print("Success!")
        print(f"Embedding Vector Dimensions: {len(vector)}")
        print(f"Sample values (first 5): {vector[:5]}")
        
    except Exception as e:
        print(f"Gemini API Call failed: {e}")

if __name__ == "__main__":
    main()
