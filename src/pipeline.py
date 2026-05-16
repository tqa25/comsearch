import logging
import signal
import time
from datetime import datetime
from typing import Dict, List, Optional

from src.ai_extractor import AIExtractor
from src.config import default_config
from src.database import DatabaseManager
from src.errors import CriticalError, RetryableError, SkippableError
from src.excel_handler import ExcelReader, ExcelWriter
from src.gemini_quick_search import GeminiQuickSearch
from src.health_monitor import HealthMonitor
from src.logger import PipelineLogger
from src.result_aggregator import ResultAggregator
from src.scrape_module import ScrapeModule
from src.search_module import SearchModule

logger = logging.getLogger(__name__)


class Pipeline:
    """Orchestrates the full company search pipeline.

    Flow: Step 2 (Gemini) → Step 4 (Deep Search) → Step 5 (Scrape + Extract)
    """

    STATUS_FLOW = {
        "pending": "search",
        "searching": "search",
        "searched": "filter",
        "scraping": "filter",
        "scraped": "ai_extract",
        "extracting": "ai_extract",
        "failed": "search",
    }

    def __init__(self, config: dict = None, pipeline_config=None):
        self.config = config or default_config
        self.db = DatabaseManager()
        self.pipeline_logger = PipelineLogger(self.db)
        self.health_monitor = HealthMonitor()

        # Initialize sub-modules
        self.gemini_search = GeminiQuickSearch(
            db=self.db, logger=logger, config=self.config
        )
        self.search_module = SearchModule(
            db=self.db, logger=logger, config=self.config
        )
        self.scrape_module = ScrapeModule(
            db=self.db, logger=logger, config=self.config
        )
        self.ai_extractor = AIExtractor(
            db=self.db, logger=logger, config=self.config
        )
        self.result_aggregator = ResultAggregator(
            db=self.db, config=self.config
        )
        self.excel_writer = ExcelWriter()

        # Graceful shutdown
        self._shutdown_requested = False
        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)

        # Stats
        self.stats = {
            "total_processed": 0,
            "step2_success": 0,
            "step4_success": 0,
            "step5_success": 0,
            "no_phone": 0,
            "failed": 0,
        }

    def _handle_shutdown(self, signum, frame):
        """Handle SIGINT/SIGTERM gracefully."""
        self._shutdown_requested = True
        logger.info("Shutdown requested. Finishing current company...")

    def _process_company(self, company_id: int) -> bool:
        """Process a single company through the pipeline.

        Args:
            company_id: The company ID.

        Returns:
            True if processing completed (success or no phone), False if failed.
        """
        company = self.db.get_company(company_id)
        if not company:
            logger.warning(f"Company {company_id} not found")
            return False

        name = company["original_name"]
        status = company.get("status", "pending")
        logger.info(f"[{company_id}] Processing: {name} (status={status})")

        try:
            # ── Step 2: Gemini Quick Search ──
            if status in ("pending", "searching", "failed"):
                self.db.update_company(company_id, status="searching")
                log_id = self.pipeline_logger.log_step_start(
                    company_id, "search", "gemini_quick_search"
                )

                try:
                    result = self.gemini_search.search(company_id)

                    # Update company with found data
                    search_result = result["result"]
                    updates = {}
                    if search_result.get("core_name_vi"):
                        updates["vietnamese_name"] = search_result["core_name_vi"]
                    if search_result.get("tax_code"):
                        updates["tax_code"] = search_result["tax_code"]
                    if search_result.get("address"):
                        updates["address"] = search_result["address"]
                    if updates:
                        self.db.update_company(company_id, **updates)

                    self.db.update_company(company_id, status="searched")
                    self.stats["step2_success"] += 1

                    self.pipeline_logger.log_step_end(
                        log_id, "success", credits_used=1
                    )

                except CriticalError:
                    self.pipeline_logger.log_step_end(
                        log_id, "failed", error_message="Critical error"
                    )
                    raise
                except Exception as e:
                    self.pipeline_logger.log_step_end(
                        log_id, "failed", error_message=str(e)
                    )
                    logger.error(f"[{company_id}] Step 2 error: {e}")

            # ── Step 4: Deep Search ──
            company = self.db.get_company(company_id)
            if company.get("status") in ("searched",):
                self.db.update_company(company_id, status="scraping")
                log_id = self.pipeline_logger.log_step_start(
                    company_id, "filter", "deep_search"
                )

                try:
                    vn_name = company.get("vietnamese_name", "")
                    tax_code = company.get("tax_code", "")

                    filtered_links = self.search_module.search_company(
                        company_id, vn_name=vn_name, tax_code=tax_code
                    )

                    self.db.update_company(company_id, status="scraped")
                    self.stats["step4_success"] += 1

                    self.pipeline_logger.log_step_end(
                        log_id, "success",
                        credits_used=len(filtered_links) * 0.5
                    )

                except CriticalError:
                    self.pipeline_logger.log_step_end(
                        log_id, "failed", error_message="Critical error"
                    )
                    raise
                except Exception as e:
                    self.pipeline_logger.log_step_end(
                        log_id, "failed", error_message=str(e)
                    )
                    logger.error(f"[{company_id}] Step 4 error: {e}")

            # ── Step 5: Scrape + Extract ──
            company = self.db.get_company(company_id)
            if company.get("status") in ("scraped",):
                self.db.update_company(company_id, status="extracting")

                # Scrape
                log_id_scrape = self.pipeline_logger.log_step_start(
                    company_id, "scrape", "firecrawl"
                )
                try:
                    scraped = self.scrape_module.scrape_company(company_id)
                    self.pipeline_logger.log_step_end(
                        log_id_scrape, "success",
                        credits_used=len(scraped)
                    )
                except CriticalError:
                    self.pipeline_logger.log_step_end(
                        log_id_scrape, "failed", error_message="Critical error"
                    )
                    raise
                except Exception as e:
                    self.pipeline_logger.log_step_end(
                        log_id_scrape, "failed", error_message=str(e)
                    )
                    logger.error(f"[{company_id}] Scrape error: {e}")

                # Extract
                log_id_extract = self.pipeline_logger.log_step_start(
                    company_id, "ai_extract", "gemini_extract"
                )
                try:
                    contacts = self.ai_extractor.extract_for_company(company_id)
                    self.pipeline_logger.log_step_end(
                        log_id_extract, "success",
                        credits_used=len(contacts)
                    )
                except CriticalError:
                    self.pipeline_logger.log_step_end(
                        log_id_extract, "failed", error_message="Critical error"
                    )
                    raise
                except Exception as e:
                    self.pipeline_logger.log_step_end(
                        log_id_extract, "failed", error_message=str(e)
                    )
                    logger.error(f"[{company_id}] Extract error: {e}")

                self.db.update_company(company_id, status="done")

            # Check if phone was found
            company = self.db.get_company(company_id)
            contacts = self.db.get_extracted_contacts_for_company(company_id)
            has_phone = any(c.get("phone") for c in contacts)

            if not has_phone:
                self.stats["no_phone"] += 1
                logger.warning(f"[{company_id}] No phone found")

            self.stats["step5_success"] += 1
            return True

        except CriticalError:
            self.db.update_company(
                company_id, status="permanently_failed"
            )
            logger.error(
                f"[{company_id}] Critical error — stopping pipeline"
            )
            raise
        except Exception as e:
            self.db.update_company(company_id, status="failed")
            self.stats["failed"] += 1
            logger.error(f"[{company_id}] Failed: {e}")
            return False

    def run(
        self,
        company_ids: List[int] = None,
        limit: int = None,
        offset: int = 0,
        replay_mode: bool = False,
        force_refresh: bool = False,
    ):
        """Main pipeline loop.

        Args:
            company_ids: Specific company IDs to process.
            limit: Max companies to process.
            offset: Skip N companies.
            replay_mode: Use cached data only.
            force_refresh: Bypass all caches.
        """
        if replay_mode:
            logger.info("Running in replay mode (cached data only)")

        # Get companies to process
        if company_ids:
            companies = [
                self.db.get_company(cid) for cid in company_ids
            ]
            companies = [c for c in companies if c]
        else:
            companies = self.db.get_all_companies(status="pending")
            if offset:
                companies = companies[offset:]
            if limit:
                companies = companies[:limit]

        if not companies:
            logger.info("No companies to process")
            return

        total = len(companies)
        logger.info(f"Starting pipeline for {total} companies")

        for idx, company in enumerate(companies, start=1):
            if self._shutdown_requested:
                logger.info("Shutdown requested, stopping pipeline")
                break

            company_id = company["id"]
            self.stats["total_processed"] += 1

            print(f"[{idx}/{total}] Processing {company['original_name']}...")

            try:
                self._process_company(company_id)
            except CriticalError:
                logger.error("Pipeline stopped due to critical error")
                break

            # Progress
            self.health_monitor._processed_count = idx
            if idx % 5 == 0:
                self.health_monitor.print_status(total, idx)

        # Print summary
        self._print_summary()

    def resume(self):
        """Resume pipeline from last checkpoint."""
        # Get companies not in 'done' or 'permanently_failed'
        companies = self.db.get_all_companies()
        resume_companies = [
            c for c in companies
            if c["status"] not in ("done", "permanently_failed")
        ]

        if not resume_companies:
            logger.info("No companies to resume")
            return

        logger.info(f"Resuming pipeline for {len(resume_companies)} companies")
        company_ids = [c["id"] for c in resume_companies]
        self.run(company_ids=company_ids)

    def retry_failed(self, max_retries: int = 2):
        """Retry failed companies.

        Args:
            max_retries: Max retry attempts per company.
        """
        failed = self.db.get_all_companies(status="failed")
        if not failed:
            logger.info("No failed companies to retry")
            return

        logger.info(f"Retrying {len(failed)} failed companies")
        company_ids = [c["id"] for c in failed]
        self.run(company_ids=company_ids)

    def _print_summary(self):
        """Print batch summary report."""
        s = self.stats
        total = s["total_processed"]
        step2_pct = (s["step2_success"] / total * 100) if total else 0
        step4_pct = (s["step4_success"] / total * 100) if total else 0

        summary = f"""
{'=' * 45}
  BÁO CÁO PIPELINE - {datetime.now().strftime('%Y-%m-%d')}
{'=' * 45}
  Tổng công ty xử lý:            {total}
  Bước 2 thành công (Gemini):     {s['step2_success']} ({step2_pct:.0f}%)
  Bước 4 thành công (Deep):       {s['step4_success']}
  Không tìm được phone:           {s['no_phone']}
  Thất bại (lỗi):                 {s['failed']}
  Credits used:                   {self.health_monitor.get_total_credits():.1f}
{'=' * 45}
"""
        logger.info(summary)
        print(summary)
