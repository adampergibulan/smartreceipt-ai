import asyncio
import uuid
from datetime import datetime

from telegram import Update
from telegram.error import TelegramError
from telegram.ext import ContextTypes

from bot.config import AUTHORIZED_USER_IDS, RECEIPTS_DIR
from bot.formatter import build_receipt_message, split_message
from bot.gemini_client import ReceiptAnalysisError, extract_receipt
from bot.validation import validate_receipt


def is_authorized(update: Update) -> bool:
    """Return True if the sender's Telegram user ID is in the allowed list."""
    user = update.effective_user
    return user is not None and user.id in AUTHORIZED_USER_IDS


def make_receipt_filename() -> str:
    """Create a unique filename like receipt_20261023_a1b2c3d4.jpg"""
    date_part = datetime.now().strftime("%Y%m%d")
    unique_part = uuid.uuid4().hex[:8]
    return f"receipt_{date_part}_{unique_part}.jpg"


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Runs when the user sends /start to the bot."""
    user = update.effective_user

    if not is_authorized(update):
        print(f"Unauthorized /start from user ID {user.id}")
        await update.message.reply_text(
            "⛔ Sorry, you are not authorized to use this bot.\n"
            f"Your Telegram ID is {user.id}. "
            "Please send it to the administrator to request access."
        )
        return

    message = (
        f"Hello {user.first_name}! 👋\n\n"
        "Welcome to SmartReceipt AI.\n"
        "Send me a photo of your receipt and I will read it for you."
    )
    await update.message.reply_text(message)


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Runs when the user sends a photo to the bot."""
    user = update.effective_user

    # Authorization check comes FIRST, before touching the photo
    if not is_authorized(update):
        print(f"Unauthorized photo rejected from user ID {user.id}")
        await update.message.reply_text(
            "⛔ You are not authorized to upload receipts."
        )
        return

    # Telegram gives several sizes. The last one is the largest.
    photo = update.message.photo[-1]

    # Build a unique filename and the full save location
    filename = make_receipt_filename()
    save_path = RECEIPTS_DIR / filename

    try:
        # Download the photo from Telegram and save it on this laptop
        telegram_file = await photo.get_file()
        await telegram_file.download_to_drive(save_path)
    except TelegramError as error:
        print(f"Telegram error while downloading: {error}")
        await update.message.reply_text(
            "⚠️ Sorry, I could not download your image from Telegram.\n"
            "Please try sending it again."
        )
        return
    except OSError as error:
        print(f"File error while saving: {error}")
        await update.message.reply_text(
            "⚠️ Sorry, something went wrong while saving your receipt.\n"
            "Please contact the administrator."
        )
        return

    print(f"Saved receipt from {user.first_name}: {filename}")

    await update.message.reply_text(
        "✅ Receipt image received and saved successfully!\n"
        f"Filename: {filename}\n\n"
        "⏳ Analysing the receipt, please wait..."
    )

    # --- Phase 3: analyse the SAVED image with Gemini ---
    try:
        # Run the slow AI call in a background thread so the bot stays responsive
        data = await asyncio.to_thread(extract_receipt, save_path)
        result = validate_receipt(data)
        message = build_receipt_message(data, result)
    except ReceiptAnalysisError as error:
        # Expected problems. The user message is safe to show.
        print(f"Analysis failed for {filename}: {error.kind}")
        await update.message.reply_text(
            f"⚠️ {error.user_message}\n\n"
            "Your image was saved. You can send it again or send a clearer photo."
        )
        return
    except Exception as error:
        # Anything unexpected. Log only the error type, never details.
        print(f"Unexpected analysis error for {filename}: {type(error).__name__}")
        await update.message.reply_text(
            "⚠️ Something went wrong while analysing your receipt.\n"
            "Your image was saved. Please try again later."
        )
        return

    print(f"Analysis finished for {filename}: review_required={result.review_required}")

    # Send the summary. Long summaries are split to fit Telegram's limit.
    try:
        for part in split_message(message):
            await update.message.reply_text(part)
    except TelegramError as error:
        print(f"Telegram error while sending the summary: {type(error).__name__}")


async def handle_unsupported(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Runs when the user sends anything that is not a photo or a command."""
    user = update.effective_user

    # Strangers get the same rejection, with no extra information
    if not is_authorized(update):
        print(f"Unauthorized message rejected from user ID {user.id}")
        await update.message.reply_text(
            "⛔ You are not authorized to use this bot."
        )
        return

    print(f"Unsupported message type from {user.first_name}")
    await update.message.reply_text(
        "❌ Unsupported file type.\n"
        "Please send your receipt as a normal photo (not as a file or PDF)."
    )