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
    "cassandra",
    "database",
    "platform",
    "backend",
    "architect",
    "engineer",
    "devops",
    "sre",
    "site reliability",
    "principal",
    "staff",
)
TARGET_SKILL_KEYWORDS = (
    "cassandra",
    "scylladb",
    "nosql",
    "distributed systems",
    "distributed databases",
    "kubernetes",
)
TARGET_SUMMARY_KEYWORDS = (
    "cassandra",
    "scylladb",
    "nosql",
    "distributed",
    "low latency",
    "high throughput",
    "database performance",
)
NON_TECH_TITLE_KEYWORDS = (
    "influencer",
    "activist",
    "psychologist",
    "therapist",
    "marketer",
    "partnerships",
    "venture",
    "investor",
    "lecturer",
    "speaker",
)


def _passes_icp_gate(candidate: LeadCandidate) -> bool:
    text = " ".join(
        [
            candidate.current_company.lower(),
            candidate.title.lower(),
            candidate.headline.lower(),
            " ".join(candidate.skills).lower(),
            candidate.summary.lower(),
        ]
    )
    has_company_signal = TARGET_COMPANY in candidate.current_company.lower()
    has_domain_signal = any(keyword in text for keyword in ("cassandra", "nosql", "distributed", "scylladb"))
    has_technical_role = any(keyword in text for keyword in ("engineer", "architect", "devops", "sre", "platform", "database", "backend"))
    has_non_tech_flag = any(keyword in text for keyword in NON_TECH_TITLE_KEYWORDS)
    normalized_profile = candidate.profile_url.lower().strip()
    has_profile_url = "linkedin.com/in/" in normalized_profile
    source_value = candidate.source.lower().strip()
    unverified_source = any(marker in source_value for marker in ("unverified", "generated", "favikon"))
    return (
        (has_company_signal or (has_domain_signal and has_technical_role))
        and not has_non_tech_flag
        and has_profile_url
        and not unverified_source
    )


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
    score = 0
    reasons: list[str] = []
    lowered_title = candidate.title.lower()
    lowered_headline = candidate.headline.lower()
    lowered_summary = candidate.summary.lower()
    candidate_skills = " ".join(candidate.skills).lower()

    if TARGET_COMPANY in candidate.current_company.lower():
        score += 50
        reasons.append("works at DataStax")

    title_space = f"{lowered_title} {lowered_headline}"
    title_hits = [kw for kw in TARGET_TITLE_KEYWORDS if kw in title_space]
    if title_hits:
        score += min(25, 8 * len(title_hits))
        reasons.append(f"title match: {', '.join(title_hits)}")

    skill_hits = [kw for kw in TARGET_SKILL_KEYWORDS if kw in candidate_skills]
    if skill_hits:
        score += min(25, 6 * len(skill_hits))
        reasons.append(f"skills match: {', '.join(skill_hits)}")

    summary_hits = [kw for kw in TARGET_SUMMARY_KEYWORDS if kw in lowered_summary]
    if summary_hits:
        score += min(15, 4 * len(summary_hits))
        reasons.append(f"summary match: {', '.join(summary_hits)}")

    # Explicitly require domain relevance to avoid selecting generic influencers.
    domain_hit_count = len(set(skill_hits)) + len(set(summary_hits))
    if TARGET_COMPANY in candidate.current_company.lower() and domain_hit_count:
        score += 10
        reasons.append("company + domain alignment")
    elif domain_hit_count >= 2:
        score += 10
        reasons.append("strong domain alignment")

    if candidate.source == "linkedin_lead_sync":
        score += 20
        reasons.append("real LinkedIn lead form submitter")

    non_tech_hits = [kw for kw in NON_TECH_TITLE_KEYWORDS if kw in title_space]
    if non_tech_hits:
        score -= min(30, 10 * len(non_tech_hits))
        reasons.append(f"non-ICP title signal: {', '.join(non_tech_hits)}")

    bounded_score = max(0, min(score, 100))
    return bounded_score, "; ".join(reasons) if reasons else "no clear target signals"


def identify_relevant_leads(candidates: list[LeadCandidate], threshold: int) -> list[ScoredLead]:
    scored: list[ScoredLead] = []
    for candidate in candidates:
        score, reason = score_lead(candidate)
        scored.append(
            ScoredLead(
                candidate=candidate,
                relevance_score=score,
                reason=reason,
                selected=score >= threshold and _passes_icp_gate(candidate),
            )
        )
    return sorted(scored, key=lambda item: item.relevance_score, reverse=True)
