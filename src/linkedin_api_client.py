from __future__ import annotations

import json
import os
from pathlib import Path
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from src.models import LeadCandidate


class LinkedInApiError(RuntimeError):
    pass


@dataclass(frozen=True)
class LinkedInApiConfig:
    api_key: str
    provider: str = "proxycurl"
    country: str = "Israel"
    limit: int = 20


def _load_local_env_file() -> None:
    env_path = Path(".env")
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _build_proxycurl_search_url(country: str, limit: int) -> str:
    # Uses Proxycurl's search endpoint semantics for person discovery.
    # If a different provider is used, this adapter can be swapped while keeping normalization.
    params = {
        "country": country,
        "current_company": "DataStax",
        "keyword_title": "engineer OR architect OR platform OR database OR devops",
        "keyword_skills": "Cassandra OR NoSQL OR distributed systems",
        "page_size": str(limit),
    }
    return f"https://nubela.co/proxycurl/api/linkedin/search/person?{urlencode(params)}"


def _build_linkdapi_search_url(country: str, limit: int) -> str:
    params = {
        "country": country,
        "current_company": "DataStax",
        "keyword_title": "engineer OR architect OR platform OR database OR devops",
        "keyword_skills": "Cassandra OR NoSQL OR distributed systems",
        "count": str(limit),
    }
    return f"https://linkdapi.com/api/v1/search/people?{urlencode(params)}"


def _extract_results(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(payload.get("results"), list):
        return payload["results"]
    if isinstance(payload.get("profiles"), list):
        return payload["profiles"]
    data = payload.get("data")
    if isinstance(data, dict):
        if isinstance(data.get("results"), list):
            return data["results"]
        if isinstance(data.get("profiles"), list):
            return data["profiles"]
        if isinstance(data.get("items"), list):
            return data["items"]
    if isinstance(data, list):
        return data
    return []


def fetch_real_candidates_from_api(config: LinkedInApiConfig) -> list[LeadCandidate]:
    provider = config.provider.strip().lower()
    if provider == "proxycurl":
        url = _build_proxycurl_search_url(country=config.country, limit=config.limit)
        headers = {
            "Authorization": f"Bearer {config.api_key}",
            "Accept": "application/json",
        }
    elif provider == "linkdapi":
        url = _build_linkdapi_search_url(country=config.country, limit=config.limit)
        headers = {
            "X-linkdapi-apikey": config.api_key,
            "Accept": "application/json",
        }
    else:
        raise LinkedInApiError("Unsupported LINKEDIN_DATA_PROVIDER. Use 'proxycurl' or 'linkdapi'.")

    request = Request(
        url=url,
        headers=headers,
        method="GET",
    )
    try:
        with urlopen(request, timeout=30) as response:
            payload: dict[str, Any] = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        if provider == "proxycurl" and exc.code == 410:
            raise LinkedInApiError(
                "Proxycurl endpoint returned HTTP 410 (service deprecated). "
                "Set LINKEDIN_DATA_PROVIDER=linkdapi and LINKEDIN_DATA_API_KEY to use the maintained API path."
            ) from exc
        raise LinkedInApiError(
            f"{provider} request failed with HTTP {exc.code}. Verify API key/plan and request filters."
        ) from exc
    except URLError as exc:
        raise LinkedInApiError(f"{provider} network error: {exc}") from exc

    raw_results = _extract_results(payload)
    candidates: list[LeadCandidate] = []

    for item in raw_results[: config.limit]:
        full_name = item.get("full_name") or "Unknown Name"
        title = item.get("occupation") or item.get("headline") or "Unknown Title"
        location = item.get("location") or config.country
        profile_url = item.get("linkedin_profile_url") or item.get("profile_url") or ""

        current_company = ""
        experiences = item.get("experiences") or []
        if experiences and isinstance(experiences, list):
            current_company = experiences[0].get("company", "")
        if not current_company:
            current_company = item.get("current_company", "")

        skills = item.get("skills") or []
        if isinstance(skills, str):
            skills = [skills]

        summary = item.get("summary") or item.get("about") or ""

        candidates.append(
            LeadCandidate(
                full_name=full_name,
                headline=title,
                current_company=current_company,
                title=title,
                location=location,
                profile_url=profile_url,
                skills=skills,
                summary=summary,
                source="third_party_api",
            )
        )

    return candidates


def load_api_config_from_env(country: str, limit: int) -> LinkedInApiConfig:
    _load_local_env_file()
    api_key = os.getenv("LINKEDIN_DATA_API_KEY", "").strip()
    provider = os.getenv("LINKEDIN_DATA_PROVIDER", "proxycurl").strip().lower()
    if not api_key:
        raise LinkedInApiError(
            "Missing LINKEDIN_DATA_API_KEY. "
            "Set it (or place it in .env) and rerun with --lead-source third_party_api, "
            "or pass --allow-mock-fallback."
        )
    return LinkedInApiConfig(api_key=api_key, provider=provider, country=country, limit=limit)
