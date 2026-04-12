
import os
import sys
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).resolve().parent / "src"))

from src import licence

print(f"GUMROAD_PRODUCT_ID: '{licence.GUMROAD_PRODUCT_ID}'")
print(f"GUMROAD_ACCESS_TOKEN: '{licence.GUMROAD_ACCESS_TOKEN}'")
