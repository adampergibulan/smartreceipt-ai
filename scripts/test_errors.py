import tempfile
from pathlib import Path

from bot.gemini_client import (
    MAX_IMAGE_BYTES,
    ReceiptAnalysisError,
    extract_receipt,
    translate_client_error,
)


class FakeError(Exception):
    """Pretends to be a Google error with a status code."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


results = []


def check(name, expected_kind, action):
    kind = "NO ERROR RAISED"
    message = ""
    try:
        action()
    except ReceiptAnalysisError as error:
        kind = error.kind
        message = error.user_message
    status = "PASS" if kind == expected_kind else "FAIL"
    print(f"[{status}] {name}: expected {expected_kind}, got {kind}")
    if kind == expected_kind:
        print(f"        user sees: {message}")
    results.append(status)


with tempfile.TemporaryDirectory() as folder:
    folder = Path(folder)

    # --- File problems (checked before any Gemini call) ---
    check("Missing file", "missing_file",
          lambda: extract_receipt(folder / "nothing.jpg"))

    gif_file = folder / "photo.gif"
    gif_file.write_bytes(b"GIF89a-fake")
    check("Unsupported format (.gif)", "unsupported_format",
          lambda: extract_receipt(gif_file))

    empty_file = folder / "empty.jpg"
    empty_file.write_bytes(b"")
    check("Empty file", "empty_file",
          lambda: extract_receipt(empty_file))

    fake_file = folder / "fake.jpg"
    fake_file.write_text("this is just text, not an image")
    check("Text renamed to .jpg", "corrupted_file",
          lambda: extract_receipt(fake_file))

    big_file = folder / "big.jpg"
    big_file.write_bytes(b"\xff\xd8\xff" + b"0" * MAX_IMAGE_BYTES)
    check("Oversized file", "too_large",
          lambda: extract_receipt(big_file))


# --- Google error codes (simulated, no real call) ---
def raise_translated(code, message):
    def action():
        raise translate_client_error(FakeError(code, message))
    return action


check("Rate limit (429)", "rate_limit", raise_translated(429, "quota"))
check("Forbidden (403)", "auth_failed", raise_translated(403, "denied"))
check("Bad API key (400)", "auth_failed", raise_translated(400, "API key not valid"))
check("Model not found (404)", "model_not_found", raise_translated(404, "no model"))
check("Bad request (400)", "bad_request", raise_translated(400, "invalid argument"))

print()
print(f"{results.count('PASS')} of {len(results)} passed")