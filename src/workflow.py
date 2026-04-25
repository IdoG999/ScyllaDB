from __future__ import annotations

import sqlite3
from pathlib import Path

from src import db
from src.lead_finder import identify_relevant_leads, load_candidates_from_source
from src.personalizer import PersonalizationError, generate_messages, load_prompt_template


def run_hunter_workflow(
    connection: sqlite3.Connection,
    candidates_path: Path,
    prompt_path: Path,
    threshold: int,
    top_n: int,
    lead_source: str = "mock_file",
    country: str = "Israel",
    limit: int = 20,
    allow_mock_fallback: bool = False,
    llm_mode: str = "mock",
    llm_model: str = "gpt-4o-mini",
    allow_llm_mock_fallback: bool = False,
    dry_run: bool = True,
) -> int:
    candidates = load_candidates_from_source(
        lead_source=lead_source,
        candidates_path=candidates_path,
        country=country,
        limit=limit,
        allow_mock_fallback=allow_mock_fallback,
    )
    scored_leads = identify_relevant_leads(candidates, threshold=threshold)
    selected = [lead for lead in scored_leads if lead.selected][:top_n]
    prompt_template = load_prompt_template(prompt_path)

    run_id = db.create_run(connection)
    generated_count = 0
    sent_count = 0

    for lead in scored_leads:
        lead_id = db.insert_lead(connection, run_id, lead)

        trigger_passed = lead.selected and lead.relevance_score >= threshold and lead in selected
        if not trigger_passed:
            continue

        try:
            messages = generate_messages(
                scored_lead=lead,
                prompt_template=prompt_template,
                llm_mode=llm_mode,
                llm_model=llm_model,
            )
        except PersonalizationError:
            if not allow_llm_mock_fallback:
                raise
            messages = generate_messages(
                scored_lead=lead,
                prompt_template=prompt_template,
                llm_mode="mock",
                llm_model=llm_model,
            )
        generated_count += 2
        status = "dry_run_sent" if dry_run else "generated"
        db.insert_messages(connection, run_id, lead_id, messages, status=status)
        if dry_run:
            sent_count += 2
            print(f"[DRY RUN] Would send invite + email to {lead.candidate.full_name}")
        else:
            print(f"[GENERATED] Drafted invite + email for {lead.candidate.full_name}")

    db.finalize_run(
        connection=connection,
        run_id=run_id,
        discovered_count=len(scored_leads),
        selected_count=len(selected),
        generated_count=generated_count,
        sent_count=sent_count,
    )
    return run_id
