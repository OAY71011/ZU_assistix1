# admin.py
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import (
    CallbackQueryHandler, CommandHandler, MessageHandler,
    ConversationHandler, ContextTypes, filters
)
from db import (
    get_all_requests, get_waiting_requests, get_request_by_id,
    update_status, update_permission, get_user_requests,
    add_admin, remove_admin, get_admins,
    get_task_list, set_task_list
)
from config import ADMIN_IDS, MAIN_ADMIN_ID

SELECT_ADMIN_ACTION, SELECT_REQ_ACTION, SELECT_REQUEST_ID, SEND_MSG, BROADCAST, CHANGE_STATUS, ADD_ADMIN, REMOVE_ADMIN, SET_TASKS = range(9)

# --- Admin Entry ---
async def admin_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("🚫 You are not authorized to use the admin panel.")
        return ConversationHandler.END

    keyboard = [
        [InlineKeyboardButton("📢 Send Announcement", callback_data="broadcast")],
        [InlineKeyboardButton("📂 View All Requests", callback_data="view_all")],
        [InlineKeyboardButton("🕒 Active Requests", callback_data="active")],
        [InlineKeyboardButton("🔍 Search by Request ID", callback_data="search_req")],
        [InlineKeyboardButton("🔍 Search by User ID", callback_data="search_user")],
        [InlineKeyboardButton("📈 Summary Report", callback_data="report")],
    ]

    if user_id == MAIN_ADMIN_ID:
        keyboard += [
            [InlineKeyboardButton("➕ Add Admin", callback_data="add_admin")],
            [InlineKeyboardButton("➖ Remove Admin", callback_data="remove_admin")],
            [InlineKeyboardButton("📋 Show Admins", callback_data="show_admins")],
            [InlineKeyboardButton("⚙️ Task Types", callback_data="set_tasks")],
        ]

    await update.message.reply_text("🛠 Admin Panel:", reply_markup=InlineKeyboardMarkup(keyboard))
    return SELECT_ADMIN_ACTION

# --- Admin Menu Actions ---
async def handle_admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    action = query.data

    if action == "broadcast":
        await query.message.reply_text("📢 Type the announcement to send to all users:")
        return BROADCAST

    if action == "view_all":
        return await list_requests(query, context, all_requests=True)

    if action == "active":
        return await list_requests(query, context, all_requests=False)

    if action == "search_req":
        await query.message.reply_text("🔍 Enter Request ID:")
        return SELECT_REQUEST_ID

    if action == "search_user":
        await query.message.reply_text("🔍 Enter User ID:")
        return SEND_MSG

    if action == "report":
        rows = get_all_requests()
        stats = {"total": 0, "waiting": 0, "accepted": 0, "done": 0, "cancelled": 0, "denied": 0}
        for r in rows:
            stats["total"] += 1
            stats[r[7]] += 1
        await query.message.reply_text(
            f"📊 Summary:\n"
            f"Total: {stats['total']}\n"
            f"✅ Accepted: {stats['accepted']}\n"
            f"⏳ Waiting: {stats['waiting']}\n"
            f"✅ Done: {stats['done']}\n"
            f"❌ Cancelled: {stats['cancelled']}\n"
            f"🚫 Denied: {stats['denied']}"
        )
        return SELECT_ADMIN_ACTION

    if action == "add_admin":
        await query.message.reply_text("👤 Send User ID to add as admin:")
        return ADD_ADMIN

    if action == "remove_admin":
        await query.message.reply_text("👤 Send Admin ID to remove:")
        return REMOVE_ADMIN

    if action == "show_admins":
        admins = get_admins()
        msg = "👥 Admin List:\n" + "\n".join(str(a) for a in admins)
        await query.message.reply_text(msg)
        return SELECT_ADMIN_ACTION

    if action == "set_tasks":
        current = get_task_list()
        await query.message.reply_text(
            "⚙️ Current Tasks:\n" + "\n".join(current) +
            "\n\nSend new task types (comma separated):"
        )
        return SET_TASKS

# --- Show Requests ---
async def list_requests(query, context, all_requests=True):
    rows = get_all_requests() if all_requests else get_waiting_requests()
    if not rows:
        await query.message.reply_text("📭 No requests found.")
        return SELECT_ADMIN_ACTION

    msg = "📄 Requests:\n\n"
    for r in rows[:20]:
        preview = (r[5][:20] + '...') if len(r[5]) > 20 else r[5]
        msg += f"#{r[0]} | {r[3]} | {r[7]} | {preview} | {'✅' if r[8] else '🚫'}\n"
    msg += "\nSend request ID to manage:"
    await query.message.reply_text(msg)
    return SELECT_REQUEST_ID

# --- View Request Details ---
async def handle_request_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    req_id = update.message.text.strip()
    if not req_id.isdigit():
        await update.message.reply_text("❗ Invalid request ID.")
        return SELECT_REQUEST_ID

    row = get_request_by_id(int(req_id))
    if not row:
        await update.message.reply_text("❌ Not found.")
        return SELECT_REQUEST_ID

    context.user_data["selected_request"] = row

    msg = (
        f"📄 Request #{row[0]}\n"
        f"User ID: {row[1]}\n"
        f"Task: {row[3]}\n"
        f"Status: {row[7]}\n"
        f"Comment: {row[5][:20]}...\n"
        f"Can message admin: {'✅' if row[8] else '🚫'}"
    )
    keyboard = [
        [InlineKeyboardButton("👁 View Full", callback_data="view_full")],
        [InlineKeyboardButton("🔁 Change Status", callback_data="change_status")],
        [InlineKeyboardButton("💬 Message User", callback_data="send_msg")],
        [InlineKeyboardButton("🔒 Toggle Permission", callback_data="toggle_msg")],
        [InlineKeyboardButton("🔙 Back", callback_data="back_admin")]
    ]
    await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
    return SELECT_REQ_ACTION

# --- Request Actions ---
async def handle_request_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    req = context.user_data.get("selected_request")
    if not req:
        await query.message.reply_text("❗ No request selected.")
        return SELECT_ADMIN_ACTION

    if query.data == "view_full":
        await query.message.reply_text(f"💬 Comment:\n{req[5]}")
        if req[6]:
            path = os.path.join("media", req[6])
            if os.path.exists(path):
                await query.message.reply_document(InputFile(path))
        return SELECT_REQ_ACTION

    if query.data == "change_status":
        buttons = [
            [InlineKeyboardButton("✅ Accept", callback_data="accepted")],
            [InlineKeyboardButton("❌ Deny", callback_data="denied")],
            [InlineKeyboardButton("⏳ Waiting", callback_data="waiting")],
            [InlineKeyboardButton("✅ Done", callback_data="done")]
        ]
        await query.message.reply_text("Select new status:", reply_markup=InlineKeyboardMarkup(buttons))
        return CHANGE_STATUS

    if query.data == "send_msg":
        await query.message.reply_text("💬 Type message to user:")
        return SEND_MSG

    if query.data == "toggle_msg":
        update_permission(req[0], 0 if req[8] else 1)
        await query.message.reply_text("🔒 Message permission toggled.")
        return SELECT_ADMIN_ACTION

    if query.data == "back_admin":
        return await admin_start(update, context)

# --- Change Status ---
async def set_new_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    req = context.user_data.get("selected_request")
    update_status(req[0], query.data)
    await query.message.reply_text(f"✅ Status updated to {query.data}")
    return SELECT_ADMIN_ACTION

# --- Message User ---
async def handle_message_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    req = context.user_data.get("selected_request")
    await update.get_bot().send_message(req[1], f"📩 Admin Message:\n{update.message.text}")
    await update.message.reply_text("✅ Message sent to user.")
    return SELECT_ADMIN_ACTION

# --- Broadcast Message ---
async def handle_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = set([r[1] for r in get_all_requests()])
    for uid in users:
        try:
            await update.get_bot().send_message(uid, f"📢 Announcement:\n\n{update.message.text}")
        except:
            continue
    await update.message.reply_text("✅ Sent to all users.")
    return SELECT_ADMIN_ACTION

# --- Admin Management (main only) ---
async def add_new_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.text.strip()
    if uid.isdigit():
        add_admin(int(uid))
        await update.message.reply_text("✅ Admin added.")
    return SELECT_ADMIN_ACTION

async def remove_existing_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.text.strip()
    if uid.isdigit():
        remove_admin(int(uid))
        await update.message.reply_text("✅ Admin removed.")
    return SELECT_ADMIN_ACTION

async def handle_set_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tasks = [t.strip() for t in update.message.text.split(",") if t.strip()]
    set_task_list(tasks)
    await update.message.reply_text("✅ Task types updated.")
    return SELECT_ADMIN_ACTION

# --- Admin Handler ---
def get_admin_handler():
    return ConversationHandler(
        entry_points=[CommandHandler("admin", admin_start)],
        states={
            SELECT_ADMIN_ACTION: [CallbackQueryHandler(handle_admin_menu)],
            BROADCAST: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_broadcast)],
            SELECT_REQUEST_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_request_details)],
            SELECT_REQ_ACTION: [CallbackQueryHandler(handle_request_action)],
            CHANGE_STATUS: [CallbackQueryHandler(set_new_status)],
            SEND_MSG: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message_user)],
            ADD_ADMIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_new_admin)],
            REMOVE_ADMIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, remove_existing_admin)],
            SET_TASKS: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_set_tasks)],
        },
        fallbacks=[],
        allow_reentry=True
    )
from telegram.ext import ConversationHandler, CommandHandler, CallbackQueryHandler, MessageHandler, filters

def get_main_admin_handler():
    return ConversationHandler(
        entry_points=[CommandHandler("madmin", admin_start)],
        states={
            SELECT_ADMIN_ACTION: [CallbackQueryHandler(handle_admin_menu)],
            BROADCAST: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_broadcast)],
            SELECT_REQUEST_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_request_details)],
            SELECT_REQ_ACTION: [CallbackQueryHandler(handle_request_action)],
            CHANGE_STATUS: [CallbackQueryHandler(set_new_status)],
            SEND_MSG: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message_user)],
            ADD_ADMIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_new_admin)],
            REMOVE_ADMIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, remove_existing_admin)],
            SET_TASKS: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_set_tasks)],
        },
        fallbacks=[],
        allow_reentry=True
    )
