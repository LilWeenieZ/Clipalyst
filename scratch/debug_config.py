
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Root is one level up from scratch/
ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT))

print(f"ROOT: {ROOT}")
env_path = ROOT / ".env"
print(f"Env path exists: {env_path.exists()}")

load_dotenv(dotenv_path=env_path)

print(f"ENV GUMROAD_PRODUCT_ID: '{os.getenv('GUMROAD_PRODUCT_ID')}'")
print(f"ENV GUMROAD_ACCESS_TOKEN: '{os.getenv('GUMROAD_ACCESS_TOKEN')}'")

from src import config
print(f"CONFIG GUMROAD_PRODUCT_ID: '{config.GUMROAD_PRODUCT_ID}'")
print(f"CONFIG GUMROAD_ACCESS_TOKEN: '{config.GUMROAD_ACCESS_TOKEN}'")

from src import licence
print(f"LICENCE GUMROAD_PRODUCT_ID: '{licence.GUMROAD_PRODUCT_ID}'")
print(f"LICENCE GUMROAD_ACCESS_TOKEN: '{licence.GUMROAD_ACCESS_TOKEN}'")
