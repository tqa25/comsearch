# S3: URL Scoring Guide — Hệ Thống Chấm Điểm URL

> **MỤC ĐÍCH:** Agent xây dựng `filter_module.py` PHẢI hiểu rõ hệ thống chấm điểm này.

---

## Công Thức Tổng

```
Total Score = Domain Score + Keyword Bonus + TLD Bonus + Name Match Bonus
```

Tất cả ngưỡng điểm **có thể tùy chỉnh** qua biến môi trường (`.env`).

---

## 1. Domain Score

Xác định bằng loại domain. Config key: `DOMAIN_SCORES`

| Loại | Điểm mặc định | Domains ví dụ |
|---|---|---|
| `official` | **15** | Website chính của công ty |
| `legal` | **30** | `masothue.com`, `thuvienphapluat.vn`, `hosocongty.vn`, `yellowpages.vn` |
| `job` | **30** | `vietnamworks.com`, `topcv.vn`, `jobsgo.vn`, `vietcareer.vn` |
| `social` | **-100** | `facebook.com`, `linkedin.com` → Bị loại hoàn toàn |

**Tùy chỉnh:** `DOMAIN_SCORES={"official": 15, "legal": 30, "job": 30, "social": -100}`

### Known Domains Map

```python
KNOWN_DOMAINS = {
    "thuvienphapluat.vn":  ("thuvienphapluat", "legal"),
    "hosocongty.vn":       ("hosocongty",       "legal"),
    "masothue.com":        ("masothue",         "legal"),
    "yellowpages.vn":      ("yellowpages",      "official"),
    "vietnamworks.com":    ("vietnamworks",     "job"),
    "topcv.vn":            ("topcv",            "job"),
    "vietcareer.vn":       ("vietcareer",       "job"),
    "jobsgo.vn":           ("jobsgo",           "job"),
    "facebook.com":        ("facebook",         "social"),
    "linkedin.com":        ("linkedin",         "social"),
}
```

Nếu domain KHÔNG nằm trong danh sách → mặc định `official` (15 điểm).

---

## 2. Keyword Bonus

Kiểm tra từ khóa trong **URL path**. Config key: `KEYWORD_SCORES`

| Từ khóa | Điểm | Ví dụ URL path |
|---|---|---|
| `contact`, `lien-he`, `lienhe`, `contacts` | **+10** | `/lien-he`, `/contact-us` |
| `admin`, `hanh-chinh`, `hanchinh`, `administration` | **+10** | `/hanh-chinh` |
| `recruitment`, `tuyen-dung`, `tuyendung`, `career`, `careers`, `jobs` | **+5** | `/tuyen-dung` |

**Tùy chỉnh:** `KEYWORD_SCORES={"contact": 10, "admin": 10, "recruitment": 5}`

---

## 3. TLD Bonus

Điểm cộng theo đuôi tên miền. Config key: `TLD_SCORES`

| TLD | Điểm |
|---|---|
| `.vn`, `.com.vn`, `.com`, `.net`, `.org`, `.org.vn` | **+5** |
| `.info`, `.biz`, `.top`, `.xyz`, `.club`, `.tk`, `.ml`, `.ga` | **+2** |

**Tùy chỉnh:** `TLD_SCORES={"..."}`

---

## 4. Name Match Bonus (Fuzzy Matching)

So sánh tên công ty (cả EN lẫn VN) với domain, URL path, và title.

**Thuật toán:**
1. Normalize tên: bỏ dấu, lowercase, loại stop words (`Co.`, `Ltd`, `TNHH`, `CP`...)
2. Normalize domain: bỏ `www.`, bỏ TLD (`.com.vn`, `.com`...)
3. Sliding window `SequenceMatcher` so sánh từng cửa sổ
4. Nếu tỷ lệ khớp ≥ 80% → Bonus **0–20 điểm** (tuyến tính)

```
match_ratio = 0.80 → bonus = 0 điểm
match_ratio = 0.90 → bonus = 10 điểm
match_ratio = 1.00 → bonus = 20 điểm
```

---

## 5. Bộ Lọc Đặc Biệt

### Blacklist (score = 0, KHÔNG scrape)

```python
BLACKLISTED_DOMAINS = [
    "infocom.vn", "xinvoice.vn", "dauthau.info",
    "dauthau.net", "thuonghieuviet.info.vn", "fiingate.vn",
]
```

### Skip (score = 0, chỉ track)

```python
SKIP_DOMAINS = [
    "google.com", "youtube.com", "wikipedia.org", "baomoi.com",
    "vnexpress.net", "bing.com", "twitter.com", "tiktok.com",
    "pinterest.com", "amazon.com", "shopee.vn", "lazada.vn",
]
```

### Dedup

Mỗi domain chỉ giữ **1 URL đại diện** (URL đầu tiên gặp).

---

## 6. Early Stop

```
EARLY_STOP_SCORE = 35   # Điểm tối thiểu coi là "link xịn"
EARLY_STOP_COUNT = 10   # Số link xịn cần có để dừng search
```

**Logic:** Nếu đã có ≥ `EARLY_STOP_COUNT` URL với score ≥ `EARLY_STOP_SCORE` → dừng search ngay, chuyển sang Bước 5 Scrape.

**Tùy chỉnh:** Đặt trong `.env`:
```
EARLY_STOP_SCORE=35
EARLY_STOP_COUNT=10
```

---

## 7. Ví Dụ Tính Điểm

### Ví dụ 1: URL website chính
```
URL: https://abc-vina.com.vn/lien-he
Company: "ABC Vina Co., Ltd"

Domain Score:     15 (official — không nằm trong known domains)
TLD Bonus:        +5 (.com.vn)
Keyword Bonus:   +10 (lien-he → contact)
Name Match:      +18 (tên khớp 98% với domain "abc-vina")
─────────────────────
TOTAL:            48 ✅ (≥ 35)
```

### Ví dụ 2: URL pháp lý
```
URL: https://masothue.com/0123456789-cong-ty-abc
Company: "ABC Co., Ltd"

Domain Score:     30 (legal — masothue.com)
TLD Bonus:        +5 (.com)
Keyword Bonus:    +0 (không có từ khóa contact)
Name Match:       +5 (khớp 82% với path)
─────────────────────
TOTAL:            40 ✅
```

### Ví dụ 3: URL tin tức (bị skip)
```
URL: https://vnexpress.net/abc-company-mo-rong.html
→ Nằm trong SKIP_DOMAINS → score = 0, không scrape ❌
```
