import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
model = os.getenv("GEMINI_MODEL")

if not api_key or not model:
    print("GEMINI_API_KEY or GEMINI_MODEL is missing in .env")
    sys.exit(1)

# Find the newest saved receipt image
receipts_dir = Path(__file__).resolve().parent.parent / "receipts"
images = sorted(receipts_dir.glob("*.jpg"), key=lambda p: p.stat().st_mtime)

if not images:
    print("No receipt images found in the receipts folder.")
    sys.exit(1)

image_path = images[-1]
print(f"Testing with: {image_path.name}")

image_bytes = image_path.read_bytes()
client = genai.Client(api_key=api_key)

prompt = (
    "Is this image a receipt or an invoice? "
    "Which languages can you see on it? Answer in two short sentences."
)

try:
    response = client.models.generate_content(
        model=model,
        contents=[
            prompt,
            types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
        ],
    )
    print("Gemini replied:")
    print(response.text)
except Exception as error:
    # Print only the error type and a short message, never the API key
    print("Gemini request failed:", type(error).__name__)
    print(str(error)[:300])