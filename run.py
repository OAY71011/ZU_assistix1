# run.py

from telegram.ext import ApplicationBuilder
from user import get_user_handler
from admin import get_admin_handler, get_main_admin_handler
from config import ADMIN_IDS,BOT_TOKEN  # optional: if needed inside main()



def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Register conversation handlers
    app.add_handler(get_user_handler())
    app.add_handler(get_admin_handler())
    app.add_handler(get_main_admin_handler())

    print("✅ Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
