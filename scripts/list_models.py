"""Quick API key diagnostic - lists all models and check details."""
import os
import json
import urllib.request
from dotenv import load_dotenv

load_dotenv()
key = os.getenv("GEMINI_API_KEY")
print(f"Key prefix: {key[:12]}...")

try:
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={key}"
    resp = urllib.request.urlopen(url)
    data = json.loads(resp.read())
    print("[PASS] API Key is VALID (can list models)")
    models = data.get('models', [])
    print(f"Found {len(models)} models:")
    for m in models:
        print(f"  - {m['name']} (supported methods: {m.get('supportedGenerationMethods', [])})")
except Exception as e:
    print(f"[FAIL] API Key is INVALID: {e}")
