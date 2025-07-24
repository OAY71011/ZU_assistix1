import sqlite3
from datetime import datetime

DB_NAME = 'tasks.db'


# --- Base Connection ---
def get_connection():
    return sqlite3.connect(DB_NAME)


# --- Initialize All Tables ---
def init_db():
    with get_connection() as conn:
        c = conn.cursor()

        # Requests Table
        c.execute('''
            CREATE TABLE IF NOT EXISTS requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                username TEXT,
                task_type TEXT,
                sub_type TEXT,
                comment TEXT,
                media TEXT,
                status TEXT DEFAULT 'waiting',
                can_message INTEGER DEFAULT 0,
                created_at TEXT
            )
        ''')

        # Admins Table
        c.execute('''
            CREATE TABLE IF NOT EXISTS admins (
                admin_id INTEGER PRIMARY KEY
            )
        ''')

        # Task List Table
        c.execute('''
            CREATE TABLE IF NOT EXISTS task_list (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_name TEXT UNIQUE NOT NULL
            )
        ''')

        conn.commit()


# --- Request Management ---
def add_request(user_id, username, task_type, sub_type, comment, media=None):
    with get_connection() as conn:
        c = conn.cursor()
        c.execute('''
            INSERT INTO requests (user_id, username, task_type, sub_type, comment, media, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, username, task_type, sub_type, comment, media, datetime.now().isoformat()))
        conn.commit()
        return c.lastrowid


def update_status(request_id, status):
    with get_connection() as conn:
        conn.execute("UPDATE requests SET status = ? WHERE id = ?", (status, request_id))


def update_permission(request_id, can_message):
    with get_connection() as conn:
        conn.execute("UPDATE requests SET can_message = ? WHERE id = ?", (can_message, request_id))


def update_comment(request_id, new_comment):
    with get_connection() as conn:
        conn.execute("UPDATE requests SET comment = ? WHERE id = ?", (new_comment, request_id))


def get_request_by_id(request_id):
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM requests WHERE id = ?", (request_id,)).fetchone()
        return row


def get_all_requests():
    with get_connection() as conn:
        return conn.execute("SELECT * FROM requests ORDER BY id DESC").fetchall()


def get_waiting_requests():
    with get_connection() as conn:
        return conn.execute("SELECT * FROM requests WHERE status = 'waiting' ORDER BY id DESC").fetchall()


def get_user_requests(user_id):
    with get_connection() as conn:
        return conn.execute("SELECT * FROM requests WHERE user_id = ? ORDER BY id DESC", (user_id,)).fetchall()


def get_user_from_request(req_id):
    with get_connection() as conn:
        row = conn.execute("SELECT user_id FROM requests WHERE id = ?", (req_id,)).fetchone()
        return row[0] if row else None


# --- Admin Management ---
def add_admin(admin_id: int):
    with get_connection() as conn:
        conn.execute("INSERT OR IGNORE INTO admins (admin_id) VALUES (?)", (admin_id,))


def remove_admin(admin_id: int):
    with get_connection() as conn:
        conn.execute("DELETE FROM admins WHERE admin_id = ?", (admin_id,))


def get_admins():
    with get_connection() as conn:
        rows = conn.execute("SELECT admin_id FROM admins").fetchall()
        return [r[0] for r in rows]


def is_admin(user_id: int):
    return user_id in get_admins()


# --- Task List Management ---
def get_task_list():
    with get_connection() as conn:
        rows = conn.execute("SELECT task_name FROM task_list ORDER BY id").fetchall()
        return [r[0] for r in rows]


def add_task(task_name: str):
    with get_connection() as conn:
        conn.execute("INSERT INTO task_list (task_name) VALUES (?)", (task_name,))


def remove_task(task_name: str):
    with get_connection() as conn:
        conn.execute("DELETE FROM task_list WHERE task_name = ?", (task_name,))

def set_task_list(task_names: list[str]):
    with get_connection() as conn:
        conn.execute("DELETE FROM task_list")
        conn.executemany("INSERT INTO task_list (task_name) VALUES (?)", [(t,) for t in task_names])
