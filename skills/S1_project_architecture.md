# S1: Project Architecture — Kiến Trúc Dự Án `comsearch`

> **MỤC ĐÍCH:** Mọi AI agent PHẢI đọc file này trước khi tạo bất kỳ file nào. Đảm bảo code đúng chỗ, đúng tên, đúng module boundary.

---

## 1. Cấu Trúc Thư Mục

```
comsearch/
├── .env                         # API keys (KHÔNG commit lên git)
├── .env.example                 # Template API keys
├── .gitignore
├── CLAUDE.md                    # Context tổng hợp cho AI agent
├── requirements.txt             # Python dependencies
│
├── skills/                      # Hướng dẫn cho AI agents (KHÔNG SỬA)
│   ├── S1_project_architecture.md
│   ├── S2_coding_conventions.md
│   ├── S3_url_scoring_guide.md
│   ├── S4_api_integration.md
│   ├── S5_wsl_system_context.md
│   └── S6_git_auto_branch.md
│
├── docs/                        # Tài liệu dự án
│   └── pipeline_workflow.md     # Sơ đồ vận hành pipeline
│
├── prompt/                      # Prompt cho từng AI agent task
│   └── *.md
│
├── src/                         # SOURCE CODE CHÍNH
│   ├── __init__.py
│   ├── config.py                # Centralized config (env vars + defaults)
│   ├── database.py              # DatabaseManager — tất cả DB reads/writes
│   ├── schemas.py               # Data validation schemas
│   ├── errors.py                # Custom exception hierarchy
│   ├── gemini_quick_search.py   # Bước 2: AI Quick Search
│   ├── search_module.py         # Bước 4: Deep Search (Serper queries)
│   ├── filter_module.py         # Bước 4: URL scoring & filtering
│   ├── scrape_module.py         # Bước 5.1: Firecrawl scrape
│   ├── ai_extractor.py          # Bước 5.2: Gemini contact extraction
│   ├── pipeline.py              # Orchestrator: kết nối tất cả bước
│   ├── excel_handler.py         # Đọc Excel input + ghi report
│   ├── result_aggregator.py     # Tổng hợp extracted_contacts
│   ├── logger.py                # Structured logging to pipeline_logs
│   ├── rate_limiter.py          # Adaptive rate limiting
│   ├── connection_pool.py       # HTTP connection reuse
│   └── health_monitor.py        # Credit usage tracking
│
├── scripts/                     # CLI entry points
│   └── run_batch.py             # Main CLI runner
│
├── tests/                       # Test files
│   ├── test_database.py
│   ├── test_filter_module.py
│   ├── test_search_module.py
│   └── test_integration.py
│
├── data/                        # Runtime data (gitignored)
│   └── company_data.db          # SQLite database
│
└── output/                      # Generated reports (gitignored)
    └── *.xlsx
```

## 2. Quy Tắc Tạo File

| Quy tắc | Chi tiết |
|---|---|
| Source code | PHẢI nằm trong `src/` |
| Test files | PHẢI nằm trong `tests/`, prefix `test_` |
| Scripts CLI | PHẢI nằm trong `scripts/` |
| Import path | Luôn dùng `from src.module import Class` |
| Không tạo | File ở root ngoài `.env`, `CLAUDE.md`, `requirements.txt`, `.gitignore` |

## 3. Database Schema (SQLite)

File: `data/company_data.db`

### Bảng `companies`
```sql
CREATE TABLE companies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    original_name TEXT NOT NULL,          -- Tên công ty gốc (EN/VN)
    vietnamese_name TEXT,                 -- Tên pháp lý VN (từ Bước 2/4.2)
    tax_code TEXT,                        -- Mã số thuế (từ Bước 2/4.2)
    address TEXT,
    status TEXT DEFAULT 'pending',        -- Trạng thái pipeline
    vn_data_source TEXT,                  -- Nguồn dữ liệu VN (snippet/scrape)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Bảng `search_results`
```sql
CREATE TABLE search_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL,
    search_query TEXT,                    -- Query gửi đi
    search_type TEXT,                     -- step1_contact / step3_tax / step4_bare
    result_rank INTEGER,
    url TEXT,
    title TEXT,
    snippet TEXT,
    credits_used REAL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES companies(id)
);
```

### Bảng `filtered_links`
```sql
CREATE TABLE filtered_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    search_result_id INTEGER,
    company_id INTEGER NOT NULL,
    url TEXT NOT NULL,
    source_type TEXT,                     -- official_website / legal / job / ...
    should_scrape BOOLEAN DEFAULT 1,
    reason TEXT,
    relevance_score REAL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES companies(id)
);
```

### Bảng `scraped_pages`
```sql
CREATE TABLE scraped_pages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL,
    filtered_link_id INTEGER,
    url TEXT,
    source_type TEXT,
    markdown_content TEXT,               -- Nội dung đã scrape
    content_length INTEGER DEFAULT 0,
    scrape_status TEXT DEFAULT 'pending', -- pending / success / failed
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES companies(id)
);
```

### Bảng `extracted_contacts`
```sql
CREATE TABLE extracted_contacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL,
    source_type TEXT,                    -- Nguồn trích xuất
    source_url TEXT,
    address TEXT,
    phone TEXT,
    email TEXT,
    website TEXT,
    fax TEXT,
    representative TEXT,
    raw_ai_response TEXT,
    confidence_score REAL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES companies(id)
);
```

### Bảng `pipeline_logs`
```sql
CREATE TABLE pipeline_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER,
    step TEXT,                           -- search / filter / scrape / ai_extract
    source_name TEXT,
    status TEXT,                         -- success / failed
    credits_used REAL DEFAULT 0,
    network_latency_ms REAL,
    error_message TEXT,
    error_category TEXT,
    raw_request TEXT,
    raw_response_summary TEXT,
    metadata TEXT,                       -- JSON
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);
```

### Bảng `query_cache`
```sql
CREATE TABLE query_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query_hash TEXT UNIQUE NOT NULL,
    query_text TEXT,
    company_id INTEGER,
    result_count INTEGER DEFAULT 0,
    expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Bảng `daily_quota`
```sql
CREATE TABLE daily_quota (
    date TEXT PRIMARY KEY,
    gemini_grounding_used INTEGER DEFAULT 0,
    serper_used INTEGER DEFAULT 0
);
```

## 4. Data Flow

```
[Excel Input]
     ↓
[companies table] (status: pending)
     ↓  Bước 2: Gemini Quick Search
[companies table] (updated: vietnamese_name, tax_code) + grounding_urls
     ↓  Bước 4: Deep Search
[search_results] → [filtered_links] (scored, deduped)
     ↓  Bước 5: Scrape + Extract
[scraped_pages] → [extracted_contacts]
     ↓
[companies table] (status: done) → [Excel Report]
```

## 5. Company Status Machine

```
pending → searching → searched → scraping → scraped → extracting → ai_done → done
                                                                              ↑
failed (retryable) ─────────────────────────────────────────────────────────┘
permanently_failed (sau max retries)
```

## 6. Module Dependency Graph

```
pipeline.py (orchestrator)
  ├── gemini_quick_search.py    (Bước 2)
  ├── search_module.py          (Bước 4 - queries)
  │   └── filter_module.py      (Bước 4 - scoring)
  ├── scrape_module.py          (Bước 5.1)
  ├── ai_extractor.py           (Bước 5.2)
  ├── result_aggregator.py      (tổng hợp)
  └── excel_handler.py          (I/O)

Shared dependencies (mọi module đều dùng):
  ├── database.py
  ├── config.py
  ├── logger.py
  ├── errors.py
  └── schemas.py
```
