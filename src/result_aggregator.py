import logging
from typing import Dict, List, Optional

from src.config import default_config
from src.database import DatabaseManager

logger = logging.getLogger(__name__)


class ResultAggregator:
    """Aggregate extracted contacts and generate summary statistics."""

    def __init__(self, db: DatabaseManager, config=None):
        self.db = db
        self.config = config or default_config

    def aggregate_all(self) -> List[Dict]:
        """Aggregate extracted_contacts for all companies.

        Returns:
            List of dicts with company info + best contact data.
        """
        companies = self.db.get_all_companies()
        results = []

        for company in companies:
            company_id = company["id"]
            contacts = self.db.get_extracted_contacts_for_company(company_id)

            # Pick best contact (highest confidence)
            best_contact = {}
            if contacts:
                contacts.sort(
                    key=lambda x: x.get("confidence_score", 0),
                    reverse=True,
                )
                best_contact = contacts[0]

            result = {
                "original_name": company.get("original_name", ""),
                "vietnamese_name": company.get("vietnamese_name", ""),
                "tax_code": company.get("tax_code", ""),
                "phone": best_contact.get("phone", ""),
                "email": best_contact.get("email", ""),
                "address": best_contact.get("address", "") or company.get("address", ""),
                "website": best_contact.get("website", ""),
                "source": best_contact.get("source_type", ""),
                "confidence": best_contact.get("confidence_score", 0),
                "status": company.get("status", ""),
            }
            results.append(result)

        return results

    def generate_summary_stats(self, data: List[Dict] = None) -> Dict:
        """Generate summary statistics.

        Args:
            data: Aggregated data (fetches from DB if None).

        Returns:
            Dict with summary statistics.
        """
        if data is None:
            data = self.aggregate_all()

        total = len(data)
        found_phone = sum(1 for d in data if d.get("phone"))
        found_email = sum(1 for d in data if d.get("email"))
        done = sum(1 for d in data if d.get("status") == "done")
        failed = sum(1 for d in data if d.get("status") in ("failed", "permanently_failed"))

        return {
            "total_companies": total,
            "found_phone": found_phone,
            "phone_pct": f"{found_phone / total * 100:.1f}%" if total else "0%",
            "found_email": found_email,
            "email_pct": f"{found_email / total * 100:.1f}%" if total else "0%",
            "done": done,
            "failed": failed,
            "step2_success": 0,  # Filled by pipeline
            "step4_success": 0,
            "gemini_requests": 0,
            "serper_credits": 0,
            "firecrawl_credits": 0,
        }
