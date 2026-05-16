# Task T1B: Gemini Quick Search — Bước 2: AI Search

## Role
Bạn là **Agent-B** (Wave 1), chịu trách nhiệm xây dựng module Gemini Quick Search (Bước 2 của pipeline).

## Context — ĐỌC TRƯỚC KHI LÀM
1. `skills/S1_project_architecture.md` — Kiến trúc file
2. `skills/S2_coding_conventions.md` — Quy ước code
3. `skills/S4_api_integration.md` — Pattern gọi API
4. `skills/S6_git_auto_branch.md` — Quy trình git
5. `docs/pipeline_workflow.md` — Sơ đồ vận hành (xem Bước 2)

## Input
- Foundation đã có: `config.py`, `database.py`, `errors.py`
- API: Google Gemini với Search Grounding
- Env var: `GEMINI_API_KEY`

## Task — Việc Cần Làm

### 1. Tạo `src/gemini_quick_search.py`

**Class `GeminiQuickSearch`:**

```python
def __init__(self, db, logger, config=None):
    # Khởi tạo Gemini client với search grounding

def search(self, company_id: int) -> dict:
    """Bước 2: AI Quick Search.
    
    Returns:
        {
            "result": {
                "core_name_vi": str,     # Tên pháp lý tiếng Việt
                "tax_code": str,          # Mã số thuế
                "phone": str,             # Số điện thoại (nếu tìm được)
                "address": str,
                "website": str,
                "confidence": float,      # 0.0 - 1.0
            },
            "grounding_urls": [str],      # ⭐ URLs mà Gemini đã "xem"
            "input_tokens": int,
            "output_tokens": int,
            "is_sufficient": bool,        # Có đủ dữ liệu không
            "fallback_reason": str,       # Lý do cần tiếp tục (nếu thiếu)
        }
    """
```

**Yêu cầu chi tiết:**
- Gọi Gemini model với `google_search` tool (grounding)
- Prompt bằng tiếng Việt, yêu cầu AI trả JSON
- Trích xuất `grounding_urls` từ grounding metadata của response
- `is_sufficient`: True nếu có phone VÀ confidence ≥ threshold
- **KHÔNG Early Stop**: Dù `is_sufficient=True`, pipeline vẫn tiếp tục (quyết định ở `pipeline.py`)
- Track daily quota: cập nhật `daily_quota.gemini_grounding_used`
- Handle errors: 429 → retry, quota exceeded → warning

**Prompt template (gợi ý):**
```
Tìm thông tin liên hệ của công ty "{company_name}".
Trả về JSON với các trường: core_name_vi, tax_code, phone, address, website, confidence.
- core_name_vi: Tên đăng ký kinh doanh bằng tiếng Việt
- tax_code: Mã số thuế (10 hoặc 13 chữ số)
- phone: Số điện thoại liên hệ
- confidence: Độ tin cậy (0.0 - 1.0)
```

## Output Mong Đợi
- 1 file: `src/gemini_quick_search.py`
- Có thể gọi: `quick.search(company_id)` → trả dict đúng format

## Constraints
- CHỈDÙNG `google-generativeai` library
- KHÔNG quyết định early stop (trả `is_sufficient` để pipeline quyết)
- `grounding_urls` PHẢI được trích xuất và trả về
- Xử lý graceful khi API key thiếu (warning, return empty)

## Git
```bash
git checkout -b ai/w1-gemini-quick-search
git commit -m "feat(gemini): add GeminiQuickSearch with grounding_urls extraction"
git push origin ai/w1-gemini-quick-search
```
