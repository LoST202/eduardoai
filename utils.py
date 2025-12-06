import os
import json
import uuid
from datetime import datetime
from threading import Lock

UPLOAD_DIR = "uploads"
HISTORY_FILE = "generation_history.json"

os.makedirs(UPLOAD_DIR, exist_ok=True)

history_lock = Lock()

def get_unique_filename(extension: str = "png") -> str:
    return f"{uuid.uuid4()}.{extension}"

def save_upload_file(file_content: bytes, filename: str) -> str:
    filepath = os.path.join(UPLOAD_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(file_content)
    return filename

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return []
    return []

def save_history_item(filename: str, prompt: str):
    """Adds an item to history and saves to disk immediately."""
    item = {
        "filename": filename,
        "prompt": prompt,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    with history_lock:
        history = load_history()
        history.append(item)
        with open(HISTORY_FILE, "w") as f:
            json.dump(history, f, indent=2)
    return item

def clear_history_data():
    with history_lock:
        with open(HISTORY_FILE, "w") as f:
            json.dump([], f)

def cleanup_file(filepath: str):
    if os.path.exists(filepath):
        try:
            os.remove(filepath)
        except Exception as e:
            print(f"Error cleaning up file {filepath}: {e}")