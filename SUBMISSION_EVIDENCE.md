# Submission Evidence: Fixes vs Review Feedback

This document maps each rejection item to the concrete fix in code and runtime evidence.

## 1) Lead Identification & Relevance

**Feedback:** low-quality/non-relevant leads were identified.  
**Fixes implemented:**
- Replaced CSV with technical ICP leads in `data/real_linkedin_candidates.csv`.
- Added strict ICP gate in `src/lead_finder.py` (`_passes_icp_gate`):
  - requires technical+domain signal or DataStax signal,
  - blocks non-technical persona keywords,
  - requires valid LinkedIn profile URL,
  - blocks unverified/generated sources from selection.

**Runtime evidence:**
- Command:
  - `python3 -m src.main verify-source --lead-source real_csv --candidates-path data/real_linkedin_candidates.csv --threshold 60 --limit 20`
- Result:
  - `Candidates fetched: 12`
  - `Candidates selected with threshold 60: 3`
  - top selected leads are DataStax/Cassandra-relevant roles.

## 2) Data Accuracy (fabricated "live" run)

**Feedback:** live run used fabricated LLM leads (influencers/therapists/etc.).  
**Fixes implemented:**
- Introduced provenance enforcement in selection logic:
  - unverified/generated sources are never selected.
- Added explicit provenance in report (`source breakdown` and `selected leads`) in `src/report.py`.
- Added process instructions in `NEXT_SUBMISSION_INSTRUCTIONS.md` disallowing fabricated "live" data claims.

**Runtime evidence:**
- `output/report_latest.md` includes:
  - `## Source Breakdown`
  - `## Selected Leads` with reasons per lead
  - mixed selected/non-selected list showing filtering and provenance.

## 3) Scoring Logic Bypass

**Feedback:** source type forced score=100 for all leads.  
**Fixes implemented:**
- Removed source-based hardcoded score path in `src/lead_finder.py`.
- Added signal-based scoring only:
  - company, title/headline, skills, summary, domain alignment.
- Added negative weighting for non-ICP title signals.
- Added tests to prevent regression.

**Runtime evidence:**
- Verify output shows varied scores (`100, 96, 88, 50, 48, ...`) instead of all 100.
- Test:
  - `tests/test_quality.py::test_source_does_not_auto_force_score`

## 4) API Implementation Looked Untested

**Feedback:** API clients looked like scaffolding without live interaction evidence.  
**Fixes implemented:**
- Extended `src/linkedin_api_client.py`:
  - provider switch via `LINKEDIN_DATA_PROVIDER=proxycurl|linkdapi`,
  - Proxycurl deprecation handling (HTTP 410) with actionable error,
  - payload parser for different response shapes (`_extract_results`).
- Added parser test in `tests/test_quality.py::ApiParsingTests`.

**Runtime evidence (live calls executed):**
- Proxycurl path command:
  - `python3 -m src.main verify-source --lead-source third_party_api --country Israel --limit 5 --threshold 60`
  - Result: HTTP `410 Gone` with explicit migration guidance.
- LinkdAPI path command:
  - `LINKEDIN_DATA_PROVIDER=linkdapi python3 -m src.main verify-source --lead-source third_party_api --country Israel --limit 5 --threshold 60`
  - Result: HTTP `403 Forbidden` (credential/plan issue), proving real network path is executed.

## 5) AI Personalization & Messaging

### Template Logic
**Feedback:** messages were near-identical and leaked prompt artifacts.  
**Fixes implemented:**
- Updated `src/personalizer.py` mock generation to branch by persona:
  - DevOps/SRE
  - Architect/Principal/Staff
  - Backend Engineer
  - default technical branch
- Removed prompt leakage text from email body.

### Contextual Alignment
**Feedback:** technical messaging was sent to non-technical personas.  
**Fixes implemented:**
- Non-technical personas blocked at selection by ICP gate.
- Selected leads now only technical/domain-aligned profiles.

**Runtime evidence:**
- `output/report_latest.md` message drafts show role-specific differences:
  - "operational toil... migration checklist" vs
  - "architecture decision framework...".

## 6) Execution & Trigger Logic (Filtering/Prioritization)

**Feedback:** threshold filtering ineffective due to score inflation.  
**Fixes implemented:**
- Trigger now depends on real score + ICP gate + top-N.
- No source shortcut can bypass threshold.

**Runtime evidence:**
- Dry-run command:
  - `python3 -m src.main run --dry-run --lead-source real_csv --candidates-path data/real_linkedin_candidates.csv --threshold 60 --top-n 10 --llm-mode mock`
- Result:
  - only 3 leads receive dry-run sends,
  - report shows `Leads discovered: 12`, `Leads selected: 3`.

## 7) Automated Verification Added

- Test suite command:
  - `python3 -m unittest discover -s tests`
- Result:
  - `Ran 6 tests ... OK`

Covered by tests:
- non-technical lead is rejected,
- relevant Cassandra/DataStax lead is selected,
- source cannot auto-force high score,
- unverified source cannot be selected,
- personalization is contextual and has no prompt leakage,
- API result extraction supports nested payload shape.

## 8) Relevant Files Changed

- `src/lead_finder.py`
- `src/personalizer.py`
- `src/linkedin_api_client.py`
- `src/main.py`
- `src/report.py`
- `tests/test_quality.py`
- `README.md`
- `NEXT_SUBMISSION_INSTRUCTIONS.md`
- `output/report_latest.md` (run evidence)
