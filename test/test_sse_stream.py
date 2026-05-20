import httpx
import json

def test_endpoint():
    url = "http://127.0.0.1:8000/chat"
    payload = {
        "message": "Who counters Darius in RANKED TOP?",
        "thread_id": "test_verification_session"
    }
    
    print("Testing SSE stream from /chat...")
    try:
        with httpx.stream("POST", url, json=payload, timeout=60.0) as response:
            if response.status_code != 200:
                print(f"❌ Failed: HTTP {response.status_code}")
                print(response.read())
                return
                
            for line in response.iter_lines():
                if line:
                    print(line)
    except Exception as e:
        print(f"❌ Error hitting endpoint: {e}")

if __name__ == "__main__":
    test_endpoint()
