import time
from pathlib import Path

from google import genai
from google.genai import errors, types

from bot.config import GEMINI_API_KEY, GEMINI_MODEL
from bot.schemas import ReceiptData

# Image types we allow
MIME_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}

# Retry settings for temporary Google overload (503) errors
MAX_ATTEMPTS = 3

PROMPT = """You are extracting data from a purchase receipt or supplier invoice.
The text may be in English, Bahasa Melayu, Chinese, or a mix of languages.

Rules:
- Only report what is clearly printed. Never guess or invent values.
- If a value is missing, unreadable, or unclear, use null.
- Never use 0 for a missing value.
- Copy item names exactly as printed. Do not translate or rename them.
- Do not calculate totals, quantities, or prices yourself.
  Only copy numbers that are printed on the receipt.
- Numbers must not include currency symbols or thousands separators.
- Use currency "MYR" only if RM or MYR is clearly printed. Otherwise null.
- If the image is not a receipt or invoice, set is_receipt to false.
- If the image is too blurry to read, set image_quality to "unreadable".
"""

# One client, reused for every request
client = genai.Client(api_key=GEMINI_API_KEY)


def extract_receipt(image_path: Path) -> ReceiptData:
    """Send a saved receipt image to Gemini and return structured data."""
    mime_type = MIME_TYPES.get(image_path.suffix.lower())
    if mime_type is None:
        raise ValueError("Unsupported image format")

    image_bytes = image_path.read_bytes()

    response = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=[
                    PROMPT,
                    types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                ],
                config={
                    "response_mime_type": "application/json",
                    "response_json_schema": ReceiptData.model_json_schema(),
                },
            )
            break
        except errors.ServerError:
            # Google is busy (like the 503 you saw). Wait, then try again.
            if attempt == MAX_ATTEMPTS:
                raise
            time.sleep(3 * attempt)

    # Check the JSON against our schema. Raises an error if it doesn't match.
    return ReceiptData.model_validate_json(response.text)
