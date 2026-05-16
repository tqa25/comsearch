# Task T1D: Scrape & Extract — Bước 5: Scrape + AI Extract

## Role
Bạn là **Agent-D** (Wave 1), chịu trách nhiệm xây dựng module scrape nội dung web và AI trích xuất thông tin liên hệ (Bước 5 pipeline).

## Context — ĐỌC TRƯỚC KHI LÀM
1. `skills/S1_project_architecture.md` — Kiến trúc file
2. `skills/S2_coding_conventions.md` — Quy ước code
3. `skills/S4_api_integration.md` — Pattern gọi API (retry, rate limit)
4. `skills/S6_git_auto_branch.md` — Quy trình git
5. `docs/pipeline_workflow.md` — Sơ đồ vận hành (xem Bước 5)

## Input
- Foundation đã có: `config.py`, `database.py`, `errors.py`
- APIs: Firecrawl Scrape API, Google Gemini AI
- Env vars: `FIRECRAWL_API_KEY`, `GEMINI_API_KEY`

## Task — Việc Cần Làm

### 1. Tạo `src/scrape_module.py`

**Class `ScrapeModule`:**

```python
def scrape_company(self, company_id: int, delay: float = 3.0) -> List[Dict]:
    """Scrape top N URLs (by relevance_score) for a company.
    
    1. Lấy filtered_links từ DB (should_scrape=1, order by relevance_score DESC)
    2. Lấy top N links (config.TOP_N, mặc định 10)
    3. Gọi Firecrawl Scrape API cho từng URL
    4. Lưu markdown content vào scraped_pages table
    """

def discover_contact_pages(self, company_id: int, delay: float = 3.0) -> List[Dict]:
    """Khám phá thêm trang liên hệ từ website chính.
    
    Nếu đã có website chính, thử scrape thêm:
    - /contact, /lien-he, /about
    """
```

**Yêu cầu:**
- Firecrawl API endpoint: `https://api.firecrawl.dev/v1/scrape`
- Request body: `{"url": url, "formats": ["markdown"], "timeout": 30000}`
- Xử lý response: extract `data.markdown`
- Credit: 1 credit per scrape
- Rate limit: `delay_seconds` giữa mỗi request
- Error handling: 429 → retry, 402 → CriticalError

### 2. Tạo `src/ai_extractor.py`

**Class `AIExtractor`:**

```python
def extract_for_company(self, company_id: int, delay: float = 3.0):
    """Trích xuất thông tin liên hệ từ tất cả scraped pages của công ty.
    
    1. Lấy scraped_pages (scrape_status='success')
    2. Sắp xếp theo priority: legal first, social last
    3. Cho mỗi page:
       a. Regex pre-filter: có cụm số giống SĐT không?
       b. Nếu có → gọi Gemini AI trích xuất JSON
       c. Lưu vào extracted_contacts
    """

def extract_from_page(self, page_id: int) -> dict:
    """Trích xuất từ 1 scraped page."""
```

**Regex pre-filter:**
```python
# Kiểm tra có chuỗi giống SĐT VN không
PHONE_PATTERN = r'(?:\+84|0)\d{9,10}'
# Nếu không match → skip page (tiết kiệm API)
```

**AI Extraction prompt (tiếng Việt):**
```
Trích xuất thông tin liên hệ từ nội dung sau. Trả về JSON:
{
  "phone": "số điện thoại",
  "email": "email",
  "address": "địa chỉ",
  "representative": "người đại diện",
  "fax": "số fax",
  "confidence": 0.0-1.0
}
Nếu không tìm thấy trường nào, để null.
```

**Xử lý xung đột:**
- Nhiều pages có SĐT khác nhau → so sánh `confidence_score` → giữ cao nhất
- Truncate markdown > 30,000 chars trước khi gửi AI

## Output Mong Đợi
- 2 files: `src/scrape_module.py`, `src/ai_extractor.py`
- ScrapeModule lấy top N URL → scrape → lưu markdown
- AIExtractor pre-filter → AI extract → lưu contacts

## Constraints
- Regex pre-filter PHẢI chạy trước AI call (tiết kiệm credit)
- Truncate markdown > 30,000 chars
- Handle 429 rate limit: backoff 60s, max 3 retries
- Processing order: `masothue` → `legal` → `official` → `job` → `social`

## Git
```bash
git checkout -b ai/w1-scrape-and-extract
git commit -m "feat(scrape): add ScrapeModule and AIExtractor with regex pre-filter"
git push origin ai/w1-scrape-and-extract
```
