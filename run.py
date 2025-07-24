# run.py
import threading
from flask import Flask
from telegram.ext import ApplicationBuilder
from user import get_user_handler
from admin import get_admin_handler
from config import BOT_TOKEN, ADMIN_IDS
from db import init_db

# --- Flask App Setup ---
# This part runs a simple web page.
app = Flask(__name__)

@app.route('/')
def index():
    return "Bot is alive!"

# --- Telegram Bot Setup ---
def run_bot():
    # Initialize the database
    init_db()
    
    # Build the bot application
    bot_app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Add ADMIN_IDS to the bot's data context for global access
    bot_app.bot_data['admin_ids'] = ADMIN_IDS

    # Register conversation handlers
    bot_app.add_handler(get_user_handler())
    bot_app.add_handler(get_admin_handler())

    print("✅ Bot is polling...")
    # Start the bot
    bot_app.run_polling()

# --- Main Execution ---
if __name__ == "__main__":
    # Run the bot in a separate thread
    bot_thread = threading.Thread(target=run_bot)
    bot_thread.start()
    
    # Run the Flask web server
    # The host must be '0.0.0.0' to be reachable by Render
    # The port is automatically chosen by Render
    app.run(host='0.0.0.0', port=10000)
