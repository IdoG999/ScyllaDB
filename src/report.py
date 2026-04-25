from __future__ import annotations

import sqlite3
from pathlib import Path

from src.db import fetch_run_report


def build_report_markdown(connection: sqlite3.Connection, run_id: int) -> str:
    run_row, lead_rows, message_rows = fetch_run_report(connection, run_id)
    if run_row is None:
        raise ValueError(f"Run id {run_id} was not found.")

    lines: list[str] = []
    lines.append(f"# GTM Hunter Run Report (run_id={run_id})")
    lines.append("")
    lines.append("## Summary")
    lines.append(f"- Started: {run_row['started_at']}")
    lines.append(f"- Finished: {run_row['finished_at']}")
    lines.append(f"- Leads discovered: {run_row['discovered_count']}")
    lines.append(f"- Leads selected: {run_row['selected_count']}")
    lines.append(f"- Messages generated: {run_row['generated_count']}")
    lines.append(f"- Messages marked sent (dry-run): {run_row['sent_count']}")
    lines.append("")

    lines.append("## Leads")
    for lead in lead_rows:
        lines.append(
            f"- {lead['full_name']} | {lead['title']} @ {lead['current_company']} | "
            f"score={lead['relevance_score']} | selected={bool(lead['selected'])} | "
            f"source={lead['source']}"
        )
        lines.append(f"  - Reason: {lead['reason']}")
        lines.append(f"  - Profile: {lead['profile_url']}")
    lines.append("")

    lines.append("## Message Drafts")
    for message in message_rows:
        lines.append(
            f"- lead_id={message['lead_id']} | channel={message['channel']} | status={message['status']}"
        )
        lines.append(f"  - Body: {message['body']}")

    return "\n".join(lines) + "\n"


def write_report(output_path: Path, content: str) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
