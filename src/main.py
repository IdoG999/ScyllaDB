from __future__ import annotations

import argparse
from pathlib import Path

from src.db import get_connection, init_db, purge_mock_leads
from src.report import build_report_markdown, write_report
from src.workflow import run_hunter_workflow


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="GTM Hunter PoC CLI")
    parser.add_argument(
        "command",
        choices=("init-db", "run", "report", "purge-mock"),
        help="Command to execute",
    )
    parser.add_argument("--db-path", default="data/hunter.db", help="SQLite database path")
    parser.add_argument(
        "--candidates-path",
        default="data/sample_linkedin_candidates.json",
        help="Input candidates JSON path",
    )
    parser.add_argument(
        "--prompt-path",
        default="prompts/personalization_prompt.md",
        help="Prompt template path",
    )
    parser.add_argument("--threshold", type=int, default=60, help="Selection score threshold")
    parser.add_argument("--top-n", type=int, default=5, help="Max selected leads per run")
    parser.add_argument(
        "--lead-source",
        choices=("mock_file", "real_csv", "third_party_api", "linkedin_lead_sync"),
        default="mock_file",
        help="Lead identification source",
    )
    parser.add_argument("--country", default="Israel", help="Country filter for API source")
    parser.add_argument("--limit", type=int, default=20, help="Max candidates to fetch from source")
    parser.add_argument(
        "--allow-mock-fallback",
        action="store_true",
        help="Fallback to local mock candidates if API source fails",
    )
    parser.add_argument(
        "--llm-mode",
        choices=("mock", "openai"),
        default="mock",
        help="Personalization mode",
    )
    parser.add_argument(
        "--llm-model",
        default="gpt-4o-mini",
        help="OpenAI model name when --llm-mode openai",
    )
    parser.add_argument(
        "--allow-llm-mock-fallback",
        action="store_true",
        help="Fallback to mock personalization if OpenAI call fails",
    )
    parser.add_argument("--dry-run", action="store_true", help="Enable dry-run send mode")
    parser.add_argument("--run-id", type=int, help="Run ID for report command")
    parser.add_argument(
        "--output-path",
        default="output/report_latest.md",
        help="Report output file path",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    db_path = Path(args.db_path)
    connection = get_connection(db_path)

    try:
        if args.command == "init-db":
            init_db(connection)
            print(f"Database initialized at {db_path}")
            return

        if args.command == "run":
            init_db(connection)
            run_id = run_hunter_workflow(
                connection=connection,
                candidates_path=Path(args.candidates_path),
                prompt_path=Path(args.prompt_path),
                threshold=args.threshold,
                top_n=args.top_n,
                lead_source=args.lead_source,
                country=args.country,
                limit=args.limit,
                allow_mock_fallback=args.allow_mock_fallback,
                llm_mode=args.llm_mode,
                llm_model=args.llm_model,
                allow_llm_mock_fallback=args.allow_llm_mock_fallback,
                dry_run=args.dry_run,
            )
            report = build_report_markdown(connection, run_id)
            write_report(Path(args.output_path), report)
            write_report(Path("output/example_report.md"), report)
            print(f"Run completed with id={run_id}")
            print(f"Report written to {args.output_path}")
            print("Example report refreshed at output/example_report.md")
            return

        if args.command == "report":
            if args.run_id is None:
                raise ValueError("--run-id is required for report command")
            report = build_report_markdown(connection, args.run_id)
            write_report(Path(args.output_path), report)
            print(report)
            print(f"Report written to {args.output_path}")
            return

        if args.command == "purge-mock":
            init_db(connection)
            deleted_leads, deleted_messages = purge_mock_leads(connection)
            print(f"Deleted mock leads: {deleted_leads}")
            print(f"Deleted mock messages: {deleted_messages}")
    finally:
        connection.close()


if __name__ == "__main__":
    main()
