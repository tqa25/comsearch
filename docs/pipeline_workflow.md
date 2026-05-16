# Pipeline Workflow — Sơ Đồ Vận Hành App `comsearch`

## Tổng Quan

Hệ thống **Auto Search Company** tự động tìm kiếm thông tin liên hệ doanh nghiệp Việt Nam từ tên công ty tiếng Anh. Quy trình **4 bước tuần tự**: `1 → 2 → 4 → 5`.

> **Bước 3 (Google Maps):** Giữ lại như optional feature, phát triển sau.

---

## Sơ Đồ Tổng Quan

```
┌─────────────────────────────────────────────────────┐
│                  📥 BƯỚC 1: INPUT                    │
│  Excel → companies table → status = 'pending'       │
│  Cơ chế: Resumable (tiếp tục từ chỗ dở dang)       │
└────────────────────┬────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────┐
│            🤖 BƯỚC 2: AI QUICK SEARCH                │
│  Gemini + Google Search Grounding                    │
│  Output: core_name_vi, tax_code, phone, address,     │
│          website, confidence, grounding_urls          │
│  ⚠️ KHÔNG có Early Stop ở bước này                   │
│  → Luôn tiếp tục sang Bước 4                        │
└────────────────────┬────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────┐
│         🔍 BƯỚC 4: DEEP SEARCH (Vòng lặp)           │
│                                                      │
│  ┌───────────────────────────────────┐               │
│  │ 4.1 Contact Query                 │               │
│  │ Query: (EN OR VN) AND contact     │               │
│  └──────────┬────────────────────────┘               │
│             │ Chấm điểm + Lọc                        │
│             │                                        │
│       ≥ N link đạt ≥ threshold? ──YES──→ Bước 5     │
│             │ NO                                     │
│             ▼                                        │
│  ┌───────────────────────────────────┐               │
│  │ 4.2 Infer VN Data (nếu thiếu)    │               │
│  │ Regex: Tên pháp lý + MST từ URL  │               │
│  └──────────┬────────────────────────┘               │
│             ▼                                        │
│  ┌───────────────────────────────────┐               │
│  │ 4.3 Tax Code Query (nếu có MST)  │               │
│  │ Query: "{MST}" + DEDUPE          │               │
│  └──────────┬────────────────────────┘               │
│             │ Chấm điểm + Lọc                        │
│       ≥ N link? ──YES──→ Bước 5                     │
│             │ NO                                     │
│             ▼                                        │
│  ┌───────────────────────────────────┐               │
│  │ 4.4 Bare Query (vét cuối)        │               │
│  │ Query: EN OR VN + DEDUPE         │               │
│  └──────────┬────────────────────────┘               │
│             │                                        │
└─────────────┼───────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────┐
│      🕷️ BƯỚC 5: SCRAPE + AI EXTRACT                 │
│                                                      │
│  5.1 Firecrawl Scrape                                │
│      Top N URL (mặc định 10) → HTML → Markdown      │
│                                                      │
│  5.2 AI Extractor                                    │
│      Regex pre-filter → Gemini trích xuất JSON       │
│      Output: phone, email, address, representative   │
│      Xử lý xung đột: so sánh confidence_score       │
│                                                      │
│  → status = 'done' → Excel Report                    │
└─────────────────────────────────────────────────────┘
```

---

## Bảng Đầu Vào / Đầu Ra

| Bước | Đầu vào | Đầu ra | Early Stop? |
|---|---|---|---|
| **1** | File Excel (tên công ty) | `companies` table, `status='pending'` | ❌ |
| **2** | Tên công ty thô | `vietnamese_name`, `tax_code`, `grounding_urls` | ❌ (luôn tiếp tục) |
| **4.1** | Tên EN + VN | URL đã chấm điểm | ✅ Nếu ≥ N link ≥ threshold |
| **4.2** | URL từ 4.1 (domain uy tín) | `vietnamese_name`, `tax_code` (cập nhật) | ❌ |
| **4.3** | MST (nếu có) | URL mới (đã dedupe) | ✅ Nếu ≥ N link ≥ threshold |
| **4.4** | Tên EN + VN | URL mới (đã dedupe) | ❌ (bước cuối) |
| **5.1** | Top N URL | Markdown content | ❌ |
| **5.2** | Markdown | `extracted_contacts` + Excel report | ❌ |

---

## Hệ Thống Chấm Điểm URL

```
Total = Domain Score + Keyword Bonus + TLD Bonus + Name Match Bonus
```

| Thành phần | Điểm | Tùy chỉnh |
|---|---|---|
| Domain (official) | 15 | `DOMAIN_SCORES` |
| Domain (legal/job) | 30 | `DOMAIN_SCORES` |
| Keyword (contact) | +10 | `KEYWORD_SCORES` |
| TLD (.vn, .com) | +5 | `TLD_SCORES` |
| Name Match (≥80%) | 0–20 | Fuzzy matching |
| **Early Stop threshold** | **≥ 35** | `EARLY_STOP_SCORE` |
| **Early Stop count** | **≥ 10** | `EARLY_STOP_COUNT` |

Chi tiết đầy đủ: xem `skills/S3_url_scoring_guide.md`

---

## Company Status Machine

```
pending → searching → searched → scraping → scraped → extracting → ai_done → done
                                                                              ↑
failed (retryable) ─────────────────────────────────────────────────────────┘
permanently_failed (sau max retries)
```
