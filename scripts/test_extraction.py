import sys
from pathlib import Path

from bot.config import RECEIPTS_DIR
from bot.gemini_client import extract_receipt

# Use a file name from the command line, or the newest receipt
if len(sys.argv) > 1:
    image_path = RECEIPTS_DIR / sys.argv[1]
else:
    images = sorted(RECEIPTS_DIR.glob("*.jpg"), key=lambda p: p.stat().st_mtime)
    if not images:
        print("No receipt images found.")
        sys.exit(1)
    image_path = images[-1]

print(f"Testing with: {image_path.name}")

try:
    data = extract_receipt(image_path)
    # Printed here for development only. Use dummy receipts.
    print(data.model_dump_json(indent=2))
except Exception as error:
    print("Extraction failed:", type(error).__name__)
    print(str(error)[:400])