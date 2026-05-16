import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional

from src.database import DatabaseManager

logger = logging.getLogger(__name__)


class PipelineLogger:
    """Structured logging to pipeline_logs table."""

    def __init__(self, db: DatabaseManager):
        self.db = db

    def log_step_start(
        self,
        company_id: int,
        step: str,
        source_name: str,
        raw_request: str = None,
    ) -> int:
        """Log the start of a pipeline step.

        Args:
            company_id: The company being processed.
            step: Step name (search, filter, scrape, ai_extract).
            source_name: API or module name.
            raw_request: Raw request data (optional).

        Returns:
            log_id for later use in log_step_end.
        """
        log_id = self.db.insert_pipeline_log(
            company_id=company_id,
            step=step,
            source_name=source_name,
            status="running",
            raw_request=raw_request,
            started_at=datetime.now().isoformat(),
        )
        logger.debug(
            f"[{company_id}] Step '{step}' started (log_id={log_id})"
        )
        return log_id

    def log_step_end(
        self,
        log_id: int,
        status: str,
        credits_used: float = 0,
        error_message: str = None,
        metadata: Dict = None,
    ) -> None:
        """Log the end of a pipeline step.

        Args:
            log_id: ID from log_step_start.
            status: 'success' or 'failed'.
            credits_used: API credits consumed.
            error_message: Error description (if failed).
            metadata: Additional metadata dict.
        """
        updates = {
            "status": status,
            "credits_used": credits_used,
            "completed_at": datetime.now().isoformat(),
        }
        if error_message:
            updates["error_message"] = error_message
        if metadata:
            updates["metadata"] = json.dumps(metadata)

        # Direct update since we have log_id
        import sqlite3
        import os
        from src.database import DB_PATH

        conn = sqlite3.connect(DB_PATH)
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = tuple(updates.values()) + (log_id,)
        conn.execute(
            f"UPDATE pipeline_logs SET {set_clause} WHERE id = ?", values
        )
        conn.commit()
        conn.close()

        logger.debug(f"Log {log_id} ended: status={status}, credits={credits_used}")

    def log_event(
        self,
        event_type: str,
        company_id: int = None,
        data: Dict = None,
    ) -> None:
        """Log a custom event.

        Args:
            event_type: Event type string.
            company_id: Associated company (optional).
            data: Event data dict.
        """
        self.db.insert_pipeline_log(
            company_id=company_id,
            step="event",
            source_name=event_type,
            status="info",
            metadata=json.dumps(data) if data else None,
        )
