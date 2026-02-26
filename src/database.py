import sqlite3
import json
import os
from datetime import datetime
from typing import Any


DB_PATH = os.path.join(os.path.dirname(__file__), "..", "kaziai.db")


def get_db() -> sqlite3.Connection:
    """Get a database connection with row factory."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    """Create database tables if they don't exist, and run migrations."""
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            name TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            company TEXT NOT NULL,
            location TEXT DEFAULT '',
            url TEXT DEFAULT '',
            source TEXT DEFAULT '',
            tags TEXT DEFAULT '[]',
            salary_min INTEGER,
            salary_max INTEGER,
            saved_at TEXT NOT NULL,
            notes TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER REFERENCES jobs(id),
            status TEXT DEFAULT 'saved',
            jd_text TEXT DEFAULT '',
            resume_used TEXT DEFAULT '',
            analysis TEXT DEFAULT '',
            cover_letter TEXT DEFAULT '',
            interview_prep TEXT DEFAULT '',
            applied_at TEXT,
            updated_at TEXT NOT NULL,
            notes TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS analyses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            application_id INTEGER REFERENCES applications(id),
            agent_name TEXT NOT NULL,
            output TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER REFERENCES conversations(id) ON DELETE CASCADE,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
    """)
    conn.commit()

    # Migration: add conversation_id column if it doesn't exist (upgrading from old schema)
    cols = [row["name"] for row in conn.execute("PRAGMA table_info(chat_history)").fetchall()]
    if "conversation_id" not in cols:
        conn.execute("ALTER TABLE chat_history ADD COLUMN conversation_id INTEGER REFERENCES conversations(id) ON DELETE CASCADE")
        conn.commit()

    # Migration: add user_id column to conversations if it doesn't exist
    conv_cols = [row["name"] for row in conn.execute("PRAGMA table_info(conversations)").fetchall()]
    if "user_id" not in conv_cols:
        conn.execute("ALTER TABLE conversations ADD COLUMN user_id INTEGER REFERENCES users(id)")
        conn.commit()

    # Migration: add google_id column to users if it doesn't exist
    user_cols = [row["name"] for row in conn.execute("PRAGMA table_info(users)").fetchall()]
    if "google_id" not in user_cols:
        conn.execute("ALTER TABLE users ADD COLUMN google_id TEXT")
        conn.commit()

    # Migrate orphaned messages (those without a conversation_id) into a "Previous Chat" conversation
    orphan = conn.execute("SELECT COUNT(*) as cnt FROM chat_history WHERE conversation_id IS NULL").fetchone()
    if orphan["cnt"] > 0:
        now = datetime.now().isoformat()
        cursor = conn.execute(
            "INSERT INTO conversations (title, created_at, updated_at) VALUES (?, ?, ?)",
            ("Previous Chat", now, now),
        )
        conv_id = cursor.lastrowid
        conn.execute("UPDATE chat_history SET conversation_id = ? WHERE conversation_id IS NULL", (conv_id,))
        conn.commit()

    conn.close()


# --- User CRUD ---

def create_user(email: str, password_hash: str | None, name: str, google_id: str | None = None) -> int:
    """Create a new user and return their ID."""
    conn = get_db()
    now = datetime.now().isoformat()
    cursor = conn.execute(
        "INSERT INTO users (email, password_hash, name, created_at, google_id) VALUES (?, ?, ?, ?, ?)",
        (email, password_hash or "", name, now, google_id),
    )
    conn.commit()
    user_id = cursor.lastrowid
    conn.close()
    return user_id


def get_user_by_google_id(google_id: str) -> dict | None:
    """Get a user by Google ID."""
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE google_id = ?", (google_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def link_google_id(user_id: int, google_id: str) -> None:
    """Link a Google ID to an existing user account."""
    conn = get_db()
    conn.execute("UPDATE users SET google_id = ? WHERE id = ?", (google_id, user_id))
    conn.commit()
    conn.close()


def get_user_by_email(email: str) -> dict | None:
    """Get a user by email."""
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_by_id(user_id: int) -> dict | None:
    """Get a user by ID."""
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


# --- Conversation CRUD ---

def create_conversation(title: str, user_id: int | None = None) -> int:
    """Create a new conversation and return its ID."""
    conn = get_db()
    now = datetime.now().isoformat()
    cursor = conn.execute(
        "INSERT INTO conversations (title, created_at, updated_at, user_id) VALUES (?, ?, ?, ?)",
        (title, now, now, user_id),
    )
    conn.commit()
    conv_id = cursor.lastrowid
    conn.close()
    return conv_id


def get_conversations(user_id: int | None = None) -> list[dict]:
    """Get conversations, most recent first. Optionally filtered by user."""
    conn = get_db()
    if user_id is not None:
        rows = conn.execute(
            "SELECT * FROM conversations WHERE user_id = ? ORDER BY updated_at DESC",
            (user_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM conversations ORDER BY updated_at DESC"
        ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_conversation(conv_id: int) -> dict | None:
    """Get a single conversation by ID."""
    conn = get_db()
    row = conn.execute("SELECT * FROM conversations WHERE id = ?", (conv_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_conversation_for_user(conv_id: int, user_id: int) -> dict | None:
    """Get a conversation only if it belongs to the given user."""
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM conversations WHERE id = ? AND user_id = ?",
        (conv_id, user_id),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def update_conversation_title(conv_id: int, title: str) -> None:
    """Rename a conversation."""
    conn = get_db()
    conn.execute(
        "UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?",
        (title, datetime.now().isoformat(), conv_id),
    )
    conn.commit()
    conn.close()


def delete_conversation(conv_id: int) -> None:
    """Delete a conversation and all its messages."""
    conn = get_db()
    conn.execute("DELETE FROM chat_history WHERE conversation_id = ?", (conv_id,))
    conn.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))
    conn.commit()
    conn.close()


def touch_conversation(conv_id: int) -> None:
    """Update the updated_at timestamp for a conversation."""
    conn = get_db()
    conn.execute(
        "UPDATE conversations SET updated_at = ? WHERE id = ?",
        (datetime.now().isoformat(), conv_id),
    )
    conn.commit()
    conn.close()


# --- Chat messages (conversation-scoped) ---

def save_chat_message(role: str, content: str, conversation_id: int) -> None:
    """Save a chat message to a specific conversation."""
    conn = get_db()
    conn.execute(
        "INSERT INTO chat_history (conversation_id, role, content, created_at) VALUES (?, ?, ?, ?)",
        (conversation_id, role, content, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()
    touch_conversation(conversation_id)


def get_chat_history(conversation_id: int, limit: int = 50) -> list[dict]:
    """Get recent chat messages for a specific conversation."""
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM chat_history WHERE conversation_id = ? ORDER BY created_at DESC LIMIT ?",
        (conversation_id, limit),
    ).fetchall()
    conn.close()
    return [dict(row) for row in reversed(rows)]


# --- Jobs & Applications (unchanged) ---

def save_job(job: dict) -> int:
    """Save a job to the database and return its ID."""
    conn = get_db()
    cursor = conn.execute(
        """INSERT INTO jobs (title, company, location, url, source, tags,
           salary_min, salary_max, saved_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            job.get("title", ""),
            job.get("company", ""),
            job.get("location", ""),
            job.get("url", ""),
            job.get("source", ""),
            json.dumps(job.get("tags", [])),
            job.get("salary_min"),
            job.get("salary_max"),
            datetime.now().isoformat(),
        ),
    )
    conn.commit()
    job_id = cursor.lastrowid
    conn.close()
    return job_id


def get_jobs(limit: int = 50) -> list[dict]:
    """Get saved jobs, most recent first."""
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM jobs ORDER BY saved_at DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def create_application(job_id: int, jd_text: str = "") -> int:
    """Create a new application entry."""
    conn = get_db()
    cursor = conn.execute(
        """INSERT INTO applications (job_id, status, jd_text, updated_at)
           VALUES (?, 'saved', ?, ?)""",
        (job_id, jd_text, datetime.now().isoformat()),
    )
    conn.commit()
    app_id = cursor.lastrowid
    conn.close()
    return app_id


def update_application(app_id: int, **kwargs) -> None:
    """Update application fields."""
    conn = get_db()
    kwargs["updated_at"] = datetime.now().isoformat()
    fields = ", ".join(f"{k} = ?" for k in kwargs)
    values = list(kwargs.values()) + [app_id]
    conn.execute(f"UPDATE applications SET {fields} WHERE id = ?", values)
    conn.commit()
    conn.close()


def get_applications(status: str | None = None) -> list[dict]:
    """Get applications, optionally filtered by status."""
    conn = get_db()
    if status:
        rows = conn.execute(
            "SELECT a.*, j.title, j.company FROM applications a "
            "JOIN jobs j ON a.job_id = j.id "
            "WHERE a.status = ? ORDER BY a.updated_at DESC",
            (status,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT a.*, j.title, j.company FROM applications a "
            "JOIN jobs j ON a.job_id = j.id "
            "ORDER BY a.updated_at DESC"
        ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def save_analysis(application_id: int, agent_name: str, output: str) -> int:
    """Save an agent's analysis output."""
    conn = get_db()
    cursor = conn.execute(
        """INSERT INTO analyses (application_id, agent_name, output, created_at)
           VALUES (?, ?, ?, ?)""",
        (application_id, agent_name, output, datetime.now().isoformat()),
    )
    conn.commit()
    analysis_id = cursor.lastrowid
    conn.close()
    return analysis_id

