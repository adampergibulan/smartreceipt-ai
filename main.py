from telegram.ext import Application, CommandHandler, MessageHandler, filters

from bot.config import TELEGRAM_BOT_TOKEN
from bot.handlers import start_command, handle_photo, handle_unsupported


def main():
    # Build the bot application using our token
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Connect the /start command to its handler function
    app.add_handler(CommandHandler("start", start_command))

    # Connect photo messages to the photo handler
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    # Anything that is not a photo or a command gets a polite rejection
    app.add_handler(MessageHandler(~filters.PHOTO & ~filters.COMMAND, handle_unsupported))

    print("Bot is running... Press Ctrl+C to stop.")

    # Keep checking Telegram for new messages
    app.run_polling()


if __name__ == "__main__":
    main()