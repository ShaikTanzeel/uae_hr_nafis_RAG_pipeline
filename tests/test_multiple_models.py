"""Test multiple models to see if any have active quota."""
import os
from dotenv import load_dotenv
from google import genai

load_dotenv()
key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=key)

test_models = [
    "gemini-2.5-flash",
    "gemini-3.5-flash",
    "gemini-2.0-flash-lite",
    "gemini-2.0-flash",
    "gemini-1.5-flash",
    "gemini-1.5-pro",
]

for model in test_models:
    print(f"Testing model: {model}...")
    try:
        r = client.models.generate_content(
            model=model,
            contents="Say OK"
        )
        print(f"  [SUCCESS] Response: {r.text.strip()}")
    except Exception as e:
        err = str(e)
        if "429" in err:
            # Check if there is limit: 0 or something else
            print(f"  [429 Quota Exhausted] details: {err[:150]}")
        else:
            print(f"  [Error] details: {err[:150]}")
