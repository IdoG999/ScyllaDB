from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
CSV_HEADER = [
    "full_name",
    "headline",
    "current_company",
    "title",
    "location",
    "profile_url",
    "skills",
    "summary",
    "source",
]


def load_env_file_if_present() -> None:
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


def build_prompt(target_count: int, country: str) -> str:
    return f"""
Generate {target_count} LinkedIn candidate records in {country} that are relevant for GTM outreach
to competitor users in DataStax/Cassandra/NoSQL/distributed database contexts.

Return ONLY a valid JSON array. No markdown, no extra text.
Each item must contain exactly these keys:
- full_name
- headline
- current_company
- title
- location
- profile_url
- skills (array of strings)
- summary

Rules:
1) Prioritize technical roles: database/platform/backend/devops/solutions architects.
2) Prioritize candidates with Cassandra/NoSQL/distributed systems relevance.
3) If a value is unknown, return an empty string (or [] for skills).
4) profile_url should be a LinkedIn profile URL when available.
5) Keep summaries concise (max 2 sentences).
""".strip()


def call_gemini(api_key: str, prompt: str, model: str) -> str:
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.2,
            "topP": 0.9,
            "maxOutputTokens": 4096,
        },
    }
    request = Request(
        url=f"{GEMINI_API_BASE}/{model}:generateContent?key={api_key}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=90) as response:
            body = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        details = ""
        try:
            details = exc.read().decode("utf-8", errors="replace")
        except Exception:
            details = ""
        if details:
            raise RuntimeError(f"Gemini request failed with HTTP {exc.code}: {details}") from exc
        raise RuntimeError(f"Gemini request failed with HTTP {exc.code}.") from exc
    except URLError as exc:
        raise RuntimeError(f"Gemini network error: {exc}") from exc

    try:
        return body["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("Gemini response missing expected text content.") from exc


def extract_json_array(raw_text: str) -> list[dict[str, Any]]:
    text = raw_text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:].strip()

    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1 or end < start:
        raise RuntimeError("Could not find JSON array in Gemini response.")

    payload = text[start : end + 1]
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Gemini output was not valid JSON array.") from exc

    if not isinstance(parsed, list):
        raise RuntimeError("Gemini output JSON is not a list.")
    return parsed


def normalize_row(item: dict[str, Any]) -> dict[str, str]:
    skills = item.get("skills") or []
    if isinstance(skills, str):
        skills_text = skills
    elif isinstance(skills, list):
        skills_text = "|".join(str(s).strip() for s in skills if str(s).strip())
    else:
        skills_text = ""

    return {
        "full_name": str(item.get("full_name", "")).strip(),
        "headline": str(item.get("headline", "")).strip(),
        "current_company": str(item.get("current_company", "")).strip(),
        "title": str(item.get("title", "")).strip(),
        "location": str(item.get("location", "")).strip(),
        "profile_url": str(item.get("profile_url", "")).strip(),
        "skills": skills_text,
        "summary": str(item.get("summary", "")).strip(),
        "source": "gemini_generated_unverified",
    }


def write_csv(rows: list[dict[str, str]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_HEADER)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch lead suggestions from Gemini into CSV.")
    parser.add_argument("--count", type=int, default=20, help="Number of lead rows to request.")
    parser.add_argument("--country", default="Israel", help="Target country for lead generation.")
    parser.add_argument(
        "--output",
        default="data/real_linkedin_candidates.csv",
        help="Output CSV path.",
    )
    parser.add_argument(
        "--model",
        default="gemini-2.0-flash",
        help="Gemini model name (for example: gemini-2.0-flash).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    load_env_file_if_present()
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("Missing GEMINI_API_KEY in environment or .env.")

    prompt = build_prompt(target_count=args.count, country=args.country)
    raw_text = call_gemini(api_key=api_key, prompt=prompt, model=args.model)
    parsed_rows = extract_json_array(raw_text)
    normalized = [normalize_row(item) for item in parsed_rows if isinstance(item, dict)]
    normalized = [row for row in normalized if row["full_name"]]
    if not normalized:
        raise RuntimeError("Gemini returned no usable rows.")

    write_csv(rows=normalized[: args.count], output_path=Path(args.output))
    print(f"Wrote {min(len(normalized), args.count)} rows to {args.output}")
    print("Source label: gemini_generated_unverified")


if __name__ == "__main__":
    main()
