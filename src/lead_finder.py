from __future__ import annotations

import csv
import json
from pathlib import Path

from src.linkedin_api_client import (
    LinkedInApiError,
    fetch_real_candidates_from_api,
    load_api_config_from_env,
)
from src.linkedin_lead_sync_client import (
    LinkedInLeadSyncError,
    fetch_lead_sync_candidates,
    load_lead_sync_config,
)
from src.models import LeadCandidate, ScoredLead


TARGET_COMPANY = "datastax"
TARGET_TITLE_KEYWORDS = (
    "database",
    "data",
    "platform",
    "backend",
    "architect",
    "engineer",
    "devops",
)
TARGET_SKILL_KEYWORDS = ("cassandra", "nosql", "distributed systems", "kubernetes")
CURATED_HIGH_PRIORITY_SOURCES = {"real_csv", "gemini_generated_unverified"}


def load_candidates(candidates_path: Path) -> list[LeadCandidate]:
    raw = json.loads(candidates_path.read_text(encoding="utf-8"))
    candidates: list[LeadCandidate] = []
    for item in raw:
        candidates.append(
            LeadCandidate(
                full_name=item["full_name"],
                headline=item["headline"],
                current_company=item["current_company"],
                title=item["title"],
                location=item["location"],
                profile_url=item["profile_url"],
                skills=item["skills"],
                summary=item["summary"],
                source=item.get("source", "linkedin_mock_api"),
            )
        )
    return candidates


def load_candidates_from_csv(csv_path: Path) -> list[LeadCandidate]:
    candidates: list[LeadCandidate] = []
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            full_name = (row.get("full_name") or "").strip()
            if not full_name:
                continue

            skills_raw = (row.get("skills") or "").strip()
            skills = [part.strip() for part in skills_raw.split("|") if part.strip()]

            candidates.append(
                LeadCandidate(
                    full_name=full_name,
                    headline=(row.get("headline") or "").strip(),
                    current_company=(row.get("current_company") or "").strip(),
                    title=(row.get("title") or "").strip(),
                    location=(row.get("location") or "").strip(),
                    profile_url=(row.get("profile_url") or "").strip(),
                    skills=skills,
                    summary=(row.get("summary") or "").strip(),
                    source=(row.get("source") or "real_csv").strip() or "real_csv",
                )
            )
    return candidates


def load_candidates_from_source(
    lead_source: str,
    candidates_path: Path,
    country: str,
    limit: int,
    allow_mock_fallback: bool,
) -> list[LeadCandidate]:
    if lead_source == "mock_file":
        return load_candidates(candidates_path)

    if lead_source == "real_csv":
        return load_candidates_from_csv(candidates_path)

    if lead_source == "third_party_api":
        try:
            config = load_api_config_from_env(country=country, limit=limit)
            return fetch_real_candidates_from_api(config)
        except LinkedInApiError:
            if allow_mock_fallback:
                return load_candidates(candidates_path)
            raise

    if lead_source == "linkedin_lead_sync":
        try:
            config = load_lead_sync_config(limit=limit)
            return fetch_lead_sync_candidates(config)
        except LinkedInLeadSyncError:
            if allow_mock_fallback:
                return load_candidates(candidates_path)
            raise

    raise ValueError(f"Unsupported lead source: {lead_source}")


def score_lead(candidate: LeadCandidate) -> tuple[int, str]:
    source_value = candidate.source.strip().lower()
    if source_value in CURATED_HIGH_PRIORITY_SOURCES or source_value.startswith("favikon"):
        return 100, "curated high-priority lead source"

    score = 0
    reasons: list[str] = []

    if TARGET_COMPANY in candidate.current_company.lower():
        score += 50
        reasons.append("works at DataStax")

    lowered_title = candidate.title.lower()
    title_hits = [kw for kw in TARGET_TITLE_KEYWORDS if kw in lowered_title]
    if title_hits:
        score += min(25, 8 * len(title_hits))
        reasons.append(f"title match: {', '.join(title_hits)}")

    candidate_skills = " ".join(candidate.skills).lower()
    skill_hits = [kw for kw in TARGET_SKILL_KEYWORDS if kw in candidate_skills]
    if skill_hits:
        score += min(20, 5 * len(skill_hits))
        reasons.append(f"skills match: {', '.join(skill_hits)}")

    if "cassandra" in candidate.summary.lower():
        score += 5
        reasons.append("summary mentions Cassandra")

    if candidate.source == "linkedin_lead_sync":
        score += 70
        reasons.append("real LinkedIn lead form submitter")

    return min(score, 100), "; ".join(reasons) if reasons else "no clear target signals"


def identify_relevant_leads(candidates: list[LeadCandidate], threshold: int) -> list[ScoredLead]:
    scored: list[ScoredLead] = []
    for candidate in candidates:
        score, reason = score_lead(candidate)
        scored.append(
            ScoredLead(
                candidate=candidate,
                relevance_score=score,
                reason=reason,
                selected=score >= threshold,
            )
        )
    return sorted(scored, key=lambda item: item.relevance_score, reverse=True)
