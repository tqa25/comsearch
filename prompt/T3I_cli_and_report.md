# Task T3I: CLI & Report — CLI Runner + Excel Report

## Role
Bạn là **Agent-I** (Wave 3), chịu trách nhiệm tạo CLI entry point và Excel report template.

## Context — ĐỌC TRƯỚC KHI LÀM
1. `skills/S1_project_architecture.md` — Cấu trúc scripts/
2. `skills/S2_coding_conventions.md` — Quy ước code
3. `skills/S5_wsl_system_context.md` — Workflow chạy local
4. `skills/S6_git_auto_branch.md` — Quy trình git

## Input
- Wave 2 đã merge: pipeline hoàn chỉnh
- Module sẵn: `pipeline.py`, `excel_handler.py`, `result_aggregator.py`

## Task — Việc Cần Làm

### 1. Tạo `scripts/run_batch.py`

CLI entry point chính cho production:

```bash
# Chạy pipeline cho 100 công ty đầu tiên
python scripts/run_batch.py --limit 100

# Dry run (preview, không gọi API)
python scripts/run_batch.py --limit 100 --dry-run

# Resume từ checkpoint
python scripts/run_batch.py --resume --limit 100

# Retry failed companies
python scripts/run_batch.py --retry-failed

# Chạy từ file Excel mới
python scripts/run_batch.py --input data/new_companies.xlsx --limit 50

# Xuất report
python scripts/run_batch.py --report-only --output output/report.xlsx

# Replay mode (dùng data cached, không gọi API)
python scripts/run_batch.py --replay

# Force refresh (bypass cache)
python scripts/run_batch.py --limit 10 --force-refresh

# Chỉ định offset
python scripts/run_batch.py --limit 50 --offset 100
```

**Sử dụng `argparse`:**

```python
parser = argparse.ArgumentParser(description="Auto Search Company Pipeline")
parser.add_argument("--input", help="Path to input Excel file")
parser.add_argument("--output", default="output/", help="Output directory")
parser.add_argument("--limit", type=int, help="Max companies to process")
parser.add_argument("--offset", type=int, default=0, help="Skip N companies")
parser.add_argument("--resume", action="store_true", help="Resume from last checkpoint")
parser.add_argument("--retry-failed", action="store_true", help="Retry failed companies")
parser.add_argument("--dry-run", action="store_true", help="Preview without API calls")
parser.add_argument("--replay", action="store_true", help="Re-process from cached data")
parser.add_argument("--force-refresh", action="store_true", help="Bypass all caches")
parser.add_argument("--report-only", action="store_true", help="Generate report only")
```

**Flow:**
1. Load `.env`
2. Parse args
3. Validate: `--limit` bắt buộc (trừ `--resume`, `--retry-failed`, `--report-only`)
4. Nếu `--input`: đọc Excel → insert vào DB
5. Chạy pipeline
6. Tự động generate report khi xong

### 2. Tạo `scripts/run_evaluation.py`

```bash
# Chạy đánh giá chất lượng
python scripts/run_evaluation.py
python scripts/run_evaluation.py --output output/evaluation_report.xlsx
```

Sử dụng `QualityEvaluator` (nếu có) hoặc `ResultAggregator` để tạo report đánh giá.

## Output Mong Đợi
- `scripts/run_batch.py` — CLI runner hoàn chỉnh
- `scripts/run_evaluation.py` — Evaluation report
- Chạy: `python scripts/run_batch.py --help` → hiện help đầy đủ

## Constraints
- `--limit` BẮT BUỘC khi chạy mới (tránh chạy hết tất cả accidentally)
- Auto-generate report filename với date: `report_YYYY-MM-DD.xlsx`
- Tất cả output vào `output/` directory
- Print progress rõ ràng: `[1/100] Processing ABC Co...`

## Git
```bash
git checkout -b ai/w3-cli-and-report
git commit -m "feat(cli): add run_batch.py CLI with resume, retry, and report options"
git push origin ai/w3-cli-and-report
```
