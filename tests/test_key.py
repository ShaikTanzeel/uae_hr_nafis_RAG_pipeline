"""Quick API key diagnostic - tests if the key works and which project it belongs to."""
import os
import json
import urllib.request
from dotenv import load_dotenv

load_dotenv()
key = os.getenv("GEMINI_API_KEY")
print(f"Key prefix: {key[:12]}...")

# Test 1: Can we list models? (this is a free, non-quota endpoint)
try:
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={key}"
    resp = urllib.request.urlopen(url)
    data = json.loads(resp.read())
    print("[PASS] API Key is VALID (can list models)")
except Exception as e:
    print(f"[FAIL] API Key is INVALID: {e}")
    exit(1)

# Test 2: Try the cheapest possible generation call
try:
    from google import genai
    client = genai.Client(api_key=key)
    r = client.models.generate_content(
        model="gemini-2.0-flash-lite",
        contents="Say OK"
    )
    print(f"[PASS] Generation works! Response: {r.text.strip()}")
except Exception as e:
    err = str(e)
    if "429" in err:
        print("[FAIL] 429 QUOTA EXHAUSTED on this key")
        if "limit: 0" in err:
            print("  WARNING: limit is 0 - project free tier may be fully consumed")
        if "PerMinute" in err and "PerDay" in err:
            print("  Both per-minute AND per-day quotas are exhausted.")
        elif "PerMinute" in err:
            print("  Only per-minute quota hit - wait 60 seconds and try again.")
        elif "PerDay" in err:
            print("  Daily quota exhausted - must wait until midnight Pacific Time.")
    else:
        print(f"[FAIL] Other error: {e}")
