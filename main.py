import uvicorn
import os
import webbrowser
import threading
from dotenv import load_dotenv

def open_browser():
    webbrowser.open("http://127.0.0.1:8000/")

if __name__ == "__main__":
    load_dotenv()
    print("Starting League of Legends Agent API & UI...")
    print("Opening the browser automatically...")
    print("Press Ctrl+C to close the server.")
    
    # Automatically open the browser 1.5 seconds after server starts
    threading.Timer(1.5, open_browser).start()
    
    # Run the uvicorn server programmatically
    uvicorn.run("app.api:app", host="0.0.0.0", port=8000, reload=True)
