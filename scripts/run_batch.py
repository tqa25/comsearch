#!/usr/bin/env python3
"""CLI entry point for the comsearch pipeline."""

import argparse
import logging
import os
import sys
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dotenv import load_dotenv

from src.config import default_config
from src.database import DatabaseManager
from src.errors import CriticalError
from src.excel_handler import ExcelReader, ExcelWriter
from src.pipeline import Pipeline
from src.result_aggregator import ResultAggregator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def load_companies_from_excel(file_path: str, db: DatabaseManager) -> int:
    """Load companies from Excel into DB.

    Returns:
        Number of companies inserted.
    """
    reader = ExcelReader()
    companies = reader.read_companies(file_path)

    count = 0
    for company in companies:
        db.insert_company(
            original_name=company["original_name"],
            tax_code=company.get("tax_code"),
        )
        count += 1

    logger.info(f"Loaded {count} companies from {file_path}")
    return count


def generate_report(output_dir: str, db: DatabaseManager) -> str:
    """Generate Excel report from DB data.

    Returns:
        Path to generated report file.
    """
    os.makedirs(output_dir, exist_ok=True)

    aggregator = ResultAggregator(db)
    data = aggregator.aggregate_all()
    stats = aggregator.generate_summary_stats(data)

    date_str = datetime.now().strftime("%Y-%m-%d")
    output_path = os.path.join(output_dir, f"report_{date_str}.xlsx")

    writer = ExcelWriter()
    writer.write_final_report(output_path, data, stats)

    logger.info(f"Report generated: {output_path}")
    return output_path


def main():
    parser = argparse.ArgumentParser(
        description="Auto Search Company Pipeline"
    )
    parser.add_argument(
        "--input", help="Path to input Excel file"
    )
    parser.add_argument(
        "--output", default="output/", help="Output directory"
    )
    parser.add_argument(
        "--limit", type=int, help="Max companies to process"
    )
    parser.add_argument(
        "--offset", type=int, default=0, help="Skip N companies"
    )
    parser.add_argument(
        "--resume", action="store_true", help="Resume from last checkpoint"
    )
    parser.add_argument(
        "--retry-failed", action="store_true", help="Retry failed companies"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Preview without API calls"
    )
    parser.add_argument(
        "--replay", action="store_true", help="Re-process from cached data"
    )
    parser.add_argument(
        "--force-refresh", action="store_true", help="Bypass all caches"
    )
    parser.add_argument(
        "--report-only", action="store_true", help="Generate report only"
    )

    args = parser.parse_args()

    # Load .env
    load_dotenv()

    db = DatabaseManager()

    # ── Report only ──
    if args.report_only:
        report_path = generate_report(args.output, db)
        print(f"Report: {report_path}")
        return

    # ── Validate args ──
    if not args.resume and not args.retry_failed and not args.report_only:
        if not args.limit and not args.input:
            parser.error("--limit is required for new runs (or use --resume / --retry-failed)")

    # ── Load input Excel ──
    if args.input:
        count = load_companies_from_excel(args.input, db)
        logger.info(f"Inserted {count} companies into DB")

    # ── Dry run ──
    if args.dry_run:
        companies = db.get_all_companies(status="pending")
        if args.offset:
            companies = companies[args.offset:]
        if args.limit:
            companies = companies[:args.limit]

        print(f"\n{'=' * 50}")
        print(f"  DRY RUN — {len(companies)} companies to process")
        print(f"{'=' * 50}")
        for i, c in enumerate(companies, 1):
            print(f"  {i}. {c['original_name']}")
        print(f"{'=' * 50}\n")
        return

    # ── Run pipeline ──
    pipeline = Pipeline(config=default_config)

    try:
        if args.retry_failed:
            pipeline.retry_failed()
        elif args.resume:
            pipeline.resume()
        else:
            pipeline.run(
                limit=args.limit,
                offset=args.offset,
                replay_mode=args.replay,
                force_refresh=args.force_refresh,
            )
    except CriticalError:
        logger.error("Pipeline stopped due to critical error")
        sys.exit(1)

    # ── Generate report ──
    report_path = generate_report(args.output, db)
    print(f"Final report: {report_path}")


if __name__ == "__main__":
    main()
