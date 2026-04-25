from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from src.models import PersonalizedMessages, ScoredLead


class PersonalizationError(RuntimeError):
    pass


def _format_openai_http_error(exc: HTTPError) -> str:
    raw_body = ""
    try:
        raw_body = exc.read().decode("utf-8", errors="replace")
    except Exception:
        raw_body = ""

    api_message = ""
    if raw_body:
        try:
            payload = json.loads(raw_body)
            api_message = payload.get("error", {}).get("message", "").strip()
        except json.JSONDecodeError:
            api_message = raw_body.strip()

    if exc.code == 401:
        return (
            "OpenAI authentication failed (401). Check OPENAI_API_KEY value and make sure it is active."
        )
    if exc.code == 429:
        hint = "Likely causes: rate limit exceeded, no billing, or exhausted quota."
        if api_message:
            return f"OpenAI request failed (429): {api_message} {hint}"
        return f"OpenAI request failed (429). {hint}"
    if exc.code == 400 and api_message:
        return f"OpenAI bad request (400): {api_message}"
    if api_message:
        return f"OpenAI request failed with HTTP {exc.code}: {api_message}"
    return f"OpenAI request failed with HTTP {exc.code}."


def load_prompt_template(prompt_path: Path) -> str:
    return prompt_path.read_text(encoding="utf-8").strip()


def generate_messages_with_mock_llm(scored_lead: ScoredLead, prompt_template: str) -> PersonalizedMessages:
    first_name = scored_lead.candidate.full_name.split()[0]
    company = scored_lead.candidate.current_company
    title = scored_lead.candidate.title
    signals = scored_lead.reason

    linkedin_invite = (
        f"Hi {first_name}, noticed your {title} role at {company}. "
        "I work with teams optimizing high-throughput distributed workloads and thought it "
        "could be useful to compare notes on migration patterns and latency trade-offs."
    )

    email_followup = (
        f"Subject: Quick idea for your distributed data stack\n\n"
        f"Hi {first_name},\n\n"
        f"I came across your profile while researching teams with strong Cassandra and "
        f"distributed systems ownership ({signals}).\n\n"
        "If reducing p99 latency and infra overhead is on your roadmap, I can share a short "
        "playbook that teams use when evaluating alternatives.\n\n"
        "Worth a 15-minute exchange next week?\n\n"
        "Best,\n"
        "ScyllaDB GTM Team\n\n"
        f"[Prompt context used: {prompt_template[:120]}...]"
    )

    return PersonalizedMessages(linkedin_invite=linkedin_invite, email_followup=email_followup)


def _load_api_key() -> str:
    env_path = Path(".env")
    if env_path.exists():
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise PersonalizationError(
            "Missing OPENAI_API_KEY. Set it or run with --llm-mode mock."
        )
    return api_key


def _build_openai_prompt(scored_lead: ScoredLead, prompt_template: str) -> str:
    return (
        f"{prompt_template}\n\n"
        "Return strict JSON only with this shape:\n"
        '{"linkedin_invite":"...", "email_followup":"..."}\n\n'
        f"Lead Name: {scored_lead.candidate.full_name}\n"
        f"Headline: {scored_lead.candidate.headline}\n"
        f"Current Company: {scored_lead.candidate.current_company}\n"
        f"Title: {scored_lead.candidate.title}\n"
        f"Location: {scored_lead.candidate.location}\n"
        f"Skills: {', '.join(scored_lead.candidate.skills)}\n"
        f"Summary: {scored_lead.candidate.summary}\n"
        f"Relevance Reason: {scored_lead.reason}\n"
    )


def generate_messages_with_openai(
    scored_lead: ScoredLead,
    prompt_template: str,
    model: str = "gpt-4o-mini",
) -> PersonalizedMessages:
    api_key = _load_api_key()
    user_prompt = _build_openai_prompt(scored_lead, prompt_template)
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "You write concise B2B outreach that is practical and personalized.",
            },
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.4,
    }
    request = Request(
        url="https://api.openai.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
    )
    try:
        with urlopen(request, timeout=45) as response:
            response_payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise PersonalizationError(_format_openai_http_error(exc)) from exc
    except URLError as exc:
        raise PersonalizationError(f"OpenAI network error: {exc}") from exc

    content = (
        response_payload.get("choices", [{}])[0]
        .get("message", {})
        .get("content", "")
        .strip()
    )
    if not content:
        raise PersonalizationError("OpenAI response did not include message content.")

    try:
        parsed = json.loads(content)
        linkedin_invite = parsed["linkedin_invite"].strip()
        email_followup = parsed["email_followup"].strip()
    except (json.JSONDecodeError, KeyError, AttributeError) as exc:
        raise PersonalizationError("OpenAI response was not valid JSON in expected format.") from exc

    if not linkedin_invite or not email_followup:
        raise PersonalizationError("OpenAI response returned empty message fields.")

    return PersonalizedMessages(
        linkedin_invite=linkedin_invite,
        email_followup=email_followup,
    )


def generate_messages(
    scored_lead: ScoredLead,
    prompt_template: str,
    llm_mode: str,
    llm_model: str,
) -> PersonalizedMessages:
    if llm_mode == "mock":
        return generate_messages_with_mock_llm(scored_lead, prompt_template)
    if llm_mode == "openai":
        return generate_messages_with_openai(scored_lead, prompt_template, model=llm_model)
    raise ValueError(f"Unsupported llm_mode: {llm_mode}")
