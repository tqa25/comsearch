# Task T1C: Search & Filter — Bước 4: Deep Search + Scoring

## Role
Bạn là **Agent-C** (Wave 1), chịu trách nhiệm xây dựng module Deep Search và URL Scoring (Bước 4 của pipeline). Đây là module QUAN TRỌNG NHẤT.

## Context — ĐỌC TRƯỚC KHI LÀM
1. `skills/S1_project_architecture.md` — Kiến trúc file
2. `skills/S2_coding_conventions.md` — Quy ước code
3. `skills/S3_url_scoring_guide.md` — ⭐ HỆ THỐNG CHẤM ĐIỂM (ĐỌC KỸ)
4. `skills/S4_api_integration.md` — Pattern gọi API
5. `skills/S6_git_auto_branch.md` — Quy trình git
6. `docs/pipeline_workflow.md` — Sơ đồ vận hành (xem Bước 4)

## Input
- Foundation đã có: `config.py`, `database.py`, `errors.py`, `schemas.py`
- API: Serper Search API (hoặc Firecrawl Search)
- Env var: `SERPER_API_KEY`, `FIRECRAWL_API_KEY`

## Task — Việc Cần Làm

### 1. Tạo `src/search_module.py`

**Class `SearchModule`:**

Bước 4 hoạt động như **vòng lặp if-else**. Dùng dữ liệu từ Bước 2 (Gemini), thực hiện tuần tự:

```python
def search_company(self, company_id: int, vn_name=None, tax_code=None) -> List[Dict]:
    """Execute deep search strategy (4.1 → 4.2 → 4.3 → 4.4).
    
    Logic:
    1. Run 4.1 Contact Query → score URLs
    2. If ≥ EARLY_STOP_COUNT links ≥ EARLY_STOP_SCORE → STOP
    3. Run 4.2 Infer VN Data (if missing vn_name/tax_code)
    4. Run 4.3 Tax Code Query (if tax_code available) → DEDUPE → score
    5. If ≥ EARLY_STOP_COUNT → STOP
    6. Run 4.4 Bare Query → DEDUPE → score
    """
```

**Sub-steps:**

- `_step1_contact_query(company_id, en_name, vn_name)` — Query: `("{EN}" OR "{VN}") AND ("liên hệ" OR "contact")`
- `_step2_infer_vn_data(company_id, results)` — Regex extract từ legal domains (masothue, thuvienphapluat...)
- `_step3_tax_query(company_id, tax_code)` — Query: `"{MST}"`
- `_step4_bare_query(company_id, en_name, vn_name)` — Query: `"{EN}" OR "{VN}"`

**⚠️ DEDUPE QUAN TRỌNG:**
- Ở bước 4.3 và 4.4: sau khi nhận URL từ API, PHẢI dedupe so với URL đã đạt điểm ở các bước trước
- Đảm bảo kết quả cuối cùng KHÔNG có URL trùng lặp
- Dedupe cũng so với `grounding_urls` từ Bước 2 (nếu có trong DB)

**Query cache:**
- Hash query (SHA-256) → check `query_cache` table → skip nếu đã search
- Populate cache sau mỗi API call

### 2. Tạo `src/filter_module.py`

**Class `LinkFilter`:**

Implement TOÀN BỘ hệ thống chấm điểm theo `skills/S3_url_scoring_guide.md`:

```python
def classify_url(self, url, company_name, title="", vn_name="") -> dict:
    """Score a single URL.
    Returns: {source_type, should_scrape, reason, relevance_score, score_breakdown}
    """

def score_urls_batch(self, urls, company_name, vn_name="") -> list:
    """Score a batch of URLs without saving to DB."""

def filter_company_links(self, company_id) -> list:
    """Classify, score, persist, and return filtered links."""
```

**PHẢI implement:**
- `BLACKLISTED_DOMAINS` list
- `SKIP_DOMAINS` list
- `KNOWN_DOMAINS` dict (domain → source_type, score_category)
- `KEYWORD_PATTERNS` list
- `_calculate_name_match_score()` — Fuzzy matching với SequenceMatcher
- TLD bonus
- Dedup by domain
- Early stop check

## Output Mong Đợi
- 2 files: `src/search_module.py`, `src/filter_module.py`
- SearchModule nhận vn_name + tax_code từ Bước 2, chạy 4 sub-steps
- FilterModule chấm điểm URL đúng công thức trong S3

## Constraints
- Query cache PHẢI hoạt động (giảm API calls)
- Dedup giữa các sub-steps PHẢI chính xác
- Scoring PHẢI match công thức trong `S3_url_scoring_guide.md`
- KHÔNG quyết định flow pipeline (chỉ return results)

## Git
```bash
git checkout -b ai/w1-search-and-filter
git commit -m "feat(search): add SearchModule with 4-step strategy and LinkFilter scoring"
git push origin ai/w1-search-and-filter
```
