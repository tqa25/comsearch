# S4: API Integration Patterns — Chuẩn Gọi API Bên Ngoài

> **MỤC ĐÍCH:** Chuẩn hóa cách tất cả module gọi external API (Firecrawl, Gemini, Serper).

---

## 1. API Keys (từ `.env`)

```
FIRECRAWL_API_KEY=fc-xxx     # Search URL + Scrape nội dung
GEMINI_API_KEY=xxx           # AI Quick Search + AI Extract
SERPER_API_KEY=xxx           # Deep Search queries
```

## 2. Credit Tracking

| API | Action | Credit Cost |
|---|---|---|
| Firecrawl | Search (1 query) | **2 credits** |
| Firecrawl | Scrape (1 page) | **1 credit** |
| Serper | Search (1 query) | **1 credit** (≤10 results), **2 credits** (>10) |
| Gemini | Grounding search | **Tính theo daily quota** (1450/ngày free tier) |
| Gemini | AI Extract | **Free tier: 15 RPM** |

Mọi credit PHẢI được log vào `pipeline_logs.credits_used`.

## 3. Retry Pattern

```python
def _api_call_with_retry(self, func, max_retries=3):
    for attempt in range(1, max_retries + 1):
        try:
            result = func()
            if self.rate_limiter:
                self.rate_limiter.report_success()
            return result
            
        except RateLimitError:  # HTTP 429
            if self.rate_limiter:
                self.rate_limiter.report_error(429)
            if attempt < max_retries:
                wait = 60 * attempt  # Exponential: 60s, 120s
                logger.warning(f"Rate limited. Waiting {wait}s (attempt {attempt})")
                time.sleep(wait)
            else:
                raise RetryableError(f"Rate limited after {max_retries} retries")
                
        except CreditExhausted:  # HTTP 402
            raise CriticalError("API credits exhausted. STOP immediately.")
            
        except requests.RequestException as e:  # Network error
            if attempt < max_retries:
                time.sleep(5)
            else:
                raise RetryableError(f"Network error: {e}")
```

## 4. HTTP Response Handling

| Status Code | Hành động | Exception |
|---|---|---|
| `200` | Success → parse response | — |
| `402` | Credits hết → **DỪNG PIPELINE NGAY** | `CriticalError` |
| `429` | Rate limited → retry with backoff | `RetryableError` |
| `403` | Forbidden → log + skip | `SkippableError` |
| `5xx` | Server error → retry | `RetryableError` |

## 5. Rate Limiter Pattern

```python
class AdaptiveRateLimiter:
    """Adaptive pacing based on API responses."""
    
    def wait(self):
        """Wait before next API call."""
        time.sleep(self.current_delay)
    
    def report_success(self):
        """Decrease delay on success (min 1s)."""
        self.current_delay = max(1.0, self.current_delay * 0.9)
    
    def report_error(self, status_code: int):
        """Increase delay on error."""
        if status_code == 429:
            self.current_delay = min(120.0, self.current_delay * 2.0)
```

## 6. Connection Pool Pattern

```python
class ConnectionManager:
    """Reuse HTTP sessions for better performance."""
    
    def __init__(self, api_key: str):
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        })
    
    def post(self, url, json, request_type="search"):
        return self.session.post(url, json=json, timeout=30)
```

## 7. Timeout Settings

| API Call | Timeout |
|---|---|
| Firecrawl Search | **30s** |
| Firecrawl Scrape | **35s** |
| Gemini AI Extract | **60s** |
| Serper Search | **15s** |

## 8. Quy Tắc Bắt Buộc

1. **KHÔNG hardcode API key** trong source code
2. **LUÔN log** credits_used vào `pipeline_logs`
3. **LUÔN kiểm tra** HTTP 402 trước khi xử lý response
4. **KHÔNG gọi API** nếu có cache hit (query_cache table)
5. Rate limiter **wait()** TRƯỚC mỗi API call
