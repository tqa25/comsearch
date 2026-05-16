#!/usr/bin/env python3
"""Evaluation report generator for comsearch pipeline."""

import argparse
import logging
import os
import sys
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dotenv import load_dotenv

from src.database import DatabaseManager
from src.excel_handler import ExcelWriter
from src.result_aggregator import ResultAggregator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description="Generate evaluation report for comsearch pipeline"
    )
    parser.add_argument(
        "--output",
        default="output/evaluation_report.xlsx",
        help="Output file path",
    )
    args = parser.parse_args()

    load_dotenv()

    db = DatabaseManager()
    aggregator = ResultAggregator(db)

    # Aggregate data
    data = aggregator.aggregate_all()
    stats = aggregator.generate_summary_stats(data)

    # Add evaluation-specific stats
    total = stats["total_companies"]
    if total > 0:
        stats["accuracy"] = f"{stats['found_phone'] / total * 100:.1f}%"
    else:
        stats["accuracy"] = "N/A"

    # Generate report
    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)

    writer = ExcelWriter()
    writer.write_final_report(args.output, data, stats)

    logger.info(f"Evaluation report: {args.output}")
    print(f"\nEvaluation Report Summary:")
    print(f"  Total companies: {stats['total_companies']}")
    print(f"  Found phone: {stats['found_phone']} ({stats['phone_pct']})")
    print(f"  Found email: {stats['found_email']} ({stats['email_pct']})")
    print(f"  Done: {stats['done']}")
    print(f"  Failed: {stats['failed']}")


if __name__ == "__main__":
    main()
