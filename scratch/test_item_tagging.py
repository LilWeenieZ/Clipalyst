import sys
import os
import time
from dotenv import load_dotenv

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Load .env from venv if not in root
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "venv", ".env"))

from src.tagger import tagger
from src.database import db

def test_real_tagging():
    print("--- Real API Test: Tagging Item 1 ---")
    
    # 1. Check current state of item 1
    content = db.get_item_content(1)
    if not content:
        print("Error: Item 1 not found in DB.")
        return
        
    print(f"Item 1 content: {content}")
    
    # Reset tags for testing
    print("Resetting tags for item 1...")
    db.update_ai_tags(1, None, None)
    
    # 2. Start tagger
    print("Starting AITagger...")
    tagger.start()
    
    # 3. Queue item 1
    print("Queueing item 1 for tagging...")
    tagger.tag_item(1)
    
    # 4. Wait for processing (give it up to 10 seconds)
    print("Waiting for AI response (max 10s)...")
    success = False
    for i in range(10):
        time.sleep(1)
        # Check DB
        with db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT content_type, ai_label FROM clipboard_items WHERE id = 1")
            row = cursor.fetchone()
            if row and row['content_type'] and row['ai_label']:
                print(f"Found tags! Type: {row['content_type']}, Label: {row['ai_label']}")
                success = True
                break
            else:
                print(f"Polling... {i+1}s")

    # 5. Stop tagger
    print("Stopping AITagger...")
    tagger.stop()
    
    if success:
        print("\nSUCCESS: Item 1 was successfully tagged by AI.")
    else:
        print("\nFAILURE: Item 1 was not tagged (check .env key and internet).")

if __name__ == "__main__":
    test_real_tagging()
