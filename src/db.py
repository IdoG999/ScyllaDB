from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from src.models import PersonalizedMessages, ScoredLead


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def get_connection(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    return connection


def init_db(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            discovered_count INTEGER DEFAULT 0,
            selected_count INTEGER DEFAULT 0,
            generated_count INTEGER DEFAULT 0,
            sent_count INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            full_name TEXT NOT NULL,
            headline TEXT NOT NULL,
            current_company TEXT NOT NULL,
            title TEXT NOT NULL,
            location TEXT NOT NULL,
            profile_url TEXT NOT NULL,
            relevance_score INTEGER NOT NULL,
            selected INTEGER NOT NULL,
            reason TEXT NOT NULL,
            source TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(run_id) REFERENCES runs(id)
        );

        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            lead_id INTEGER NOT NULL,
            channel TEXT NOT NULL,
            body TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(run_id) REFERENCES runs(id),
            FOREIGN KEY(lead_id) REFERENCES leads(id)
        );
        """
    )
    connection.commit()


def create_run(connection: sqlite3.Connection) -> int:
    cursor = connection.execute("INSERT INTO runs (started_at) VALUES (?)", (utc_now_iso(),))
    connection.commit()
    return int(cursor.lastrowid)


def finalize_run(
    connection: sqlite3.Connection,
    run_id: int,
    discovered_count: int,
    selected_count: int,
    generated_count: int,
    sent_count: int,
) -> None:
    connection.execute(
        """
        UPDATE runs
        SET finished_at = ?,
            discovered_count = ?,
            selected_count = ?,
            generated_count = ?,
            sent_count = ?
        WHERE id = ?
        """,
        (utc_now_iso(), discovered_count, selected_count, generated_count, sent_count, run_id),
    )
    connection.commit()


def insert_lead(connection: sqlite3.Connection, run_id: int, lead: ScoredLead) -> int:
    cursor = connection.execute(
        """
        INSERT INTO leads (
            run_id, full_name, headline, current_company, title, location, profile_url,
            relevance_score, selected, reason, source, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id,
            lead.candidate.full_name,
            lead.candidate.headline,
            lead.candidate.current_company,
            lead.candidate.title,
            lead.candidate.location,
            lead.candidate.profile_url,
            lead.relevance_score,
            int(lead.selected),
            lead.reason,
            lead.candidate.source,
            utc_now_iso(),
        ),
    )
    connection.commit()
    return int(cursor.lastrowid)


def insert_messages(
    connection: sqlite3.Connection,
    run_id: int,
    lead_id: int,
    messages: PersonalizedMessages,
    status: str,
) -> None:
    payload = [
        (run_id, lead_id, "linkedin_invite", messages.linkedin_invite, status, utc_now_iso()),
        (run_id, lead_id, "email_followup", messages.email_followup, status, utc_now_iso()),
    ]
    connection.executemany(
        """
        INSERT INTO messages (run_id, lead_id, channel, body, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        payload,
    )
    connection.commit()


def fetch_run_report(connection: sqlite3.Connection, run_id: int) -> tuple[sqlite3.Row, list[sqlite3.Row], list[sqlite3.Row]]:
    run_row = connection.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
    lead_rows = connection.execute(
        "SELECT * FROM leads WHERE run_id = ? ORDER BY relevance_score DESC",
        (run_id,),
    ).fetchall()
    message_rows = connection.execute(
        "SELECT * FROM messages WHERE run_id = ? ORDER BY lead_id, id",
        (run_id,),
    ).fetchall()
    return run_row, lead_rows, message_rows


def purge_mock_leads(connection: sqlite3.Connection) -> tuple[int, int]:
    lead_ids = connection.execute(
        "SELECT id FROM leads WHERE source = 'linkedin_mock_api'"
    ).fetchall()
    ids = [row["id"] for row in lead_ids]
    if not ids:
        return 0, 0

    placeholders = ",".join("?" for _ in ids)
    deleted_messages = connection.execute(
        f"DELETE FROM messages WHERE lead_id IN ({placeholders})",
        ids,
    ).rowcount
    deleted_leads = connection.execute(
        "DELETE FROM leads WHERE source = 'linkedin_mock_api'"
    ).rowcount
    connection.commit()
    return int(deleted_leads), int(deleted_messages)
