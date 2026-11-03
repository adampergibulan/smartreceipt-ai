import time
from pathlib import Path

import httpx
from google import genai
from google.genai import errors, types
from pydantic import ValidationError

from bot.config import GEMINI_API_KEY, GEMINI_MODEL
from bot.schemas import ReceiptData

# Image types we allow
MIME_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}

MAX_IMAGE_BYTES = 10 * 1024 * 1024   # 10 MB
MAX_ATTEMPTS = 3                     # for temporary Google problems only
REQUEST_TIMEOUT_MS = 45_000          # 45 seconds, in milliseconds

PROMPT = """You are extracting data from a purchase receipt or supplier invoice.
The text may be in English, Bahasa Melayu, Chinese, or a mix of languages.

Rules:
- Only report what is clearly printed. Never guess or invent values.
- If a value is missing, unreadable, or unclear, use null.
- Never use 0 for a missing value.
- Copy item names exactly as printed, character for character. Keep the
  original capitalization, spelling mistakes, spacing, and brackets.
  Do not translate, rename, correct, or change the case of item names.
- Do not calculate totals, quantities, or prices yourself.
  Only copy numbers that are printed on the receipt.
- Numbers must not include currency symbols or thousands separators.
- Use currency "MYR" only if RM or MYR is clearly printed. Otherwise null.
- If the image is not a receipt or invoice, set is_receipt to false.
- If the image is too blurry to read, set image_quality to "unreadable".
"""

# One client, reused for every request
client = genai.Client(
    api_key=GEMINI_API_KEY,
    http_options=types.HttpOptions(timeout=REQUEST_TIMEOUT_MS),
)


class ReceiptAnalysisError(Exception):
    """A problem analysing a receipt.

    kind         - short code for the developer's terminal log
    user_message - friendly text that is safe to show in Telegram
    """

    def __init__(self, kind: str, user_message: str):
        super().__init__(kind)
        self.kind = kind
        self.user_message = user_message


def looks_like_image(data: bytes, mime_type: str) -> bool:
    """Check the first bytes of the file match the claimed image type."""
    if mime_type == "image/jpeg":
        return data.startswith(b"\xff\xd8\xff")
    if mime_type == "image/png":
        return data.startswith(b"\x89PNG\r\n\x1a\n")
    if mime_type == "image/webp":
        return data[:4] == b"RIFF" and data[8:12] == b"WEBP"
    return False


def load_image(image_path: Path):
    """Check the saved image file and return (bytes, mime_type)."""
    if not image_path.is_file():
        raise ReceiptAnalysisError(
            "missing_file",
            "I could not find the saved image. Please send it again.",
        )

    mime_type = MIME_TYPES.get(image_path.suffix.lower())
    if mime_type is None:
        raise ReceiptAnalysisError(
            "unsupported_format",
            "This image format is not supported. "
            "Please send a JPG, PNG or WEBP photo.",
        )

    try:
        size = image_path.stat().st_size
        if size == 0:
            raise ReceiptAnalysisError(
                "empty_file",
                "The image file is empty. Please send the photo again.",
            )
        if size > MAX_IMAGE_BYTES:
            raise ReceiptAnalysisError(
                "too_large",
                "This image is too large (maximum 10 MB). "
                "Please send a smaller photo.",
            )
        data = image_path.read_bytes()
    except OSError:
        raise ReceiptAnalysisError(
            "unreadable_file",
            "I could not open the saved image. Please send it again.",
        )

    if not looks_like_image(data, mime_type):
        raise ReceiptAnalysisError(
            "corrupted_file",
            "The image file looks damaged or is not a real image. "
            "Please send it again.",
        )

    return data, mime_type


def translate_client_error(error) -> ReceiptAnalysisError:
    """Turn a Google 4xx error into our own error with a safe message."""
    code = getattr(error, "code", None)
    text = str(error).lower()

    if code == 429:
        return ReceiptAnalysisError(
            "rate_limit",
            "The AI service is busy or the usage limit was reached. "
            "Please try again in a few minutes.",
        )
    if code in (401, 403) or (code == 400 and "api key" in text):
        return ReceiptAnalysisError(
            "auth_failed",
            "The AI service is not set up correctly. "
            "Please contact the administrator.",
        )
    if code == 404:
        return ReceiptAnalysisError(
            "model_not_found",
            "The AI service is not set up correctly. "
            "Please contact the administrator.",
        )
    if code == 400:
        return ReceiptAnalysisError(
            "bad_request",
            "The AI service could not process this image. "
            "Please try a clearer photo.",
        )
    return ReceiptAnalysisError(
        "api_error",
        "The AI service returned an error. Please try again later.",
    )


def extract_receipt(image_path: Path) -> ReceiptData:
    """Send a saved receipt image to Gemini and return validated data.
    Raises ReceiptAnalysisError for every expected problem."""
    image_bytes, mime_type = load_image(image_path)

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
        except errors.ClientError as error:
            # Problems retrying cannot fix (bad key, rate limit, bad request)
            raise translate_client_error(error)
        except (errors.ServerError, httpx.TransportError) as error:
            # Temporary problem (Google busy, network, timeout). Try again.
            if attempt < MAX_ATTEMPTS:
                time.sleep(3 * attempt)
                continue
            if isinstance(error, httpx.TimeoutException):
                raise ReceiptAnalysisError(
                    "timeout",
                    "The AI service took too long to answer. "
                    "Please try again in a moment.",
                )
            raise ReceiptAnalysisError(
                "service_unavailable",
                "The AI service is temporarily unavailable. "
                "Please try again in a few minutes.",
            )
        except errors.APIError:
            raise ReceiptAnalysisError(
                "api_error",
                "The AI service returned an error. Please try again later.",
            )

    # Check that the reply is valid JSON in our expected structure
    text = getattr(response, "text", None)
    if not text:
        raise ReceiptAnalysisError(
            "invalid_response",
            "I could not understand the AI result. "
            "Please try again or send a clearer photo.",
        )
    try:
        return ReceiptData.model_validate_json(text)
    except ValidationError:
        raise ReceiptAnalysisError(
            "invalid_response",
            "I could not understand the AI result. "
            "Please try again or send a clearer photo.",
        )