# Task T0: Foundation — Setup Nền Tảng Dự Án

## Role
Bạn là **Agent-0**, chịu trách nhiệm xây dựng nền tảng (foundation) cho dự án `comsearch`.

## Context — ĐỌC TRƯỚC KHI LÀM
1. `skills/S1_project_architecture.md` — Kiến trúc file + DB schema
2. `skills/S2_coding_conventions.md` — Quy ước code
3. `skills/S6_git_auto_branch.md` — Quy trình git

## Input
- Project root: `~/workspaces/comsearch/`
- Đã có sẵn: thư mục `skills/`, `docs/`, `prompt/`, `src/`, `tests/`, `data/`, `output/`

## Task — Việc Cần Làm

### 1. Tạo `src/__init__.py`
File rỗng, đánh dấu `src` là Python package.

### 2. Tạo `src/errors.py`
Custom exception hierarchy:
```
PipelineError (base)
├── RetryableError    (429, network error → retry)
├── CriticalError     (402, credits hết → dừng ngay)
└── SkippableError    (parse error → skip công ty, tiếp tục)
```

### 3. Tạo `src/schemas.py`
Validation functions cho:
- `validate_search_result(data: dict)` — kiểm tra có `url` field
- `validate_scored_link(data: dict)` — kiểm tra có `url`, `relevance_score`, `should_scrape`
- `validate_company(data: dict)` — kiểm tra có `original_name`

### 4. Tạo `src/config.py`
Centralized config class đọc từ env vars, bao gồm:
- Search: `SEARCH_LIMIT=100`, `EARLY_STOP_COUNT=10`, `EARLY_STOP_SCORE=35`
- Scoring: `DOMAIN_SCORES`, `KEYWORD_SCORES`, `TLD_SCORES` (JSON dicts)
- Scrape: `TOP_N=10`, `CONTACT_DISCOVERY_ENABLED=True`
- Dedup: `ENABLE_QUERY_DEDUP=True`, `CACHE_TTL_DAYS=7`
- Rate limit: `DELAY_SECONDS=3.0`, `MAX_RETRIES=3`
- Gemini: `GEMINI_QUICK_MODEL`, `GEMINI_DAILY_LIMIT=1450`
- Serper: `SERPER_ENABLED=True`, `SERPER_NUM_RESULTS=10`

Tham chiếu `skills/S3_url_scoring_guide.md` cho giá trị default của scoring.

### 5. Tạo `src/database.py`
DatabaseManager class với:
- `__init__`: tạo DB file tại `data/company_data.db`, auto-create tables
- CRUD methods cho 7 bảng (xem S1 skill cho schema)
- Mỗi method mở + đóng connection riêng (KHÔNG thread-safe)
- Methods quan trọng: `get_company()`, `update_company()`, `insert_search_result()`, `insert_filtered_link()`, `get_search_results_for_company()`, `get_scraped_pages_for_company()`, `is_query_cached()`, `insert_query_cache()`

### 6. Tạo `.env.example`
```
FIRECRAWL_API_KEY=fc-your-api-key
GEMINI_API_KEY=your-gemini-api-key
SERPER_API_KEY=your-serper-api-key
```

### 7. Tạo `.gitignore`
```
.env
venv/
__pycache__/
data/*.db
output/
*.pyc
.DS_Store
```

### 8. Tạo `requirements.txt`
```
requests
python-dotenv
openpyxl
google-generativeai
```

## Output Mong Đợi
- 8 files mới
- Tất cả import hoạt động: `python -c "from src.config import default_config; print(default_config)"`
- DB tạo được: `python -c "from src.database import DatabaseManager; db = DatabaseManager(); print('OK')"`

## Constraints
- KHÔNG tạo file ngoài danh sách trên
- KHÔNG viết business logic (search, filter, scrape...)
- Chỉ tạo "khung xương" cho các module khác build lên

## Git
```bash
git checkout -b ai/w0-foundation
git add .
git commit -m "chore(foundation): add config, database, schemas, errors, and project setup"
git push origin ai/w0-foundation
```
