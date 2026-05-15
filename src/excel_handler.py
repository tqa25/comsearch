import logging
import os
from typing import Any, Dict, List, Optional

import openpyxl
from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter

from src.database import DatabaseManager
from src.config import default_config

logger = logging.getLogger(__name__)


class ExcelReader:
    """Reads company data from Excel input files with auto-detected columns."""

    def read_companies(self, file_path: str) -> List[Dict[str, Any]]:
        """Read companies from an Excel file with auto-detected columns.

        Scans headers for keywords like "company name", "english", "tax code"
        (case-insensitive). Skips rows without a company name.

        Args:
            file_path: Path to the Excel file.

        Returns:
            List of dicts with keys 'original_name' and optionally 'tax_code'.

        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError: If the sheet is empty or format is invalid.
        """
        if not os.path.isfile(file_path):
            raise FileNotFoundError(f"Excel file not found: {file_path}")

        wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
        try:
            ws = wb.active
            if ws is None or ws.max_row is None or ws.max_row < 1:
                raise ValueError("Excel sheet is empty or has no rows")

            rows_iter = ws.iter_rows(values_only=True)
            header_row = next(rows_iter, None)
            if header_row is None:
                raise ValueError("Excel sheet has no header row")

            headers = [str(cell).strip().lower() if cell else "" for cell in header_row]

            name_idx = self._find_column_index(headers, ["company name", "english", "company"])
            tax_idx = self._find_column_index(headers, ["tax code", "tax", "mst"])

            if name_idx is None:
                raise ValueError(
                    "Could not detect company name column. "
                    "Expected header containing: 'company name', 'english', or 'company'"
                )

            companies: List[Dict[str, Any]] = []
            for row in rows_iter:
                name_cell = row[name_idx] if name_idx < len(row) else None
                if name_cell is None or not isinstance(name_cell, str) or not name_cell.strip():
                    continue
                company: Dict[str, Any] = {"original_name": name_cell.strip()}
                if tax_idx is not None and tax_idx < len(row):
                    tax_val = row[tax_idx]
                    if tax_val is not None:
                        company["tax_code"] = str(tax_val).strip()
                companies.append(company)

            return companies
        finally:
            wb.close()

    @staticmethod
    def _find_column_index(headers: List[str], keywords: List[str]) -> Optional[int]:
        """Find column index whose header contains one of the given keywords.

        Args:
            headers: List of header strings (lowercased).
            keywords: List of keywords to search for.

        Returns:
            Index of the matching column, or None if not found.
        """
        for keyword in keywords:
            for i, header in enumerate(headers):
                if keyword in header:
                    return i
        return None


class ExcelWriter:
    """Writes company results and final reports to Excel files."""

    def __init__(self, db: Optional[DatabaseManager] = None, config=None):
        self.config = config or default_config
        self.db = db

    def write_results(self, output_path: str, results: List[Dict[str, Any]]) -> str:
        """Write basic search results to an Excel file.

        Args:
            output_path: Destination path for the output file.
            results: List of result dicts.

        Returns:
            The absolute path of the written file.
        """
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Results"

        if not results:
            ws.append(["No results"])
        else:
            headers = list(results[0].keys())
            ws.append(headers)
            for result in results:
                ws.append([result.get(h, "") for h in headers])

        self._apply_styling(ws)
        output_path = os.path.abspath(output_path)
        wb.save(output_path)
        logger.info(f"Results written to {output_path}")
        return output_path

    def write_final_report(
        self,
        output_path: str,
        aggregated_data: List[Dict[str, Any]],
        summary_stats: Dict[str, Any],
    ) -> str:
        """Write a complete final report with two sheets.

        Sheet 1 "Chi tiết": One row per company with contact details.
        Sheet 2 "Thống kê": Summary statistics.

        Args:
            output_path: Destination path for the output file.
            aggregated_data: List of company detail dicts.
            summary_stats: Dict of summary statistics.

        Returns:
            The absolute path of the written file.
        """
        wb = openpyxl.Workbook()

        ws_detail = wb.active
        ws_detail.title = "Chi tiết"

        detail_headers = [
            "Tên công ty", "MST", "Phone", "Email",
            "Địa chỉ", "Website", "Nguồn", "Độ tin cậy",
        ]
        ws_detail.append(detail_headers)
        for company in aggregated_data:
            ws_detail.append([
                company.get("original_name", ""),
                company.get("tax_code", ""),
                company.get("phone", ""),
                company.get("email", ""),
                company.get("address", ""),
                company.get("website", ""),
                company.get("source", ""),
                company.get("confidence", ""),
            ])
        self._apply_styling(ws_detail)

        ws_stats = wb.create_sheet(title="Thống kê")
        ws_stats.append(["Chỉ tiêu", "Giá trị"])
        stat_rows = [
            ("Tổng số công ty", summary_stats.get("total_companies", 0)),
            ("Tỷ lệ tìm được phone", summary_stats.get("phone_found_pct", 0)),
            ("Tỷ lệ tìm được email", summary_stats.get("email_found_pct", 0)),
            ("Tỷ lệ theo từng bước", summary_stats.get("step_pct", "")),
            ("Credits đã sử dụng", summary_stats.get("credits_used", 0)),
        ]
        for label, value in stat_rows:
            ws_stats.append([label, value])
        self._apply_styling(ws_stats)

        output_path = os.path.abspath(output_path)
        wb.save(output_path)
        logger.info(f"Final report written to {output_path}")
        return output_path

    @staticmethod
    def _apply_styling(ws: Any) -> None:
        """Apply header bold, auto-width columns, and freeze top row.

        Args:
            ws: An openpyxl worksheet object.
        """
        header_font = Font(bold=True)
        for cell in ws[1]:
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center")

        for col_idx in range(1, ws.max_column + 1):
            max_length = 0
            col_letter = get_column_letter(col_idx)
            for row in ws.iter_rows(min_col=col_idx, max_col=col_idx, values_only=True):
                cell_value = row[0]
                if cell_value is not None:
                    max_length = max(max_length, len(str(cell_value)))
            ws.column_dimensions[col_letter].width = min(max_length + 3, 60)

        ws.freeze_panes = "A2"
