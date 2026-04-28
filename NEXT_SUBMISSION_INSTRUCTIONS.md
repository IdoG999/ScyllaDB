# Next Submission Instructions (ScyllaDB GTM Assignment)

Use this checklist to avoid the exact failure points from the previous submission.

## 1) Non-Negotiable Acceptance Criteria

- Lead list must contain only ICP-relevant people (DataStax/Cassandra/distributed data engineering personas).
- Every selected lead must have an explainable score based on profile evidence (not source-based shortcuts).
- Personalization must be materially different per lead and tied to persona/context.
- Trigger logic must actually filter (some selected, some rejected) and show why.
- Report must prove what was discovered, selected, and messaged, with data provenance.

## 2) Data Quality Rules (Lead Identification)

- Use `third_party_api` or `linkedin_lead_sync` as primary sources when credentials are available.
- Set `LINKEDIN_DATA_PROVIDER=linkdapi` for maintained third-party profile search (Proxycurl may return HTTP 410).
- If using CSV fallback, only include manually verified technical profiles:
  - target roles: backend/platform/database/devops/sre/architect/engineering manager.
  - target signals: Cassandra/NoSQL/distributed systems/low-latency/high-throughput.
  - valid LinkedIn profile URL per row.
- Reject rows that are influencer/marketing/social/therapy/VC/public-policy personas.
- Never present LLM-generated rows as real-world validated leads.

## 3) Scoring and Filtering Requirements

- Do not assign fixed `100` by source.
- Score from profile signals only:
  - DataStax company match
  - technical title/headline terms
  - technical skills
  - summary/domain keywords
  - optional bonus for verified lead sync submitters
- Add an ICP gate so a lead is selected only when persona + domain relevance pass.
- Demonstrate filtering with at least one run where:
  - `discovered_count > selected_count`
  - low-quality rows appear in report as rejected.

## 4) Personalization Requirements

- LinkedIn invite and follow-up email must be generated per lead.
- Message content must reference lead-specific context:
  - role type (architect vs devops vs backend)
  - likely pain point (latency, operational overhead, scale)
  - tailored asset/CTA.
- Never leak prompt text or placeholder/template artifacts into final message body.
- Ensure outputs differ across leads (not simple name/title swaps).

## 5) Trigger Logic Demonstration

- Run with `--dry-run`.
- Keep threshold meaningful (recommended: `--threshold 60`).
- Keep `--top-n` bounded (recommended: `10-20`) so prioritization is visible.
- Show console evidence that only selected leads are "sent".

## 6) Provenance and Reporting

- Report must include:
  - run summary counts (discovered/selected/generated/sent)
  - source breakdown
  - selected lead list with reasons
  - all generated message drafts.
- Include source labels that are honest:
  - `third_party_api`
  - `linkedin_lead_sync`
  - `manual_research_seed` (for verified CSV fallback)
- Keep SQLite persistence intact (`runs`, `leads`, `messages`).

## 7) Demo Run Script (What To Execute)

```bash
python3 -m src.main init-db
python3 -m src.main verify-source --lead-source real_csv --candidates-path data/real_linkedin_candidates.csv --threshold 60 --limit 20
python3 -m src.main run --dry-run --lead-source real_csv --candidates-path data/real_linkedin_candidates.csv --threshold 60 --top-n 10 --llm-mode mock
python3 -m src.main report --run-id <RUN_ID> --output-path output/report_final.md
```

If API credentials are available:

```bash
python3 -m src.main verify-source --lead-source third_party_api --country Israel --limit 20 --threshold 60
python3 -m src.main run --dry-run --lead-source third_party_api --country Israel --limit 20 --threshold 60 --top-n 10 --llm-mode openai --allow-llm-mock-fallback
```

## 8) Submission Package Checklist

- Updated README with exact run commands and expected outcomes.
- `output/report_final.md` from the latest run.
- Notes on source/provenance and fallback behavior.
- `AGENTS_USED.md` with prompts/agent workflow used.
- Optional: short "what changed since rejection" section with explicit mapping to each feedback item.
