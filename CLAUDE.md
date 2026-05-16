# CLAUDE.md

This file provides guidance to AI agents when working with code in this repository.

## What This Project Does

**comsearch** — Automated pipeline to find Vietnamese company contact information from English company names. Pipeline: Input Excel → AI Quick Search → Deep Search + URL Scoring → Scrape + AI Extract → Excel Report.

## Quick Start

```bash
cd ~/workspaces/comsearch
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # Fill in API keys
python scripts/run_batch.py --limit 10
```

## Skills (MUST READ)

Before making ANY changes, read the relevant skill files:

| Skill | When to Read |
|---|---|
| `skills/S1_project_architecture.md` | **ALWAYS** — file structure, DB schema, data flow |
| `skills/S2_coding_conventions.md` | **ALWAYS** — code style, error handling, imports |
| `skills/S3_url_scoring_guide.md` | When working on `filter_module.py` or `search_module.py` |
| `skills/S4_api_integration.md` | When working with external APIs |
| `skills/S5_wsl_system_context.md` | When suggesting resource-heavy operations |
| `skills/S6_git_auto_branch.md` | **ALWAYS** — git workflow for every task |

## Pipeline Flow (4 Steps)

```
Step 1: Excel Input → companies table
Step 2: Gemini Quick Search → core_name_vi, tax_code, grounding_urls
Step 4: Deep Search (4.1 Contact → 4.2 Infer → 4.3 Tax → 4.4 Bare) → scored URLs
Step 5: Firecrawl Scrape → AI Extract → extracted_contacts → Excel Report
```

Full details: `docs/pipeline_workflow.md`

## Key Constraints

- **No Early Stop in Step 2** — always continue to Step 4
- **Dedup in Step 4** — each sub-step deduplicates against previous results
- **All scoring thresholds are customizable** via `.env`
- **DatabaseManager is NOT thread-safe** — one connection per call
- **Step 3 (Google Maps)** — optional, disabled by default
- **API credit awareness** — HTTP 402 = CriticalError = stop immediately

## Common Commands

```bash
python scripts/run_batch.py --limit 100           # Run pipeline
python scripts/run_batch.py --resume               # Resume from checkpoint
python scripts/run_batch.py --retry-failed         # Retry failed
python -m pytest tests/ -v                         # Run tests
```

## Git Workflow

Branch per task: `ai/{wave}-{task-name}` — see `skills/S6_git_auto_branch.md`
