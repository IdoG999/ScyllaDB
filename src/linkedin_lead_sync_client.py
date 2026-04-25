from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from src.models import LeadCandidate


class LinkedInLeadSyncError(RuntimeError):
    pass


@dataclass(frozen=True)
class LinkedInLeadSyncConfig:
    access_token: str
    owner_urn: str
    lead_type: str
    linkedin_version: str = "202604"
    limit: int = 20


def _load_env_if_present() -> None:
    if not os.path.exists(".env"):
        return
    with open(".env", encoding="utf-8") as handle:
        for raw in handle:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key not in os.environ:
                os.environ[key] = value.strip().strip('"').strip("'")


def load_lead_sync_config(limit: int) -> LinkedInLeadSyncConfig:
    _load_env_if_present()
    access_token = os.getenv("LINKEDIN_ACCESS_TOKEN", "").strip()
    owner_urn = os.getenv("LINKEDIN_OWNER_URN", "").strip()
    lead_type = os.getenv("LINKEDIN_LEAD_TYPE", "SPONSORED").strip().upper()
    linkedin_version = os.getenv("LINKEDIN_VERSION", "202604").strip()

    if not access_token:
        raise LinkedInLeadSyncError("Missing LINKEDIN_ACCESS_TOKEN for LinkedIn Lead Sync API.")
    if not owner_urn:
        raise LinkedInLeadSyncError(
            "Missing LINKEDIN_OWNER_URN (example: urn:li:sponsoredAccount:123456)."
        )
    if lead_type not in {"SPONSORED", "EVENT", "COMPANY", "ORGANIZATION_PRODUCT"}:
        raise LinkedInLeadSyncError("LINKEDIN_LEAD_TYPE must be one of SPONSORED/EVENT/COMPANY/ORGANIZATION_PRODUCT.")

    return LinkedInLeadSyncConfig(
        access_token=access_token,
        owner_urn=owner_urn,
        lead_type=lead_type,
        linkedin_version=linkedin_version,
        limit=limit,
    )


def _owner_param(owner_urn: str) -> str:
    # urn:li:sponsoredAccount:522 -> (sponsoredAccount:urn%3Ali%3AsponsoredAccount%3A522)
    if ":sponsoredAccount:" in owner_urn:
        owner_type = "sponsoredAccount"
    elif ":organization:" in owner_urn:
        owner_type = "organization"
    else:
        raise LinkedInLeadSyncError("LINKEDIN_OWNER_URN must be sponsoredAccount or organization URN.")
    return f"({owner_type}:{quote(owner_urn, safe='')})"


def fetch_lead_sync_candidates(config: LinkedInLeadSyncConfig) -> list[LeadCandidate]:
    owner = _owner_param(config.owner_urn)
    lead_type = f"(leadType:{config.lead_type})"
    url = (
        "https://api.linkedin.com/rest/leadFormResponses"
        f"?q=owner&owner={owner}&leadType={quote(lead_type, safe='():=')}"
        f"&count={config.limit}&start=0&limitedToTestLeads=false"
    )
    request = Request(
        url=url,
        headers={
            "Authorization": f"Bearer {config.access_token}",
            "Linkedin-Version": config.linkedin_version,
            "X-Restli-Protocol-Version": "2.0.0",
            "Accept": "application/json",
        },
        method="GET",
    )

    try:
        with urlopen(request, timeout=30) as response:
            payload: dict[str, Any] = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise LinkedInLeadSyncError(f"LinkedIn Lead Sync request failed with HTTP {exc.code}.") from exc
    except URLError as exc:
        raise LinkedInLeadSyncError(f"LinkedIn Lead Sync network error: {exc}") from exc

    elements = payload.get("elements", [])
    candidates: list[LeadCandidate] = []

    for item in elements[: config.limit]:
        submitter = item.get("submitter", "urn:li:person:unknown")
        pseudo_name = submitter.split(":")[-1]
        lead_type_value = item.get("leadType", config.lead_type)
        submitted_at = str(item.get("submittedAt", ""))
        owner_info = item.get("ownerInfo", {})
        account_name = (
            owner_info.get("sponsoredAccountInfo", {}).get("name")
            or owner_info.get("organizationInfo", {}).get("name")
            or "LinkedIn Lead Form"
        )

        candidates.append(
            LeadCandidate(
                full_name=f"LinkedInLead-{pseudo_name}",
                headline=f"Lead Sync {lead_type_value} response",
                current_company=account_name,
                title="Inbound Lead",
                location="Unknown",
                profile_url="",
                skills=["leadgen", "linkedin"],
                summary=f"Lead form response submitter URN: {submitter}; submittedAt={submitted_at}",
                source="linkedin_lead_sync",
            )
        )

    return candidates
