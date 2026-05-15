# S2: Coding Conventions — Quy Ước Code Python

> **MỤC ĐÍCH:** Đảm bảo code từ nhiều AI agent có thể merge mà không xung đột style.

---

## 1. Python Version & Environment

- **Python 3.10+** (type hints bắt buộc)
- Virtual env: `python -m venv venv && source venv/bin/activate`
- Dependencies: `pip install -r requirements.txt`

## 2. Import Order

```python
# 1. Standard library
import os
import json
import time
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional

# 2. Third-party
import requests
from dotenv import load_dotenv

# 3. Internal modules
from src.database import DatabaseManager
from src.logger import PipelineLogger
from src.config import default_config
from src.errors import RetryableError, CriticalError
```

## 3. Error Handling Hierarchy

```python
# Defined in src/errors.py
class PipelineError(Exception):
    """Base exception for all pipeline errors."""
    pass

class RetryableError(PipelineError):
    """Error that can be retried (e.g., 429 rate limit)."""
    pass

class CriticalError(PipelineError):
    """Error that must stop the pipeline immediately (e.g., 402 credits exhausted)."""
    pass

class SkippableError(PipelineError):
    """Error that allows skipping this company and moving to next."""
    pass
```

**Quy tắc sử dụng:**
- `429 Rate Limit` → `RetryableError`
- `402 Credits Exhausted` → `CriticalError`
- `Parsing error cho 1 công ty` → `SkippableError`
- Exception không xác định → log + skip, KHÔNG raise CriticalError

## 4. Logging

```python
# ĐÚNG: dùng logging module
import logging
logger = logging.getLogger(__name__)

logger.info(f"[{company_id}] Processing company: {name}")
logger.warning(f"[{company_id}] Rate limited, retrying...")
logger.error(f"[{company_id}] Failed: {error}")

# SAI: KHÔNG dùng print() trong src/ modules
print("Processing...")  # ❌ Chỉ dùng print trong scripts/
```

## 5. Config Pattern

```python
# Mọi config đọc từ env var, có default:
self.SEARCH_LIMIT: int = _parse_int(os.getenv("SEARCH_LIMIT"), default=100)
self.EARLY_STOP_SCORE: int = _parse_int(os.getenv("EARLY_STOP_SCORE"), default=35)

# Import config:
from src.config import default_config
# Hoặc nhận qua constructor:
def __init__(self, db, logger, config=None):
    from src.config import default_config
    self.config = config or default_config
```

## 6. Class & Method Structure

```python
class ModuleName:
    """Brief description of what this module does."""

    def __init__(self, db: DatabaseManager, logger: PipelineLogger, config=None):
        from src.config import default_config
        self.config = config or default_config
        self.db = db
        self.logger = logger

    # -- Public API --
    def public_method(self, company_id: int) -> dict:
        """Do something for a company.
        
        Args:
            company_id: The company ID to process.
            
        Returns:
            Dict with results.
            
        Raises:
            RetryableError: If rate limited.
            CriticalError: If credits exhausted.
        """
        pass

    # -- Private helpers --
    def _internal_helper(self) -> None:
        pass
```

## 7. Docstrings

- **Style:** Google style
- **Language:** Tiếng Anh
- Bắt buộc cho: class, public methods
- Optional cho: private methods (nếu logic phức tạp)

## 8. Type Hints

```python
# Bắt buộc cho tất cả function signatures
def search_company(self, company_id: int, vn_name: str = None) -> List[Dict]:
    ...

def classify_url(self, url: str, company_name: str) -> dict:
    ...
```

## 9. Database Access Pattern

```python
# Mọi DB access PHẢI qua DatabaseManager
# KHÔNG viết SQL trực tiếp trong module khác

# ĐÚNG:
result = self.db.get_company(company_id)
self.db.update_company(company_id, status='searched')
self.db.insert_search_result(company_id=cid, url=url, ...)

# SAI:
import sqlite3
conn = sqlite3.connect('data/company_data.db')  # ❌
```

## 10. Naming Conventions

| Loại | Convention | Ví dụ |
|---|---|---|
| File | snake_case | `search_module.py` |
| Class | PascalCase | `SearchModule`, `LinkFilter` |
| Method | snake_case | `search_company()`, `classify_url()` |
| Constant | UPPER_SNAKE | `EARLY_STOP_SCORE`, `CREDITS_PER_SEARCH` |
| Private | prefix `_` | `_internal_helper()`, `_extract_domain()` |
