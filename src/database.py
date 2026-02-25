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
    return conn


def init_db() -> None:
    """Create database tables if they don't exist."""
    conn = get_db()
    conn.executescript("""
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

        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
    """)
    conn.commit()
    conn.close()


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


def save_chat_message(role: str, content: str) -> None:
    """Save a chat message to history."""
    conn = get_db()
    conn.execute(
        "INSERT INTO chat_history (role, content, created_at) VALUES (?, ?, ?)",
        (role, content, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()


def get_chat_history(limit: int = 50) -> list[dict]:
    """Get recent chat messages."""
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM chat_history ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(row) for row in reversed(rows)]


def clear_chat_history() -> None:
    """Delete all chat history."""
    conn = get_db()
    conn.execute("DELETE FROM chat_history")
    conn.commit()
    conn.close()


# Initialize DB on import
init_db()
