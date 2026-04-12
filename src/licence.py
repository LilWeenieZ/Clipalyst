"""
licence.py — Gumroad licence verification for Clipalyst.

This module handles Pro activation by verifying license keys against the
Gumroad API and caching the result locally to support offline usage.
"""

import json
import logging
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────
FREE_LIMIT     = 50     # max clipboard history items for free users
FREE_PIN_LIMIT = 3      # max pinned items for free users

from src.config import DATA_ROOT

# Paths
DATA_DIR = DATA_ROOT / "licence"
KEY_FILE = DATA_DIR / "licence.key"
CACHE_FILE = DATA_DIR / "licence_cache.json"

# Gumroad Config
# We use a dynamic import here to prevent IDEs and static analyzers from flagging 
# 'src.licence_config' as a missing module. This file is only generated at 
# build-time by build.py and is intentionally missing during development.
try:
    import importlib
    _cfg = importlib.import_module("src.licence_config")
    GUMROAD_PRODUCT_ID = _cfg.GUMROAD_PRODUCT_ID
    GUMROAD_ACCESS_TOKEN = _cfg.GUMROAD_ACCESS_TOKEN
    logger.info("Gumroad credentials loaded from bundled configuration.")
except (ImportError, AttributeError):
    # Development fallback if licence_config.py is missing (e.g. after build cleanup)
    from src.config import GUMROAD_PRODUCT_ID, GUMROAD_ACCESS_TOKEN
    if GUMROAD_PRODUCT_ID and GUMROAD_ACCESS_TOKEN:
        logger.info("Gumroad credentials loaded from environment/src.config.")
    else:
        logger.warning("Gumroad credentials not found in bundled config OR environment.")


# ── Internal helpers ──────────────────────────────────────────────────────────

def _verify_with_gumroad(key: str) -> dict:
    """Perform a POST request to Gumroad to verify a license key."""
    if not GUMROAD_PRODUCT_ID:
        logger.error("Gumroad Product ID is missing. Check your configuration or .env file.")
        return {"success": False, "message": "Server configuration error (missing Product ID)"}
    if not GUMROAD_ACCESS_TOKEN:
        logger.error("Gumroad Access Token is missing. Check your configuration or .env file.")
        return {"success": False, "message": "Server configuration error (missing Access Token)"}

    url = "https://api.gumroad.com/v2/licenses/verify"
    params = {
        "product_id": GUMROAD_PRODUCT_ID,
        "license_key": key,
        "increment_uses_count": "false"
    }
    
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Authorization", f"Bearer {GUMROAD_ACCESS_TOKEN}")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")

    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            res_data = json.loads(response.read().decode())
            return res_data
    except urllib.error.HTTPError as err:
        # Gumroad often returns JSON error messages even on 4xx/5xx responses
        try:
            body = err.read().decode()
            res_data = json.loads(body)
            # If it's valid JSON from Gumroad, it usually has 'message' or 'success'
            if isinstance(res_data, dict):
                return res_data
        except Exception:
            pass
        logger.error("Gumroad HTTP Error %s: %s", err.code, err.reason)
        return {"success": False, "message": f"Server returned error {err.code} ({err.reason})"}
    except Exception as exc:
        logger.error("Gumroad API request failed: %s", exc)
        raise exc


def _save_licence(key: str, email: str):
    """Save the key and cache verification info."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    # Save plain text key
    with open(KEY_FILE, "w", encoding="utf-8") as f:
        f.write(key.strip())
        
    # Save cache
    cache = {
        "key": key,
        "email": email,
        "verified_at": datetime.now(timezone.utc).isoformat()
    }
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f)


# ── Public API ────────────────────────────────────────────────────────────────

def init(settings_manager=None) -> None:
    """
    Compatibility initialization. 
    Previously used SettingsManager, now relies on local files.
    """
    # Verify directory exists
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    logger.info("Licence module initialized.")


def activate_licence(key: str) -> dict:
    """
    Activate the application using a Gumroad license key.
    
    Returns:
        dict: {"success": True, "email": ...} or {"success": False, "error": ...}
    """
    try:
        response = _verify_with_gumroad(key)
        if response.get("success"):
            purchase = response.get("purchase", {})
            email = purchase.get("email", "unknown")
            _save_licence(key, email)
            logger.info("Licence activated for %s", email)
            return {"success": True, "email": email}
        else:
            message = response.get("message", "Invalid license key")
            logger.warning("Activation failed: %s", message)
            return {"success": False, "error": message}
    except Exception as exc:
        # Include specific error details for easier troubleshooting
        err_msg = str(exc)
        logger.error("Activation exception: %s", err_msg)
        return {"success": False, "error": f"Connection failed: {err_msg}"}


def is_pro() -> bool:
    """
    Return True if the user has a valid Pro licence.
    Includes a 7-day offline grace period.
    """
    if not KEY_FILE.exists():
        return False

    # Read cache
    if not CACHE_FILE.exists():
        # Key exists but no cache? Try to verify.
        try:
            with open(KEY_FILE, "r", encoding="utf-8") as f:
                key = f.read().strip()
            return activate_licence(key).get("success", False)
        except Exception:
            return False

    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            cache = json.load(f)
        
        verified_at_str = cache.get("verified_at")
        if not verified_at_str:
            return False
            
        verified_at = datetime.fromisoformat(verified_at_str)
        now = datetime.now(timezone.utc)
        
        # 7-day grace period
        if now - verified_at < timedelta(days=7):
            return True
            
        # Stale cache: re-verify
        logger.info("Licence cache stale, re-verifying...")
        key = cache.get("key")
        if not key:
            return False
            
        result = activate_licence(key)
        return result.get("success", False)
        
    except Exception as exc:
        logger.error("Error checking Pro status: %s", exc)
        return False


def deactivate_licence() -> None:
    """Remove the local licence files."""
    try:
        if KEY_FILE.exists():
            KEY_FILE.unlink()
        if CACHE_FILE.exists():
            CACHE_FILE.unlink()
        logger.info("Licence deactivated.")
    except Exception as exc:
        logger.error("Error deactivating licence: %s", exc)


def get_licence_info() -> dict:
    """Return info about the currently active licence."""
    if not is_pro():
        return {"active": False}
        
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            cache = json.load(f)
        return {
            "active": True,
            "email": cache.get("email", "unknown"),
            "verified_at": cache.get("verified_at")
        }
    except Exception:
        return {"active": False}

# Compatibility aliases for old imports (if any)
def activate(key: str, email: str = "") -> tuple[bool, str]:
    """Compatibility wrapper for the old activate function."""
    res = activate_licence(key)
    if res["success"]:
        return True, f"✅ Pro activated! Registered to {res['email']}"
    return False, f"❌ {res['error']}"

def deactivate() -> None:
    """Compatibility wrapper for the old deactivate function."""
    deactivate_licence()
