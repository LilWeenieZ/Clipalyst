import sys
import pathlib

# Add repo root to path
repo_root = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo_root))

try:
    from src.licence_config import GUMROAD_PRODUCT_ID, GUMROAD_ACCESS_TOKEN
    print(f"Import src.licence_config successful.")
    print(f"GUMROAD_PRODUCT_ID: {GUMROAD_PRODUCT_ID[:5]}...")
except ImportError as e:
    print(f"Import src.licence_config failed: {e}")

try:
    from src.licence import GUMROAD_PRODUCT_ID as GID
    print(f"Import GUMROAD_PRODUCT_ID from src.licence successful.")
except Exception as e:
    print(f"Import from src.licence failed: {e}")
