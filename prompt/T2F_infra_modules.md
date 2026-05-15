# Task T2F: Infra Modules — Logger, Rate Limiter, Connection Pool

## Role
Bạn là **Agent-F** (Wave 2), chịu trách nhiệm xây dựng các module infrastructure hỗ trợ pipeline.

## Context — ĐỌC TRƯỚC KHI LÀM
1. `skills/S1_project_architecture.md` — Kiến trúc file
2. `skills/S2_coding_conventions.md` — Quy ước code
3. `skills/S4_api_integration.md` — ⭐ Pattern API (rate limiter, connection pool)
4. `skills/S6_git_auto_branch.md` — Quy trình git

## Input
- Foundation đã có: `config.py`, `database.py`, `errors.py`

## Task — Việc Cần Làm

### 1. Tạo `src/logger.py`

**Class `PipelineLogger`:**
- Structured logging vào `pipeline_logs` table
- `log_step_start(company_id, step, source_name, raw_request=None) -> int` (trả log_id)
- `log_step_end(log_id, status, credits_used=0, error_message=None, metadata=None)`
- `log_event(event_type, company_id, data)` — log sự kiện tùy ý
- Tất cả metadata lưu dạng JSON string

### 2. Tạo `src/rate_limiter.py`

**Class `AdaptiveRateLimiter`:**
- `wait()` — sleep trước mỗi API call
- `report_success()` — giảm delay (min 1.0s)
- `report_error(status_code)` — tăng delay (max 120s)
- Adaptive: 429 → delay x2, success → delay x0.9
- Constructor: `AdaptiveRateLimiter(initial_delay=3.0, min_delay=1.0, max_delay=120.0)`

### 3. Tạo `src/connection_pool.py`

**Class `ConnectionManager`:**
- Quản lý `requests.Session` với persistent headers
- `__init__(api_key, base_url=None)` — tạo session với Authorization header
- `post(url, json, request_type="search") -> Response`
- `get(url, params=None) -> Response`
- Connection reuse để giảm TCP overhead
- Timeout mặc định theo request_type (search=30s, scrape=35s)

### 4. Tạo `src/health_monitor.py`

**Class `HealthMonitor`:**
- Track credit usage trong session
- `track_credits(api_name, credits_used)` — cộng dồn
- `get_summary() -> dict` — trả {api_name: credits_used}
- `estimate_remaining(total_companies, processed)` — ước tính thời gian còn lại
- `print_status()` — in trạng thái ra console

## Output Mong Đợi
- 4 files: `src/logger.py`, `src/rate_limiter.py`, `src/connection_pool.py`, `src/health_monitor.py`
- Tất cả đều independent, có thể import riêng lẻ

## Constraints
- Logger PHẢI ghi vào DB qua `DatabaseManager`
- Rate limiter PHẢI thread-safe (dùng `threading.Lock` nếu cần)
- ConnectionManager KHÔNG store API key trong log
- Tất cả module PHẢI có default fallback (hoạt động ngay cả khi không config)

## Git
```bash
git checkout -b ai/w2-infra-modules
git commit -m "feat(infra): add PipelineLogger, AdaptiveRateLimiter, ConnectionManager, HealthMonitor"
git push origin ai/w2-infra-modules
```
