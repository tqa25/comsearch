# Task T1A: Excel Handler — Đọc/Ghi Excel

## Role
Bạn là **Agent-A** (Wave 1), chịu trách nhiệm xây dựng module đọc file Excel đầu vào và ghi report đầu ra.

## Context — ĐỌC TRƯỚC KHI LÀM
1. `skills/S1_project_architecture.md` — Kiến trúc file
2. `skills/S2_coding_conventions.md` — Quy ước code
3. `skills/S6_git_auto_branch.md` — Quy trình git

## Input
- Foundation đã có: `config.py`, `database.py`, `schemas.py`, `errors.py`
- Library: `openpyxl`

## Task — Việc Cần Làm

### 1. Tạo `src/excel_handler.py`

**Class `ExcelReader`:**
- `read_companies(file_path: str) -> List[Dict]`
- Auto-detect columns: scan headers tìm keywords "company name", "english", "tax code" (case-insensitive)
- Skip rows không có tên công ty (string)
- Return: `[{"original_name": "ABC Co.", "tax_code": "0123456789"}, ...]`
- Xử lý: file không tồn tại, sheet rỗng, format sai

**Class `ExcelWriter`:**
- `write_results(output_path: str, results: List[Dict])` — ghi kết quả cơ bản
- `write_final_report(output_path: str, aggregated_data: List[Dict], summary_stats: Dict)` — ghi report hoàn chỉnh 2 sheets:
  - **Sheet 1 "Chi tiết":** Mỗi row = 1 công ty (tên, MST, phone, email, address, website, source, confidence)
  - **Sheet 2 "Thống kê":** Tổng công ty, % tìm được phone, % theo từng bước, credits used
- Styling: header bold, auto-width columns, freeze top row

## Output Mong Đợi
- 1 file: `src/excel_handler.py`
- Test thủ công: tạo file Excel mẫu, đọc được, ghi report được

## Constraints
- KHÔNG gọi API
- KHÔNG import module khác ngoài `database.py`, `config.py`
- Xử lý file Excel PHẢI dùng `openpyxl` (không pandas)

## Git
```bash
git checkout -b ai/w1-excel-handler
git commit -m "feat(excel): add ExcelReader and ExcelWriter with auto-detect columns"
git push origin ai/w1-excel-handler
```
