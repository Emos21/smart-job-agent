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
        CREATE TABLE IF NOT EXISTS user_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE REFERENCES users(id),
            target_role TEXT DEFAULT '',
            experience_level TEXT DEFAULT '',
            skills TEXT DEFAULT '[]',
            bio TEXT DEFAULT '',
            linkedin_url TEXT DEFAULT '',
            github_username TEXT DEFAULT '',
            location TEXT DEFAULT '',
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS user_resumes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER REFERENCES users(id),
            name TEXT NOT NULL,
            content TEXT NOT NULL,
            is_default INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        -- Execution audit trail for agent runs
        CREATE TABLE IF NOT EXISTS agent_traces (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER REFERENCES users(id),
            conversation_id INTEGER REFERENCES conversations(id),
            agent_name TEXT NOT NULL,
            intent TEXT DEFAULT '',
            task TEXT DEFAULT '',
            status TEXT DEFAULT 'running',
            output TEXT DEFAULT '',
            started_at TEXT NOT NULL,
            completed_at TEXT,
            total_steps INTEGER DEFAULT 0,
            total_tool_calls INTEGER DEFAULT 0
        );

        -- Individual steps within a trace
        CREATE TABLE IF NOT EXISTS agent_steps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trace_id INTEGER REFERENCES agent_traces(id) ON DELETE CASCADE,
            step_number INTEGER NOT NULL,
            thought TEXT DEFAULT '',
            tool_name TEXT DEFAULT '',
            tool_args TEXT DEFAULT '',
            tool_result TEXT DEFAULT '',
            observation TEXT DEFAULT '',
            success INTEGER DEFAULT 1,
            created_at TEXT NOT NULL
        );

        -- Episodic memory: facts the AI learned about this user
        CREATE TABLE IF NOT EXISTS user_memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER REFERENCES users(id),
            category TEXT NOT NULL DEFAULT 'fact',
            content TEXT NOT NULL,
            source_conversation_id INTEGER,
            relevance_score REAL DEFAULT 1.0,
            created_at TEXT NOT NULL,
            last_accessed TEXT
        );

        -- Goals and goal steps for multi-step planning
        CREATE TABLE IF NOT EXISTS goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER REFERENCES users(id),
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            status TEXT DEFAULT 'active',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS goal_steps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            goal_id INTEGER REFERENCES goals(id) ON DELETE CASCADE,
            step_number INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            agent_name TEXT DEFAULT '',
            status TEXT DEFAULT 'pending',
            output TEXT DEFAULT '',
            trace_id INTEGER,
            created_at TEXT NOT NULL,
            completed_at TEXT
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

    # Migration: add user_id column to jobs if it doesn't exist
    job_cols = [row["name"] for row in conn.execute("PRAGMA table_info(jobs)").fetchall()]
    if "user_id" not in job_cols:
        conn.execute("ALTER TABLE jobs ADD COLUMN user_id INTEGER REFERENCES users(id)")
        conn.commit()

    # Migration: add user_id column to applications if it doesn't exist
    app_cols = [row["name"] for row in conn.execute("PRAGMA table_info(applications)").fetchall()]
    if "user_id" not in app_cols:
        conn.execute("ALTER TABLE applications ADD COLUMN user_id INTEGER REFERENCES users(id)")
        conn.commit()

    # Migration: add embedding column to user_memories if it doesn't exist
    mem_cols = [row["name"] for row in conn.execute("PRAGMA table_info(user_memories)").fetchall()]
    if "embedding" not in mem_cols:
        conn.execute("ALTER TABLE user_memories ADD COLUMN embedding TEXT")
        conn.commit()

    # Migration: add feedback column to agent_traces if it doesn't exist
    trace_cols = [row["name"] for row in conn.execute("PRAGMA table_info(agent_traces)").fetchall()]
    if "feedback" not in trace_cols:
        conn.execute("ALTER TABLE agent_traces ADD COLUMN feedback TEXT")
        conn.commit()

    # Create notifications table if it doesn't exist
    conn.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER REFERENCES users(id),
            type TEXT NOT NULL,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            data TEXT DEFAULT '{}',
            read INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()

    # --- Phase 8 tables ---

    # RL training log
    conn.execute("""
        CREATE TABLE IF NOT EXISTS rl_training_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER REFERENCES users(id),
            samples_trained INTEGER DEFAULT 0,
            accuracy REAL,
            trained_at TEXT NOT NULL
        )
    """)

    # Autonomous tasks (Celery)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS autonomous_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER REFERENCES users(id),
            task_type TEXT NOT NULL,
            celery_task_id TEXT DEFAULT '',
            status TEXT DEFAULT 'pending',
            config TEXT DEFAULT '{}',
            state TEXT DEFAULT '',
            result_summary TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)

    # Task results
    conn.execute("""
        CREATE TABLE IF NOT EXISTS task_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER REFERENCES autonomous_tasks(id) ON DELETE CASCADE,
            result_type TEXT NOT NULL,
            data TEXT DEFAULT '{}',
            created_at TEXT NOT NULL
        )
    """)

    # Goal suggestion log (anti-spam tracking)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS goal_suggestion_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER REFERENCES users(id),
            trigger_type TEXT NOT NULL,
            cooldown_key TEXT NOT NULL,
            confidence REAL DEFAULT 0.0,
            goal_id INTEGER,
            created_at TEXT NOT NULL
        )
    """)

    # Negotiation sessions
    conn.execute("""
        CREATE TABLE IF NOT EXISTS negotiation_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER,
            topic TEXT NOT NULL,
            agents TEXT DEFAULT '[]',
            status TEXT DEFAULT 'active',
            consensus_reached INTEGER DEFAULT 0,
            final_position TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            completed_at TEXT
        )
    """)

    # Negotiation rounds
    conn.execute("""
        CREATE TABLE IF NOT EXISTS negotiation_rounds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER REFERENCES negotiation_sessions(id) ON DELETE CASCADE,
            round_number INTEGER NOT NULL,
            agent_name TEXT NOT NULL,
            response_type TEXT DEFAULT 'position',
            position TEXT DEFAULT '',
            evidence TEXT DEFAULT '',
            confidence REAL DEFAULT 0.5,
            created_at TEXT NOT NULL
        )
    """)

    conn.commit()

    # Migration: add origin and trigger_type columns to goals
    goal_cols = [row["name"] for row in conn.execute("PRAGMA table_info(goals)").fetchall()]
    if "origin" not in goal_cols:
        conn.execute("ALTER TABLE goals ADD COLUMN origin TEXT DEFAULT 'user'")
        conn.commit()
    if "trigger_type" not in goal_cols:
        conn.execute("ALTER TABLE goals ADD COLUMN trigger_type TEXT DEFAULT ''")
        conn.commit()

    # Migration: add auto_suggestions to user_profiles
    profile_cols = [row["name"] for row in conn.execute("PRAGMA table_info(user_profiles)").fetchall()]
    if "auto_suggestions" not in profile_cols:
        conn.execute("ALTER TABLE user_profiles ADD COLUMN auto_suggestions INTEGER DEFAULT 1")
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


# --- Jobs & Applications (user-scoped) ---

def save_job(job: dict, user_id: int | None = None) -> int:
    """Save a job to the database and return its ID."""
    conn = get_db()
    cursor = conn.execute(
        """INSERT INTO jobs (title, company, location, url, source, tags,
           salary_min, salary_max, saved_at, user_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
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
            user_id,
        ),
    )
    conn.commit()
    job_id = cursor.lastrowid
    conn.close()
    return job_id


def get_jobs(user_id: int | None = None, limit: int = 50) -> list[dict]:
    """Get saved jobs for a user, most recent first."""
    conn = get_db()
    if user_id is not None:
        rows = conn.execute(
            "SELECT * FROM jobs WHERE user_id = ? ORDER BY saved_at DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM jobs ORDER BY saved_at DESC LIMIT ?", (limit,)
        ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def create_application(job_id: int, jd_text: str = "", user_id: int | None = None) -> int:
    """Create a new application entry."""
    conn = get_db()
    cursor = conn.execute(
        """INSERT INTO applications (job_id, status, jd_text, updated_at, user_id)
           VALUES (?, 'saved', ?, ?, ?)""",
        (job_id, jd_text, datetime.now().isoformat(), user_id),
    )
    conn.commit()
    app_id = cursor.lastrowid
    conn.close()
    return app_id


def update_application(app_id: int, user_id: int | None = None, **kwargs) -> None:
    """Update application fields. Optionally verify ownership."""
    conn = get_db()
    if user_id is not None:
        row = conn.execute(
            "SELECT id FROM applications WHERE id = ? AND user_id = ?",
            (app_id, user_id),
        ).fetchone()
        if not row:
            conn.close()
            return
    kwargs["updated_at"] = datetime.now().isoformat()
    fields = ", ".join(f"{k} = ?" for k in kwargs)
    values = list(kwargs.values()) + [app_id]
    conn.execute(f"UPDATE applications SET {fields} WHERE id = ?", values)
    conn.commit()
    conn.close()


def get_applications(user_id: int | None = None, status: str | None = None) -> list[dict]:
    """Get applications for a user, optionally filtered by status."""
    conn = get_db()
    query = (
        "SELECT a.*, j.title, j.company FROM applications a "
        "JOIN jobs j ON a.job_id = j.id "
    )
    conditions = []
    params = []

    if user_id is not None:
        conditions.append("a.user_id = ?")
        params.append(user_id)
    if status:
        conditions.append("a.status = ?")
        params.append(status)

    if conditions:
        query += "WHERE " + " AND ".join(conditions) + " "
    query += "ORDER BY a.updated_at DESC"

    rows = conn.execute(query, params).fetchall()
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


# --- User Profile CRUD ---

def get_profile(user_id: int) -> dict | None:
    """Get the profile for a user."""
    conn = get_db()
    row = conn.execute("SELECT * FROM user_profiles WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    if not row:
        return None
    result = dict(row)
    result["skills"] = json.loads(result.get("skills") or "[]")
    return result


def upsert_profile(user_id: int, **kwargs) -> dict:
    """Create or update a user profile. Returns the updated profile."""
    conn = get_db()
    now = datetime.now().isoformat()
    existing = conn.execute("SELECT id FROM user_profiles WHERE user_id = ?", (user_id,)).fetchone()

    if "skills" in kwargs and isinstance(kwargs["skills"], list):
        kwargs["skills"] = json.dumps(kwargs["skills"])

    kwargs["updated_at"] = now

    if existing:
        fields = ", ".join(f"{k} = ?" for k in kwargs)
        values = list(kwargs.values()) + [user_id]
        conn.execute(f"UPDATE user_profiles SET {fields} WHERE user_id = ?", values)
    else:
        kwargs["user_id"] = user_id
        cols = ", ".join(kwargs.keys())
        placeholders = ", ".join("?" for _ in kwargs)
        conn.execute(f"INSERT INTO user_profiles ({cols}) VALUES ({placeholders})", list(kwargs.values()))

    conn.commit()
    conn.close()
    return get_profile(user_id)


# --- User Resume CRUD ---

def save_resume(user_id: int, name: str, content: str, is_default: bool = False) -> int:
    """Save a resume for a user. If is_default, unset other defaults first."""
    conn = get_db()
    now = datetime.now().isoformat()

    if is_default:
        conn.execute("UPDATE user_resumes SET is_default = 0 WHERE user_id = ?", (user_id,))

    cursor = conn.execute(
        "INSERT INTO user_resumes (user_id, name, content, is_default, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, name, content, 1 if is_default else 0, now, now),
    )
    conn.commit()
    resume_id = cursor.lastrowid
    conn.close()
    return resume_id


def get_resumes(user_id: int) -> list[dict]:
    """Get all resumes for a user."""
    conn = get_db()
    rows = conn.execute(
        "SELECT id, user_id, name, is_default, created_at, updated_at, LENGTH(content) as char_count FROM user_resumes WHERE user_id = ? ORDER BY updated_at DESC",
        (user_id,),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_resume(resume_id: int, user_id: int) -> dict | None:
    """Get a specific resume by ID, verifying ownership."""
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM user_resumes WHERE id = ? AND user_id = ?",
        (resume_id, user_id),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_default_resume(user_id: int) -> dict | None:
    """Get the user's default resume."""
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM user_resumes WHERE user_id = ? AND is_default = 1",
        (user_id,),
    ).fetchone()
    if not row:
        # Fall back to most recent resume
        row = conn.execute(
            "SELECT * FROM user_resumes WHERE user_id = ? ORDER BY updated_at DESC LIMIT 1",
            (user_id,),
        ).fetchone()
    conn.close()
    return dict(row) if row else None


def delete_resume(resume_id: int, user_id: int) -> bool:
    """Delete a resume. Returns True if deleted."""
    conn = get_db()
    cursor = conn.execute(
        "DELETE FROM user_resumes WHERE id = ? AND user_id = ?",
        (resume_id, user_id),
    )
    conn.commit()
    deleted = cursor.rowcount > 0
    conn.close()
    return deleted


def set_default_resume(resume_id: int, user_id: int) -> bool:
    """Set a resume as the default for a user."""
    conn = get_db()
    conn.execute("UPDATE user_resumes SET is_default = 0 WHERE user_id = ?", (user_id,))
    cursor = conn.execute(
        "UPDATE user_resumes SET is_default = 1 WHERE id = ? AND user_id = ?",
        (resume_id, user_id),
    )
    conn.commit()
    updated = cursor.rowcount > 0
    conn.close()
    return updated


# --- Agent Traces ---

def create_trace(user_id: int, conversation_id: int | None, agent_name: str, intent: str = "", task: str = "") -> int:
    """Create a new agent execution trace and return its ID."""
    conn = get_db()
    now = datetime.now().isoformat()
    cursor = conn.execute(
        "INSERT INTO agent_traces (user_id, conversation_id, agent_name, intent, task, status, started_at) VALUES (?, ?, ?, ?, ?, 'running', ?)",
        (user_id, conversation_id, agent_name, intent, task[:2000], now),
    )
    conn.commit()
    trace_id = cursor.lastrowid
    conn.close()
    return trace_id


def add_trace_step(
    trace_id: int,
    step_number: int,
    thought: str = "",
    tool_name: str = "",
    tool_args: str = "",
    tool_result: str = "",
    observation: str = "",
    success: bool = True,
) -> int:
    """Add a step to an agent trace."""
    conn = get_db()
    now = datetime.now().isoformat()
    cursor = conn.execute(
        "INSERT INTO agent_steps (trace_id, step_number, thought, tool_name, tool_args, tool_result, observation, success, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (trace_id, step_number, thought[:1000], tool_name, tool_args[:2000], tool_result[:4000], observation[:2000], 1 if success else 0, now),
    )
    conn.commit()
    step_id = cursor.lastrowid
    conn.close()
    return step_id


def complete_trace(trace_id: int, status: str = "completed", output: str = "", total_steps: int = 0, total_tool_calls: int = 0) -> None:
    """Mark a trace as completed/failed with its output."""
    conn = get_db()
    now = datetime.now().isoformat()
    conn.execute(
        "UPDATE agent_traces SET status = ?, output = ?, completed_at = ?, total_steps = ?, total_tool_calls = ? WHERE id = ?",
        (status, output[:4000], now, total_steps, total_tool_calls, trace_id),
    )
    conn.commit()
    conn.close()


def get_traces(user_id: int, limit: int = 20) -> list[dict]:
    """Get recent agent traces for a user."""
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM agent_traces WHERE user_id = ? ORDER BY started_at DESC LIMIT ?",
        (user_id, limit),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_trace_steps(trace_id: int) -> list[dict]:
    """Get all steps for a trace."""
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM agent_steps WHERE trace_id = ? ORDER BY step_number ASC",
        (trace_id,),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


# --- User Memories (Episodic) ---

def save_memory(user_id: int, content: str, category: str = "fact", source_conversation_id: int | None = None, relevance_score: float = 1.0, embedding: str | None = None) -> int:
    """Save a memory about a user. Optional embedding is a JSON string of floats."""
    conn = get_db()
    now = datetime.now().isoformat()
    cursor = conn.execute(
        "INSERT INTO user_memories (user_id, category, content, source_conversation_id, relevance_score, created_at, last_accessed, embedding) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (user_id, category, content, source_conversation_id, relevance_score, now, now, embedding),
    )
    conn.commit()
    mem_id = cursor.lastrowid
    conn.close()
    return mem_id


def get_memories(user_id: int, category: str | None = None, limit: int = 20) -> list[dict]:
    """Get memories for a user, optionally filtered by category."""
    conn = get_db()
    if category:
        rows = conn.execute(
            "SELECT * FROM user_memories WHERE user_id = ? AND category = ? ORDER BY relevance_score DESC, created_at DESC LIMIT ?",
            (user_id, category, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM user_memories WHERE user_id = ? ORDER BY relevance_score DESC, created_at DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
    # Update last_accessed
    ids = [row["id"] for row in rows]
    if ids:
        now = datetime.now().isoformat()
        placeholders = ",".join("?" for _ in ids)
        conn.execute(f"UPDATE user_memories SET last_accessed = ? WHERE id IN ({placeholders})", [now] + ids)
        conn.commit()
    conn.close()
    return [dict(row) for row in rows]


def search_memories(user_id: int, query: str, limit: int = 10) -> list[dict]:
    """Search memories by keyword (SQLite LIKE)."""
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM user_memories WHERE user_id = ? AND content LIKE ? ORDER BY relevance_score DESC LIMIT ?",
        (user_id, f"%{query}%", limit),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_all_memories_with_embeddings(user_id: int) -> list[dict]:
    """Get all memories for a user, including parsed embeddings."""
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM user_memories WHERE user_id = ? ORDER BY created_at DESC",
        (user_id,),
    ).fetchall()
    conn.close()
    results = []
    for row in rows:
        mem = dict(row)
        raw = mem.get("embedding")
        if raw:
            try:
                mem["embedding_vec"] = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                mem["embedding_vec"] = None
        else:
            mem["embedding_vec"] = None
        results.append(mem)
    return results


def semantic_search_memories(user_id: int, query_embedding: list[float], limit: int = 10, threshold: float = 0.3) -> list[dict]:
    """Search memories by cosine similarity against a query embedding."""
    from .embeddings import cosine_similarity

    all_memories = get_all_memories_with_embeddings(user_id)
    scored = []
    for mem in all_memories:
        vec = mem.get("embedding_vec")
        if not vec:
            continue
        sim = cosine_similarity(query_embedding, vec)
        if sim >= threshold:
            scored.append((sim, mem))

    scored.sort(key=lambda x: -x[0])
    return [m for _, m in scored[:limit]]


# --- Agent Trace Feedback ---

def set_trace_feedback(trace_id: int, user_id: int, feedback: str) -> bool:
    """Set feedback on a trace. Returns True if updated."""
    conn = get_db()
    cursor = conn.execute(
        "UPDATE agent_traces SET feedback = ? WHERE id = ? AND user_id = ?",
        (feedback, trace_id, user_id),
    )
    conn.commit()
    updated = cursor.rowcount > 0
    conn.close()
    return updated


def get_feedback_stats(user_id: int) -> dict:
    """Get feedback statistics for a user's traces."""
    conn = get_db()
    rows = conn.execute(
        "SELECT feedback, COUNT(*) as cnt FROM agent_traces WHERE user_id = ? AND feedback IS NOT NULL GROUP BY feedback",
        (user_id,),
    ).fetchall()
    conn.close()
    return {row["feedback"]: row["cnt"] for row in rows}


# --- Notifications ---

def create_notification(user_id: int, type: str, title: str, message: str, data: str = "{}") -> int:
    """Create a notification for a user."""
    conn = get_db()
    now = datetime.now().isoformat()
    cursor = conn.execute(
        "INSERT INTO notifications (user_id, type, title, message, data, read, created_at) VALUES (?, ?, ?, ?, ?, 0, ?)",
        (user_id, type, title, message, data, now),
    )
    conn.commit()
    nid = cursor.lastrowid
    conn.close()
    return nid


def get_notifications(user_id: int, unread_only: bool = False, limit: int = 50) -> list[dict]:
    """Get notifications for a user, most recent first."""
    conn = get_db()
    query = "SELECT * FROM notifications WHERE user_id = ?"
    params: list[Any] = [user_id]
    if unread_only:
        query += " AND read = 0"
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def mark_notification_read(nid: int, user_id: int) -> bool:
    """Mark a single notification as read."""
    conn = get_db()
    cursor = conn.execute(
        "UPDATE notifications SET read = 1 WHERE id = ? AND user_id = ?",
        (nid, user_id),
    )
    conn.commit()
    updated = cursor.rowcount > 0
    conn.close()
    return updated


def mark_all_notifications_read(user_id: int) -> int:
    """Mark all notifications as read for a user. Returns count updated."""
    conn = get_db()
    cursor = conn.execute(
        "UPDATE notifications SET read = 1 WHERE user_id = ? AND read = 0",
        (user_id,),
    )
    conn.commit()
    count = cursor.rowcount
    conn.close()
    return count


def get_unread_notification_count(user_id: int) -> int:
    """Get count of unread notifications for a user."""
    conn = get_db()
    row = conn.execute(
        "SELECT COUNT(*) as cnt FROM notifications WHERE user_id = ? AND read = 0",
        (user_id,),
    ).fetchone()
    conn.close()
    return row["cnt"] if row else 0


# --- Goals ---

def create_goal(user_id: int, title: str, description: str = "") -> int:
    """Create a new goal and return its ID."""
    conn = get_db()
    now = datetime.now().isoformat()
    cursor = conn.execute(
        "INSERT INTO goals (user_id, title, description, status, created_at, updated_at) VALUES (?, ?, ?, 'active', ?, ?)",
        (user_id, title, description, now, now),
    )
    conn.commit()
    goal_id = cursor.lastrowid
    conn.close()
    return goal_id


def add_goal_step(goal_id: int, step_number: int, title: str, description: str = "", agent_name: str = "") -> int:
    """Add a step to a goal."""
    conn = get_db()
    now = datetime.now().isoformat()
    cursor = conn.execute(
        "INSERT INTO goal_steps (goal_id, step_number, title, description, agent_name, status, created_at) VALUES (?, ?, ?, ?, ?, 'pending', ?)",
        (goal_id, step_number, title, description, agent_name, now),
    )
    conn.commit()
    step_id = cursor.lastrowid
    conn.close()
    return step_id


def get_goals(user_id: int, status: str | None = None) -> list[dict]:
    """Get goals for a user, optionally filtered by status."""
    conn = get_db()
    if status:
        rows = conn.execute(
            "SELECT * FROM goals WHERE user_id = ? AND status = ? ORDER BY updated_at DESC",
            (user_id, status),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM goals WHERE user_id = ? ORDER BY updated_at DESC",
            (user_id,),
        ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_goal(goal_id: int, user_id: int) -> dict | None:
    """Get a goal by ID with ownership check."""
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM goals WHERE id = ? AND user_id = ?",
        (goal_id, user_id),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_goal_steps(goal_id: int) -> list[dict]:
    """Get all steps for a goal."""
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM goal_steps WHERE goal_id = ? ORDER BY step_number ASC",
        (goal_id,),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def update_goal_status(goal_id: int, status: str) -> None:
    """Update a goal's status."""
    conn = get_db()
    now = datetime.now().isoformat()
    conn.execute(
        "UPDATE goals SET status = ?, updated_at = ? WHERE id = ?",
        (status, now, goal_id),
    )
    conn.commit()
    conn.close()


def update_goal_step(step_id: int, status: str, output: str = "", trace_id: int | None = None) -> None:
    """Update a goal step's status and output."""
    conn = get_db()
    now = datetime.now().isoformat()
    completed_at = now if status in ("completed", "failed", "skipped") else None
    conn.execute(
        "UPDATE goal_steps SET status = ?, output = ?, trace_id = ?, completed_at = ? WHERE id = ?",
        (status, output[:4000], trace_id, completed_at, step_id),
    )
    conn.commit()
    conn.close()


def get_next_pending_step(goal_id: int) -> dict | None:
    """Get the next pending step for a goal."""
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM goal_steps WHERE goal_id = ? AND status = 'pending' ORDER BY step_number ASC LIMIT 1",
        (goal_id,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


# --- RL Training Log ---

def log_rl_training(user_id: int, samples_trained: int, accuracy: float | None = None) -> int:
    """Log an RL training run."""
    conn = get_db()
    now = datetime.now().isoformat()
    cursor = conn.execute(
        "INSERT INTO rl_training_log (user_id, samples_trained, accuracy, trained_at) VALUES (?, ?, ?, ?)",
        (user_id, samples_trained, accuracy, now),
    )
    conn.commit()
    log_id = cursor.lastrowid
    conn.close()
    return log_id


# --- Autonomous Tasks ---

def create_autonomous_task(user_id: int, task_type: str, celery_task_id: str = "", config: str = "{}") -> int:
    """Create a new autonomous task record."""
    conn = get_db()
    now = datetime.now().isoformat()
    cursor = conn.execute(
        "INSERT INTO autonomous_tasks (user_id, task_type, celery_task_id, status, config, created_at, updated_at) VALUES (?, ?, ?, 'pending', ?, ?, ?)",
        (user_id, task_type, celery_task_id, config, now, now),
    )
    conn.commit()
    task_id = cursor.lastrowid
    conn.close()
    return task_id


def update_autonomous_task(task_id: int, **kwargs) -> None:
    """Update an autonomous task record."""
    conn = get_db()
    kwargs["updated_at"] = datetime.now().isoformat()
    fields = ", ".join(f"{k} = ?" for k in kwargs)
    values = list(kwargs.values()) + [task_id]
    conn.execute(f"UPDATE autonomous_tasks SET {fields} WHERE id = ?", values)
    conn.commit()
    conn.close()


def get_autonomous_task(task_id: int) -> dict | None:
    """Get a single autonomous task by ID."""
    conn = get_db()
    row = conn.execute("SELECT * FROM autonomous_tasks WHERE id = ?", (task_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_tasks(user_id: int, status: str | None = None, limit: int = 50) -> list[dict]:
    """Get autonomous tasks for a user."""
    conn = get_db()
    query = "SELECT * FROM autonomous_tasks WHERE user_id = ?"
    params: list[Any] = [user_id]
    if status:
        query += " AND status = ?"
        params.append(status)
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def create_task_result(task_id: int, result_type: str, data: str = "{}") -> int:
    """Create a result entry for an autonomous task."""
    conn = get_db()
    now = datetime.now().isoformat()
    cursor = conn.execute(
        "INSERT INTO task_results (task_id, result_type, data, created_at) VALUES (?, ?, ?, ?)",
        (task_id, result_type, data, now),
    )
    conn.commit()
    result_id = cursor.lastrowid
    conn.close()
    return result_id


def get_task_results(task_id: int) -> list[dict]:
    """Get all results for an autonomous task."""
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM task_results WHERE task_id = ? ORDER BY created_at ASC",
        (task_id,),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


# --- Goal Suggestions ---

def create_goal_with_origin(user_id: int, title: str, description: str = "", origin: str = "user", trigger_type: str = "") -> int:
    """Create a goal with origin tracking (user or agent_suggested)."""
    conn = get_db()
    now = datetime.now().isoformat()
    status = "suggested" if origin == "agent_suggested" else "active"
    cursor = conn.execute(
        "INSERT INTO goals (user_id, title, description, status, origin, trigger_type, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (user_id, title, description, status, origin, trigger_type, now, now),
    )
    conn.commit()
    goal_id = cursor.lastrowid
    conn.close()
    return goal_id


def get_suggested_goals(user_id: int) -> list[dict]:
    """Get agent-suggested goals that haven't been approved/dismissed."""
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM goals WHERE user_id = ? AND origin = 'agent_suggested' AND status = 'suggested' ORDER BY created_at DESC",
        (user_id,),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def approve_goal(goal_id: int, user_id: int) -> bool:
    """Approve a suggested goal — changes status to active."""
    conn = get_db()
    now = datetime.now().isoformat()
    cursor = conn.execute(
        "UPDATE goals SET status = 'active', updated_at = ? WHERE id = ? AND user_id = ? AND status = 'suggested'",
        (now, goal_id, user_id),
    )
    conn.commit()
    updated = cursor.rowcount > 0
    conn.close()
    return updated


def dismiss_goal(goal_id: int, user_id: int) -> bool:
    """Dismiss a suggested goal."""
    conn = get_db()
    now = datetime.now().isoformat()
    cursor = conn.execute(
        "UPDATE goals SET status = 'dismissed', updated_at = ? WHERE id = ? AND user_id = ? AND status = 'suggested'",
        (now, goal_id, user_id),
    )
    conn.commit()
    updated = cursor.rowcount > 0
    conn.close()
    return updated


def log_goal_suggestion(user_id: int, trigger_type: str, cooldown_key: str, confidence: float, goal_id: int | None = None) -> int:
    """Log a goal suggestion for anti-spam tracking."""
    conn = get_db()
    now = datetime.now().isoformat()
    cursor = conn.execute(
        "INSERT INTO goal_suggestion_log (user_id, trigger_type, cooldown_key, confidence, goal_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, trigger_type, cooldown_key, confidence, goal_id, now),
    )
    conn.commit()
    log_id = cursor.lastrowid
    conn.close()
    return log_id


def get_recent_suggestions(user_id: int, hours: int = 24) -> list[dict]:
    """Get suggestions created in the last N hours for anti-spam."""
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM goal_suggestion_log WHERE user_id = ? AND created_at > datetime('now', ? || ' hours') ORDER BY created_at DESC",
        (user_id, f"-{hours}"),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_suggestion_by_cooldown_key(user_id: int, cooldown_key: str, days: int = 7) -> dict | None:
    """Check if a suggestion with this cooldown key was made recently."""
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM goal_suggestion_log WHERE user_id = ? AND cooldown_key = ? AND created_at > datetime('now', ? || ' days') ORDER BY created_at DESC LIMIT 1",
        (user_id, cooldown_key, f"-{days}"),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


# --- Negotiation ---

def create_negotiation_session(conversation_id: int | None, topic: str, agents: list[str]) -> int:
    """Create a negotiation session."""
    conn = get_db()
    now = datetime.now().isoformat()
    cursor = conn.execute(
        "INSERT INTO negotiation_sessions (conversation_id, topic, agents, status, created_at) VALUES (?, ?, ?, 'active', ?)",
        (conversation_id, topic, json.dumps(agents), now),
    )
    conn.commit()
    session_id = cursor.lastrowid
    conn.close()
    return session_id


def add_negotiation_round(session_id: int, round_number: int, agent_name: str, response_type: str, position: str, evidence: str = "", confidence: float = 0.5) -> int:
    """Add a round to a negotiation session."""
    conn = get_db()
    now = datetime.now().isoformat()
    cursor = conn.execute(
        "INSERT INTO negotiation_rounds (session_id, round_number, agent_name, response_type, position, evidence, confidence, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (session_id, round_number, agent_name, response_type, position, evidence, confidence, now),
    )
    conn.commit()
    round_id = cursor.lastrowid
    conn.close()
    return round_id


def complete_negotiation(session_id: int, consensus_reached: bool, final_position: str) -> None:
    """Complete a negotiation session."""
    conn = get_db()
    now = datetime.now().isoformat()
    conn.execute(
        "UPDATE negotiation_sessions SET status = 'completed', consensus_reached = ?, final_position = ?, completed_at = ? WHERE id = ?",
        (1 if consensus_reached else 0, final_position, now, session_id),
    )
    conn.commit()
    conn.close()


def get_negotiation_rounds(session_id: int) -> list[dict]:
    """Get all rounds for a negotiation session."""
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM negotiation_rounds WHERE session_id = ? ORDER BY round_number ASC, id ASC",
        (session_id,),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


# --- User profile auto_suggestions preference ---

def get_auto_suggestions_enabled(user_id: int) -> bool:
    """Check if auto-suggestions are enabled for a user."""
    conn = get_db()
    row = conn.execute(
        "SELECT auto_suggestions FROM user_profiles WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    conn.close()
    if not row:
        return True  # Default on
    return bool(row["auto_suggestions"])

