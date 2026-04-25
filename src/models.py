from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LeadCandidate:
    full_name: str
    headline: str
    current_company: str
    title: str
    location: str
    profile_url: str
    skills: list[str]
    summary: str
    source: str = "linkedin_mock_api"


@dataclass(frozen=True)
class ScoredLead:
    candidate: LeadCandidate
    relevance_score: int
    reason: str
    selected: bool


@dataclass(frozen=True)
class PersonalizedMessages:
    linkedin_invite: str
    email_followup: str
