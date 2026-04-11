import requests
import json

API_URL = "http://localhost:8000/chat"

def send_message(message: str, thread_id: str):
    print(f"\nUser ({thread_id}): {message}")
    payload = {
        "message": message,
        "thread_id": thread_id
    }
    
    response = requests.post(API_URL, json=payload)
    
    if response.status_code == 200:
        print(f"Agent: {response.json()['response']}")
    else:
        print(f"Error: {response.text}")

# 1. Test Memory on Thread A
send_message("Hi, I main Top lane.", "thread_A")
send_message("What role do I play?", "thread_A")

# 2. Test OP.GG Data on Thread B
send_message("Who counters Darius?", "thread_B")