import sys

from bot.config import RECEIPTS_DIR
from bot.gemini_client import ReceiptAnalysisError, extract_receipt
from bot.validation import validate_receipt

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
    result = validate_receipt(data)

    print(f"Supplier: {data.supplier_name}")
    print(f"Date: {result.receipt_date} ({result.date_source})")
    print(f"Items: {len(data.items)}")
    print(f"Grand total: {data.grand_total}")
    print(f"Review required: {result.review_required}")
    for note in result.review_notes:
        print(f"  REVIEW: {note}")
    for note in result.info_notes:
        print(f"  info: {note}")
except ReceiptAnalysisError as error:
    print("Failed:", error.kind)
    print("User would see:", error.user_message)
except Exception as error:
    print("Unexpected failure:", type(error).__name__)