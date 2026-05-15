# Task T3G: Unit Tests — Tests Cho Từng Module

## Role
Bạn là **Agent-G** (Wave 3), chịu trách nhiệm viết unit tests cho tất cả module trong `src/`.

## Context — ĐỌC TRƯỚC KHI LÀM
1. `skills/S1_project_architecture.md` — Biết cấu trúc module
2. `skills/S2_coding_conventions.md` — Quy ước test
3. `skills/S3_url_scoring_guide.md` — Để viết test cho scoring
4. `skills/S6_git_auto_branch.md` — Quy trình git

## Input
- Wave 2 đã merge: tất cả module trong `src/` đã hoàn chỉnh
- Library: `pytest`

## Task — Việc Cần Làm

### Tạo test files trong `tests/`:

#### `tests/test_database.py`
- Test tạo DB, tạo tables
- Test CRUD: insert company, get company, update status
- Test insert_search_result, insert_filtered_link
- Test query_cache: insert, check is_cached
- Test edge cases: company not found, duplicate insert

#### `tests/test_filter_module.py` (QUAN TRỌNG NHẤT)
- Test classify_url với từng loại domain:
  - official website → score ~15-40
  - legal domain (masothue) → score ~30+
  - blacklisted → score = 0
  - skip domain → score = 0
  - social → score = -100
- Test keyword bonus: URL có `/lien-he` → +10
- Test TLD bonus: `.com.vn` → +5
- Test name match: tên khớp 90% → bonus ~10
- Test early stop logic: ≥10 links ≥ 35
- Test dedup by domain

#### `tests/test_search_module.py`
- Test query generation cho mỗi step (4.1, 4.3, 4.4)
- Test dedup logic giữa steps
- Test query cache hit/miss
- Mock API calls (KHÔNG gọi API thật)

#### `tests/test_config.py`
- Test default values
- Test env var override
- Test JSON dict parsing

#### `tests/test_errors.py`
- Test exception hierarchy
- Test isinstance checks

### Quy tắc test:

```python
import pytest
from unittest.mock import MagicMock, patch

# Mock database
@pytest.fixture
def mock_db():
    db = MagicMock()
    db.get_company.return_value = {
        "id": 1, "original_name": "ABC Co., Ltd",
        "vietnamese_name": "Công ty TNHH ABC", "tax_code": "0123456789",
        "status": "pending"
    }
    return db

# Mock logger
@pytest.fixture
def mock_logger():
    return MagicMock()
```

## Output Mong Đợi
- 5+ test files trong `tests/`
- Chạy: `python -m pytest tests/ -v` → tất cả PASS
- Coverage: ít nhất test scoring logic và database CRUD

## Constraints
- KHÔNG gọi API thật (mock tất cả)
- KHÔNG tạo/sửa file trong `src/`
- Test PHẢI chạy offline (không cần .env)
- Sử dụng `pytest` + `unittest.mock`

## Git
```bash
git checkout -b ai/w3-unit-tests
git commit -m "test(all): add unit tests for database, filter, search, config modules"
git push origin ai/w3-unit-tests
```
