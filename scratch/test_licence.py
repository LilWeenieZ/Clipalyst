import os
import sys
import json
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src import licence

class TestLicence(unittest.TestCase):
    def setUp(self):
        # Override data dir for testing
        self.test_data = Path("./scratch/test_data")
        self.test_data.mkdir(parents=True, exist_ok=True)
        licence.DATA_DIR = self.test_data
        licence.KEY_FILE = self.test_data / "licence.key"
        licence.CACHE_FILE = self.test_data / "licence_cache.json"
        
        # Ensure files don't exist
        if licence.KEY_FILE.exists(): licence.KEY_FILE.unlink()
        if licence.CACHE_FILE.exists(): licence.CACHE_FILE.unlink()

    def tearDown(self):
        # Clean up
        if licence.KEY_FILE.exists(): licence.KEY_FILE.unlink()
        if licence.CACHE_FILE.exists(): licence.CACHE_FILE.unlink()
        if self.test_data.exists(): self.test_data.rmdir()

    def test_is_pro_no_files(self):
        self.assertFalse(licence.is_pro())

    def test_is_pro_fresh_cache(self):
        # Create a fresh cache (1 hour ago)
        verified_at = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        with open(licence.KEY_FILE, "w") as f: f.write("TEST-KEY")
        with open(licence.CACHE_FILE, "w") as f:
            json.dump({"key": "TEST-KEY", "email": "test@example.com", "verified_at": verified_at}, f)
        
        self.assertTrue(licence.is_pro())

    def test_is_pro_stale_cache_success(self):
        # Create a stale cache (10 days ago)
        verified_at = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
        with open(licence.KEY_FILE, "w") as f: f.write("STALE-KEY")
        with open(licence.CACHE_FILE, "w") as f:
            json.dump({"key": "STALE-KEY", "email": "test@example.com", "verified_at": verified_at}, f)
        
        # Mock Gumroad verify to return success
        with patch("src.licence._verify_with_gumroad") as mock_verify:
            mock_verify.return_value = {"success": True, "purchase": {"email": "updated@example.com"}}
            self.assertTrue(licence.is_pro())
            mock_verify.assert_called_once_with("STALE-KEY")
            
            # Verify cache was updated
            with open(licence.CACHE_FILE, "r") as f:
                new_cache = json.load(f)
                self.assertEqual(new_cache["email"], "updated@example.com")
                new_date = datetime.fromisoformat(new_cache["verified_at"])
                self.assertLess(datetime.now(timezone.utc) - new_date, timedelta(minutes=1))

    def test_is_pro_stale_cache_fail(self):
        # Create a stale cache (10 days ago)
        verified_at = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
        with open(licence.KEY_FILE, "w") as f: f.write("BAD-KEY")
        with open(licence.CACHE_FILE, "w") as f:
            json.dump({"key": "BAD-KEY", "email": "test@example.com", "verified_at": verified_at}, f)
        
        # Mock Gumroad verify to return failure
        with patch("src.licence._verify_with_gumroad") as mock_verify:
            mock_verify.return_value = {"success": False, "message": "Invalid key"}
            self.assertFalse(licence.is_pro())

    def test_deactivate(self):
        with open(licence.KEY_FILE, "w") as f: f.write("KEY")
        with open(licence.CACHE_FILE, "w") as f: json.dump({}, f)
        
        licence.deactivate_licence()
        self.assertFalse(licence.KEY_FILE.exists())
        self.assertFalse(licence.CACHE_FILE.exists())

if __name__ == "__main__":
    unittest.main()
