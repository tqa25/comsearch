# Task T2E: Pipeline Orchestrator — Kết Nối Toàn Bộ Pipeline

## Role
Bạn là **Agent-E** (Wave 2), chịu trách nhiệm xây dựng `pipeline.py` — module điều phối kết nối tất cả bước 1→2→4→5.

## Context — ĐỌC TRƯỚC KHI LÀM
1. `skills/S1_project_architecture.md` — Kiến trúc + Status Machine
2. `skills/S2_coding_conventions.md` — Quy ước code
3. `skills/S6_git_auto_branch.md` — Quy trình git
4. `docs/pipeline_workflow.md` — ⭐ SƠ ĐỒ VẬN HÀNH (ĐỌC KỸ)

## Input
- Wave 1 modules đã merge vào `main`:
  - `src/excel_handler.py` (T1A)
  - `src/gemini_quick_search.py` (T1B)
  - `src/search_module.py` + `src/filter_module.py` (T1C)
  - `src/scrape_module.py` + `src/ai_extractor.py` (T1D)

## Task — Việc Cần Làm

### Tạo `src/pipeline.py`

**Class `Pipeline`:**

```python
class Pipeline:
    STATUS_FLOW = {
        'pending': 'search',
        'searching': 'search',
        'searched': 'filter',
        'scraping': 'filter',
        'scraped': 'ai_extract',
        'extracting': 'ai_extract',
        'failed': 'search',
    }

    def __init__(self, config: dict, pipeline_config=None):
        # Khởi tạo tất cả sub-modules

    def run(self, company_ids=None, limit=None, offset=0,
            replay_mode=False, force_refresh=False):
        """Main pipeline loop cho danh sách công ty."""

    def resume(self):
        """Resume pipeline từ chỗ bị gián đoạn."""

    def retry_failed(self, max_retries=2):
        """Retry các công ty bị failed."""
```

**Logic chính trong `run()` cho MỖI công ty:**

```
1. BƯỚC 2: Gemini Quick Search
   → Lấy core_name_vi, tax_code, grounding_urls
   → ⚠️ KHÔNG Early Stop ở đây (luôn tiếp tục)
   → Lưu kết quả vào DB

2. BƯỚC 4: Deep Search
   → search_module.search_company(company_id, vn_name, tax_code)
   → filter_module.filter_company_links(company_id)

3. BƯỚC 5: Scrape + Extract
   → scrape_module.scrape_company(company_id)
   → ai_extractor.extract_for_company(company_id)

4. Kiểm tra kết quả
   → Có phone? → status = 'done'
   → Không phone? → status = 'done' (nhưng log warning)
```

**Các feature bắt buộc:**
- **Resumable:** Kiểm tra `status` của company → resume từ step phù hợp
- **Graceful shutdown:** Bắt SIGINT/SIGTERM → hoàn thành company hiện tại → dừng
- **Batch stats:** Đếm success/fail/skip, credits used, log summary cuối
- **Checkpoint:** Cập nhật `status` sau mỗi step (search→searched→scraped→done)
- **Bước 3 (Maps):** Giữ như optional, mặc định TẮT. Có thể bật qua config

**Batch summary report (cuối mỗi run):**
```
═══════════════════════════════════════
  BÁO CÁO PIPELINE - 2026-05-15
═══════════════════════════════════════
  Tổng công ty xử lý:            50
  Bước 2 thành công (Gemini):     45 (90%)
  Bước 4 thành công (Deep):       40
  Không tìm được phone:           5
  Thất bại (lỗi):                 2
  Gemini requests:                48 / 1450
  Serper credits:                 120
═══════════════════════════════════════
```

### Tạo `src/result_aggregator.py`

```python
class ResultAggregator:
    def aggregate_all(self) -> List[Dict]:
        """Tổng hợp extracted_contacts cho tất cả companies."""

    def generate_summary_stats(self, data) -> Dict:
        """Thống kê: tổng, % phone, % email, credits..."""
```

## Output Mong Đợi
- 2 files: `src/pipeline.py`, `src/result_aggregator.py`
- Pipeline chạy được: `Pipeline(config).run(limit=5)`
- Resume hoạt động: interrupt → resume → tiếp tục đúng chỗ

## Constraints
- Bước 2 KHÔNG có Early Stop
- Bước 3 (Maps) là optional, mặc định TẮT
- Status PHẢI được checkpoint vào DB sau mỗi step
- CriticalError (402) PHẢI dừng toàn bộ pipeline ngay lập tức

## Git
```bash
git checkout -b ai/w2-pipeline-orchestrator
git commit -m "feat(pipeline): add Pipeline orchestrator with resume and graceful shutdown"
git push origin ai/w2-pipeline-orchestrator
```
