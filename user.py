# user.py

import os
from uuid import uuid4
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    CallbackQueryHandler, CommandHandler, MessageHandler,
    ConversationHandler, ContextTypes, filters
)
from db import (
    add_request, get_request_by_id, get_user_requests,
    update_comment, update_status
)

SELECT_ACTION, SELECT_TYPE, COMMENT, MEDIA, CONFIRM, CHECK_ACTION, SELECT_BY_ID, FOLLOWUP = range(8)

TASK_TYPES = ["Software Task", "Write Paper", "Make Presentation", "Other"]
MEDIA_DIR = "media"
os.makedirs(MEDIA_DIR, exist_ok=True)

WELCOME_MSG = "👋 أهلا بك في ZU Assistix! كيف يمكنني مساعدتك؟"

# --- ENTRY ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("➕ New Request", callback_data="new_request")],
        [InlineKeyboardButton("📂 Check Request", callback_data="check_request")]
    ]
    message = update.message or update.callback_query.message
    await message.reply_text(WELCOME_MSG, reply_markup=InlineKeyboardMarkup(keyboard))

    return SELECT_ACTION


# --- MAIN MENU SELECTION ---
async def select_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    choice = query.data

    if choice == "new_request":
        keyboard = [[InlineKeyboardButton(t, callback_data=t)] for t in TASK_TYPES]
        keyboard.append([InlineKeyboardButton("🔙 Go Back", callback_data="back_main")])
        await query.message.reply_text("📝 Choose request type:", reply_markup=InlineKeyboardMarkup(keyboard))
        return SELECT_TYPE

    elif choice == "check_request":
        keyboard = [
            [InlineKeyboardButton("📜 Request History", callback_data="history")],
            [InlineKeyboardButton("📌 Active Requests", callback_data="active")],
            [InlineKeyboardButton("🔍 Check by ID", callback_data="by_id")],
            [InlineKeyboardButton("🔙 Go Back", callback_data="back_main")]
        ]
        await query.message.reply_text("📂 Choose option:", reply_markup=InlineKeyboardMarkup(keyboard))
        return CHECK_ACTION


# --- TYPE SELECT ---
async def select_task_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "back_main":
        return await start(query, context)

    context.user_data["task_type"] = query.data
    await query.message.reply_text("✍️ Please write your comment:")
    return COMMENT


# --- RECEIVE COMMENT ---
async def receive_comment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["comment"] = update.message.text
    await update.message.reply_text("📎 Upload media (or type 'skip'):")
    return MEDIA


# --- MEDIA HANDLING ---
async def receive_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file = None
    file_ext = ".bin"

    if update.message.photo:
        file = update.message.photo[-1]
        file_ext = ".jpg"
    elif update.message.document:
        file = update.message.document
        file_ext = os.path.splitext(file.file_name)[-1]
    elif update.message.voice:
        file = update.message.voice
        file_ext = ".ogg"

    if not file:
        await update.message.reply_text("❗ Unsupported file. Try again or type 'skip'.")
        return MEDIA

    tg_file = await file.get_file()
    file_name = f"{uuid4()}{file_ext}"
    await tg_file.download_to_drive(os.path.join(MEDIA_DIR, file_name))
    context.user_data["media"] = file_name

    return await show_submit_options(update, context)

async def skip_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["media"] = None
    return await show_submit_options(update, context)

# --- SHOW CONFIRM ---
async def show_submit_options(update: Update, context: ContextTypes.DEFAULT_TYPE):
    buttons = [
        [
            InlineKeyboardButton("✅ Submit", callback_data="submit"),
            InlineKeyboardButton("✏️ Edit", callback_data="edit"),
            InlineKeyboardButton("❌ Cancel", callback_data="cancel")
        ]
    ]
    await update.message.reply_text("📤 What do you want to do?", reply_markup=InlineKeyboardMarkup(buttons))
    return CONFIRM


# --- SUBMIT ---
async def handle_submission(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = query.from_user
    task_type = context.user_data.get("task_type")
    comment = context.user_data.get("comment")
    media = context.user_data.get("media")

    req_id = add_request(user.id, user.username or user.first_name, task_type, None, comment, media)
    await query.message.reply_text(
        f"✅ Submitted! Your request ID is #{req_id}.\n\n"
        f"📝 Type: {task_type}\n"
        f"📎 Media: {'Attached' if media else 'None'}"
    )
    return await start(update, context)

async def edit_comment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.message.reply_text("✏️ Enter your updated comment:")
    return COMMENT

async def cancel_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.message.reply_text("❌ Request canceled.")
    return await start(update, context)



# --- CHECK MENU OPTIONS ---
async def check_options(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    choice = query.data

    if choice == "back_main":
        return await start(query, context)
    user_id = query.from_user.id

    rows = get_user_requests(user_id)
    if not rows:
        await query.message.reply_text("📭 No requests found.")
        return CHECK_ACTION

    if choice == "active":
        rows = [r for r in rows if r[7] == "waiting" or r[7] == "accepted"]
        title = "🕒 Active Requests"
    else:
        title = "📜 Request History"

    msg = title + ":\n\n"
    msg += "ID | Task | Status | Comment (preview) | Msg?\n"
    for r in rows:
        preview = (r[5][:20] + '...') if len(r[5]) > 20 else r[5]
        msg += f"#{r[0]} | {r[3]} | {r[7]} | {preview} | {'✅' if r[8] else '🚫'}\n"

    msg += "\n🔍 To view/edit/cancel, send the request ID (e.g., 3)"
    await query.message.reply_text(msg)
    return SELECT_BY_ID


# --- HANDLE ID SELECTION ---
async def handle_request_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if not text.isdigit():
        await update.message.reply_text("❗ Please send a valid request ID.")
        return SELECT_BY_ID

    req_id = int(text)
    row = get_request_by_id(req_id)
    if not row or row[1] != update.effective_user.id:
        await update.message.reply_text("❌ Request not found or not yours.")
        return SELECT_BY_ID

    # 🚫 Block cancelled requests
    if row[7] == "cancelled":
        await update.message.reply_text("🚫 You cannot view or edit cancelled requests.")
        return await start(update, context)

    context.user_data["selected_id"] = req_id
    context.user_data["selected_request"] = row
    context.user_data["can_message"] = row[8]

    msg = (
        f"📄 Request #{row[0]}\n"
        f"📝 Type: {row[3]}\n"
        f"📌 Status: {row[7]}\n"
        f"💬 Comment: {row[5]}\n"
        f"📎 Media: {'Attached' if row[6] else 'None'}\n"
        f"📨 Can message admin: {'✅' if row[8] else '🚫'}"
    )

    buttons = [
        [InlineKeyboardButton("✏️ Edit Comment", callback_data="edit_comment")],
        [InlineKeyboardButton("❌ Cancel Request", callback_data="cancel_request")],
    ]
    if row[8]:
        buttons.append([InlineKeyboardButton("💬 Send Message to Admin", callback_data="send_message")])
    buttons.append([InlineKeyboardButton("🔙 Go Back", callback_data="back_main")])

    await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(buttons))
    return FOLLOWUP



# --- FOLLOWUP ACTIONS ---
async def handle_followup_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    action = query.data
    req = context.user_data.get("selected_request")

    if not req:
        await query.message.reply_text("⚠️ No request selected.")
        return SELECT_ACTION

    status = req[7]  # status is at index 7 in the DB row

    if status == "cancelled" and action in ["edit_comment", "send_message"]:
        await query.message.reply_text("🚫 This request is cancelled and cannot be modified.")
        return SELECT_ACTION

    if action == "edit_comment":
        await query.message.reply_text("✏️ Send your updated comment:")
        return COMMENT

    elif action == "send_message":
        await query.message.reply_text("💬 Type your message to send to the admin:")
        return FOLLOWUP

    elif action == "cancel_request":
        update_status(req[0], "cancelled")
        await query.message.reply_text("❌ Request has been cancelled.")
        return await start(update, context)

    return SELECT_ACTION


async def handle_user_message_to_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    req_id = context.user_data.get("selected_id")
    user = update.effective_user
    msg = update.message.text

    from run import ADMIN_IDS  # dynamically import to avoid circular import
    for admin_id in ADMIN_IDS:
        await update.get_bot().send_message(
            admin_id,
            f"📨 Message from @{user.username or user.first_name} (Request #{req_id}):\n{msg}"
        )
    await update.message.reply_text("✅ Message sent to admin.")
    return FOLLOWUP


# --- ConversationHandler ---
def get_user_handler():
    return ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            SELECT_ACTION: [CallbackQueryHandler(select_action)],
            SELECT_TYPE: [CallbackQueryHandler(select_task_type)],
            COMMENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_comment)],
            MEDIA: [
                MessageHandler(filters.Document.ALL | filters.PHOTO | filters.VOICE, receive_media),
                MessageHandler(filters.TEXT & filters.Regex("(?i)^skip$"), skip_media)
            ],
            CONFIRM: [
                CallbackQueryHandler(handle_submission, pattern="^submit$"),
                CallbackQueryHandler(edit_comment, pattern="^edit$"),
                CallbackQueryHandler(cancel_request, pattern="^cancel$")
            ],
            CHECK_ACTION: [CallbackQueryHandler(check_options)],
            SELECT_BY_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_request_id)],
            FOLLOWUP: [
                CallbackQueryHandler(handle_followup_buttons),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_user_message_to_admin)
            ]
        },
        fallbacks=[],
        allow_reentry=True
    )
