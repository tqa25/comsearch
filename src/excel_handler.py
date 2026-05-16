import logging
import os
from datetime import datetime
from typing import Dict, List, Optional

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from src.config import default_config
from src.database import DatabaseManager

logger = logging.getLogger(__name__)


HEADER_KEYWORDS = {
    "company_name": ["company", "name", "english", "tên", "công ty"],
    "tax_code": ["tax", "mst", "mã số thuế", "tax code", "tin"],
}


def _detect_column(headers: List[str], keywords: List[str]) -> Optional[int]:
    """Find column index matching any keyword (case-insensitive)."""
    for idx, header in enumerate(headers):
        header_lower = str(header).lower().strip()
        if any(kw in header_lower for kw in keywords):
            return idx
    return None


class ExcelReader:
    """Read company names from input Excel files."""

    def read_companies(self, file_path: str) -> List[Dict]:
        """Read companies from Excel file with auto-detect columns.

        Args:
            file_path: Path to input Excel file.

        Returns:
            List of dicts with 'original_name' and optional 'tax_code'.

        Raises:
            FileNotFoundError: If file does not exist.
            ValueError: If file is empty or has no valid rows.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Excel file not found: {file_path}")

        wb = load_workbook(file_path, read_only=True, data_only=True)
        ws = wb.active

        if ws is None:
            raise ValueError("Excel file has no active sheet")

        rows_iter = ws.iter_rows(values_only=True)

        # Read header row
        try:
            headers = next(rows_iter)
        except StopIteration:
            raise ValueError("Excel file is empty — no header row found")

        if headers is None:
            raise ValueError("Excel file is empty — no header row found")

        # Auto-detect columns
        name_col = _detect_column(list(headers), HEADER_KEYWORDS["company_name"])
        tax_col = _detect_column(list(headers), HEADER_KEYWORDS["tax_code"])

        if name_col is None:
            # Fallback: use first column
            logger.warning(
                "Could not detect company name column, using first column"
            )
            name_col = 0

        companies: List[Dict] = []
        for row_num, row in enumerate(rows_iter, start=2):
            if row is None:
                continue

            name_val = row[name_col] if name_col < len(row) else None
            # Skip rows without a string company name
            if not isinstance(name_val, str) or not name_val.strip():
                continue

            tax_val = None
            if tax_col is not None and tax_col < len(row):
                val = row[tax_col]
                if val is not None:
                    tax_val = str(val).strip()

            companies.append({
                "original_name": name_val.strip(),
                "tax_code": tax_val if tax_val else None,
            })

        wb.close()

        if not companies:
            raise ValueError(
                f"No valid company rows found in {file_path}"
            )

        logger.info(f"Read {len(companies)} companies from {file_path}")
        return companies


class ExcelWriter:
    """Write pipeline results to Excel report files."""

    # Styling constants
    HEADER_FONT = Font(bold=True, color="FFFFFF", size=11)
    HEADER_FILL = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    HEADER_ALIGNMENT = Alignment(horizontal="center", vertical="center")

    def write_results(self, output_path: str, results: List[Dict]) -> None:
        """Write basic results to Excel.

        Args:
            output_path: Output file path.
            results: List of result dicts.
        """
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

        wb = Workbook()
        ws = wb.active
        ws.title = "Results"

        headers = ["Company", "Phone", "Email", "Website", "Address"]
        self._write_header(ws, headers)

        for idx, result in enumerate(results, start=2):
            ws.cell(row=idx, column=1, value=result.get("company_name", ""))
            ws.cell(row=idx, column=2, value=result.get("phone", ""))
            ws.cell(row=idx, column=3, value=result.get("email", ""))
            ws.cell(row=idx, column=4, value=result.get("website", ""))
            ws.cell(row=idx, column=5, value=result.get("address", ""))

        self._auto_width(ws)
        wb.save(output_path)
        logger.info(f"Wrote {len(results)} results to {output_path}")

    def write_final_report(
        self,
        output_path: str,
        aggregated_data: List[Dict],
        summary_stats: Dict,
    ) -> None:
        """Write complete report with detail and summary sheets.

        Args:
            output_path: Output file path.
            aggregated_data: List of company result dicts.
            summary_stats: Dict with summary statistics.
        """
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

        wb = Workbook()

        # ── Sheet 1: Chi tiết ──
        ws_detail = wb.active
        ws_detail.title = "Chi tiết"

        detail_headers = [
            "STT", "Tên công ty (EN)", "Tên tiếng Việt", "Mã số thuế",
            "Phone", "Email", "Địa chỉ", "Website", "Nguồn", "Độ tin cậy",
        ]
        self._write_header(ws_detail, detail_headers)

        for idx, row_data in enumerate(aggregated_data, start=2):
            ws_detail.cell(row=idx, column=1, value=idx - 1)
            ws_detail.cell(row=idx, column=2, value=row_data.get("original_name", ""))
            ws_detail.cell(row=idx, column=3, value=row_data.get("vietnamese_name", ""))
            ws_detail.cell(row=idx, column=4, value=row_data.get("tax_code", ""))
            ws_detail.cell(row=idx, column=5, value=row_data.get("phone", ""))
            ws_detail.cell(row=idx, column=6, value=row_data.get("email", ""))
            ws_detail.cell(row=idx, column=7, value=row_data.get("address", ""))
            ws_detail.cell(row=idx, column=8, value=row_data.get("website", ""))
            ws_detail.cell(row=idx, column=9, value=row_data.get("source", ""))
            ws_detail.cell(row=idx, column=10, value=row_data.get("confidence", ""))

        self._auto_width(ws_detail)
        ws_detail.freeze_panes = "A2"

        # ── Sheet 2: Thống kê ──
        ws_summary = wb.create_sheet("Thống kê")

        summary_headers = ["Chỉ số", "Giá trị"]
        self._write_header(ws_summary, summary_headers)

        stats_rows = [
            ("Tổng công ty xử lý", summary_stats.get("total_companies", 0)),
            ("Tìm được phone", summary_stats.get("found_phone", 0)),
            ("% tìm được phone", summary_stats.get("phone_pct", "0%")),
            ("Tìm được email", summary_stats.get("found_email", 0)),
            ("Bước 2 thành công (Gemini)", summary_stats.get("step2_success", 0)),
            ("Bước 4 thành công (Deep Search)", summary_stats.get("step4_success", 0)),
            ("Thất bại (lỗi)", summary_stats.get("failed", 0)),
            ("Gemini requests", summary_stats.get("gemini_requests", 0)),
            ("Serper credits", summary_stats.get("serper_credits", 0)),
            ("Firecrawl credits", summary_stats.get("firecrawl_credits", 0)),
        ]

        for idx, (label, value) in enumerate(stats_rows, start=2):
            ws_summary.cell(row=idx, column=1, value=label)
            ws_summary.cell(row=idx, column=2, value=value)

        self._auto_width(ws_summary)

        wb.save(output_path)
        logger.info(f"Wrote final report to {output_path}")

    def _write_header(self, ws, headers: List[str]) -> None:
        """Write styled header row."""
        for col_idx, header in enumerate(headers, start=1):
            cell = ws.cell(row=1, column=col_idx, value=header)
            cell.font = self.HEADER_FONT
            cell.fill = self.HEADER_FILL
            cell.alignment = self.HEADER_ALIGNMENT

    def _auto_width(self, ws) -> None:
        """Auto-adjust column widths."""
        for col_idx, column_cells in enumerate(ws.columns, start=1):
            max_length = 0
            column_letter = get_column_letter(col_idx)
            for cell in column_cells:
                if cell.value:
                    max_length = max(max_length, len(str(cell.value)))
            adjusted_width = min(max_length + 2, 50)
            ws.column_dimensions[column_letter].width = max(adjusted_width, 10)
