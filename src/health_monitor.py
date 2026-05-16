import logging
import time
from typing import Dict

logger = logging.getLogger(__name__)


class HealthMonitor:
    """Track API credit usage and estimate remaining time."""

    def __init__(self):
        self._credits: Dict[str, float] = {}
        self._start_time: float = time.time()
        self._processed_count: int = 0

    def track_credits(self, api_name: str, credits_used: float):
        """Add credits used for an API.

        Args:
            api_name: API identifier (e.g., 'serper', 'firecrawl', 'gemini').
            credits_used: Number of credits consumed.
        """
        self._credits[api_name] = self._credits.get(api_name, 0) + credits_used

    def get_summary(self) -> Dict[str, float]:
        """Get credit usage summary.

        Returns:
            Dict mapping API name to total credits used.
        """
        return dict(self._credits)

    def get_total_credits(self) -> float:
        """Get total credits used across all APIs."""
        return sum(self._credits.values())

    def estimate_remaining(
        self, total_companies: int, processed: int
    ) -> Dict:
        """Estimate remaining time and credits.

        Args:
            total_companies: Total number of companies to process.
            processed: Number already processed.

        Returns:
            Dict with estimated time and credits.
        """
        remaining = total_companies - processed
        if processed <= 0:
            return {
                "estimated_time_minutes": 0,
                "estimated_credits": 0,
                "remaining_companies": remaining,
            }

        elapsed = time.time() - self._start_time
        avg_time_per_company = elapsed / processed
        avg_credits_per_company = self.get_total_credits() / processed

        est_time_minutes = (avg_time_per_company * remaining) / 60
        est_credits = avg_credits_per_company * remaining

        return {
            "estimated_time_minutes": round(est_time_minutes, 1),
            "estimated_credits": round(est_credits, 1),
            "remaining_companies": remaining,
            "avg_time_per_company_sec": round(avg_time_per_company, 1),
            "avg_credits_per_company": round(avg_credits_per_company, 1),
        }

    def print_status(
        self, total_companies: int = None, processed: int = None
    ):
        """Print current status to console."""
        credits = self.get_summary()
        total = self.get_total_credits()
        elapsed = time.time() - self._start_time

        lines = [
            f"  Credits used: {total:.1f}",
        ]
        for api, amount in sorted(credits.items()):
            lines.append(f"    {api}: {amount:.1f}")

        if total_companies and processed is not None:
            est = self.estimate_remaining(total_companies, processed)
            lines.append(
                f"  Estimated remaining: {est['estimated_time_minutes']} min"
            )

        logger.info("\n".join(lines))

    def reset(self):
        """Reset all counters."""
        self._credits.clear()
        self._start_time = time.time()
        self._processed_count = 0
