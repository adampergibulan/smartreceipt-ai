import os
from pathlib import Path
from dotenv import load_dotenv

# Read the variables stored in the .env file
load_dotenv()

# Get the Telegram bot token from the environment
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Stop early with a clear message if the token is missing
if not TELEGRAM_BOT_TOKEN:
    raise ValueError(
        "TELEGRAM_BOT_TOKEN is missing. Check that your .env file exists "
        "and contains TELEGRAM_BOT_TOKEN=your_token"
    )

# Authorized Telegram user IDs, e.g. AUTHORIZED_USER_IDS=111,222
_raw_ids = os.getenv("AUTHORIZED_USER_IDS", "")
AUTHORIZED_USER_IDS = set()
for item in _raw_ids.split(","):
    item = item.strip()
    if item.isdigit():
        AUTHORIZED_USER_IDS.add(int(item))

# Stop early if nobody is authorized (safer than allowing everyone)
if not AUTHORIZED_USER_IDS:
    raise ValueError(
        "AUTHORIZED_USER_IDS is missing or invalid. Add it to your .env file, "
        "for example: AUTHORIZED_USER_IDS=123456789"
    )

# Folder where receipt images are saved (created automatically if missing)
BASE_DIR = Path(__file__).resolve().parent.parent
RECEIPTS_DIR = BASE_DIR / "receipts"
RECEIPTS_DIR.mkdir(exist_ok=True)

# Gemini AI settings
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")

if not GEMINI_API_KEY:
    raise ValueError(
        "GEMINI_API_KEY is missing. Add it to your .env file."
    )