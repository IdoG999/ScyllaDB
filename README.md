# GTM Hunter PoC (ScyllaDB Home Assignment)

This repository contains a small-scale prototype of an automated GTM "hunter" workflow targeting DataStax users.

## What It Demonstrates

- **Lead identification logic** from either:
  - local mock candidate file, or
  - third-party LinkedIn data API (real profiles when credentials are configured).
- **AI-powered personalization** via mocked mode or real OpenAI mode.
- **Trigger logic** that decides who should receive outreach.
- **Dry-run sending** (no real external messaging).
- **Persistence + reporting** in SQLite and Markdown.

## Assignment Mapping

- **Lead Identification Logic**: Implemented in `src/lead_finder.py` with multiple sources:
  - `mock_file`
  - `real_csv`
  - `third_party_api`
  - `linkedin_lead_sync`
- **AI-Powered Personalization**: Implemented in `src/personalizer.py` with:
  - `--llm-mode mock`
  - `--llm-mode openai`
- **Trigger Logic + Dry Run**: Implemented in `src/workflow.py` (threshold + top-N selection and dry-run logging).
- **Report + Database**: Implemented in `src/db.py` and `src/report.py` with persisted runs/leads/messages and generated report files.

## Project Structure

- `src/lead_finder.py` - lead source selection and DataStax relevance scoring.
- `src/linkedin_api_client.py` - third-party LinkedIn API fetch + normalization.
- `src/linkedin_lead_sync_client.py` - LinkedIn Lead Sync API ingestion (real lead form responses).
- `src/personalizer.py` - mocked and OpenAI-based personalization for invite + follow-up.
- `src/workflow.py` - orchestration, trigger checks, dry-run dispatch.
- `src/db.py` - SQLite schema and persistence.
- `src/report.py` - report generation.
- `src/main.py` - CLI entrypoint.
- `data/sample_linkedin_candidates.json` - sample candidate dataset.
- `data/real_linkedin_candidates.csv` - real LinkedIn candidate input file (user supplied).
- `prompts/personalization_prompt.md` - prompt used by the personalizer layer.
- `output/example_report.md` - generated sample report artifact.
- `AGENTS_USED.md` - prompt/agent workflow used to build this project.
- `INTERVIEW_WORKFLOW_QA.md` - interview walkthrough and expected Q&A.

## Requirements

- Python 3.11+ (3.10+ should also work)

Optional:
```bash
pip install -r requirements.txt
```

## How To Run

### Correct Run (Recommended)

Use this exact order for a clean assignment demo:

```bash
# 0) (Optional) clean old mock rows
python3 -m src.main purge-mock

# 1) Generate 20 candidate rows automatically (or edit CSV manually)
export GEMINI_API_KEY="your_gemini_api_key"
python3 scripts/fetch_leads_from_gemini.py --count 20 --country Israel --model gemini-2.0-flash --output data/real_linkedin_candidates.csv

# 2) Run hunter workflow in dry-run mode
python3 -m src.main run --dry-run --lead-source real_csv --candidates-path data/real_linkedin_candidates.csv --top-n 20 --threshold 60 --llm-mode mock

# 3) Export final report using run id printed in step 2
python3 -m src.main report --run-id <latest_run_id> --output-path output/report_final.md
```

Expected success indicators:
- report shows `Leads discovered > 0`
- report shows `Leads selected > 0`
- report shows `Messages generated > 0`
- `data/hunter.db` includes records in `runs`, `leads`, `messages`

Recommended final run order (assignment demo):
```bash
# 1) (Optional) Auto-generate candidate rows with Gemini
export GEMINI_API_KEY="your_gemini_api_key"
python3 scripts/fetch_leads_from_gemini.py --count 20 --country Israel --model gemini-2.0-flash --output data/real_linkedin_candidates.csv

# 2) Run GTM workflow with real CSV source in dry-run mode
python3 -m src.main run --dry-run --lead-source real_csv --candidates-path data/real_linkedin_candidates.csv --top-n 20 --threshold 60 --llm-mode mock

# 3) Export report for the latest run id printed in step 2
python3 -m src.main report --run-id <latest_run_id> --output-path output/report_final.md
```

Initialize database:
```bash
python -m src.main init-db
```

Run the full pipeline in dry-run mode (mock source):
```bash
python -m src.main run --dry-run --threshold 60 --top-n 3 --lead-source mock_file
```

Run with real profiles from CSV (you provide real LinkedIn rows):
```bash
python -m src.main run --dry-run --lead-source real_csv --candidates-path data/real_linkedin_candidates.csv --top-n 20
```

Fully automated CSV generation via Gemini (writes directly to CSV format):
```bash
export GEMINI_API_KEY="your_gemini_api_key"
python3 scripts/fetch_leads_from_gemini.py --count 20 --country Israel --model gemini-2.0-flash --output data/real_linkedin_candidates.csv
```

Then run the pipeline:
```bash
python -m src.main run --dry-run --lead-source real_csv --candidates-path data/real_linkedin_candidates.csv --top-n 20
```

Run with real OpenAI personalization:
```bash
export OPENAI_API_KEY="your_openai_api_key"
python -m src.main run --dry-run --lead-source mock_file --llm-mode openai --llm-model gpt-4o-mini
```

If you want OpenAI mode but fallback to mock when API fails:
```bash
python -m src.main run --dry-run --llm-mode openai --allow-llm-mock-fallback
```

Run with real LinkedIn leads from a third-party API (top 20 from Israel):
```bash
export LINKEDIN_DATA_API_KEY="your_api_key_here"
python -m src.main run --dry-run --lead-source third_party_api --country Israel --limit 20 --top-n 20
```

Run with LinkedIn Lead Sync API (real lead form responses, top 20):
```bash
export LINKEDIN_ACCESS_TOKEN="your_oauth_access_token"
export LINKEDIN_OWNER_URN="urn:li:sponsoredAccount:123456789"
export LINKEDIN_LEAD_TYPE="SPONSORED"
export LINKEDIN_VERSION="202604"
python -m src.main run --dry-run --lead-source linkedin_lead_sync --limit 20 --top-n 20 --llm-mode openai --allow-llm-mock-fallback
```

You can also place credentials in a local `.env` file (auto-loaded by the API client):
```bash
LINKEDIN_DATA_API_KEY=your_api_key_here
LINKEDIN_ACCESS_TOKEN=your_oauth_access_token
LINKEDIN_OWNER_URN=urn:li:sponsoredAccount:123456789
LINKEDIN_LEAD_TYPE=SPONSORED
LINKEDIN_VERSION=202604
OPENAI_API_KEY=your_openai_api_key
GEMINI_API_KEY=your_gemini_api_key
```

CSV format for `data/real_linkedin_candidates.csv`:
- `full_name,headline,current_company,title,location,profile_url,skills,summary,source`
- `skills` should use `|` as separator (example: `Cassandra|NoSQL|Distributed Systems`)

If you want API mode but allow local fallback when credentials are missing or API call fails:
```bash
python -m src.main run --dry-run --lead-source third_party_api --country Israel --limit 20 --allow-mock-fallback
```

Delete all mock (non-real) people from database:
```bash
python -m src.main purge-mock
```

Generate report for a specific run:
```bash
python -m src.main report --run-id <latest_run_id> --output-path output/report_final.md
```

## Expected Output Example

During dry-run:
- Console logs which leads would receive a LinkedIn invite and follow-up email.
- `data/hunter.db` stores:
  - `runs`
  - `leads`
  - `messages`
- `output/report_latest.md` and `output/example_report.md` are generated.
- Lead entries in reports include their `source` (`real_csv`, `linkedin_lead_sync`, `third_party_api`, or `linkedin_mock_api`).

## Notes

- Real LinkedIn leads are available via:
  - `--lead-source linkedin_lead_sync` (official LinkedIn marketing lead responses), or
  - `--lead-source third_party_api` (external profile search provider).
- Personalization can run in `mock` mode or `openai` mode.
- Official LinkedIn Lead Sync access may require app approval, business verification, and role permissions. The `real_csv` path is provided as a deterministic fallback for assignment review.
