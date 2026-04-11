import sys
import os
from unittest.mock import MagicMock, patch
import json

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.tagger import AITagger
from src.database import db

def test_tagger_logic():
    print("--- Testing AITagger Logic with Mocks ---")
    
    # Mock database
    db.get_item_content = MagicMock(return_value="Check out this cool URL: https://example.com")
    db.update_ai_tags = MagicMock()
    
    # Mock Anthropic Client
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text='{"type": "url", "label": "Example URL link"}')]
    mock_client.messages.create.return_value = mock_response
    
    with patch('src.tagger.Anthropic', return_value=mock_client), \
         patch('src.tagger.load_dotenv'):
        
        tagger = AITagger()
        tagger.client = mock_client # Ensure it's set
        
        print("Processing item 1...")
        tagger._process_item(1)
        
        # Verify DB calls
        db.get_item_content.assert_called_with(1)
        
        # Verify API call
        mock_client.messages.create.assert_called_once()
        call_args = mock_client.messages.create.call_args[1]
        print(f"Model used: {call_args['model']}")
        print(f"Prompt sent: {call_args['messages'][0]['content'][:100]}...")
        
        # Verify DB update
        db.update_ai_tags.assert_called_with(1, "url", "Example URL link")
        print("Success: DB updated with correct tags.")

    print("--- Test Complete ---")

if __name__ == "__main__":
    test_tagger_logic()
