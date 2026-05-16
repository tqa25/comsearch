# Task T3H: Integration Test — Test End-to-End Pipeline

## Role
Bạn là **Agent-H** (Wave 3), chịu trách nhiệm viết integration test chạy pipeline end-to-end với dữ liệu mẫu.

## Context — ĐỌC TRƯỚC KHI LÀM
1. `skills/S1_project_architecture.md` — Data flow
2. `skills/S6_git_auto_branch.md` — Quy trình git
3. `docs/pipeline_workflow.md` — Flow pipeline đầy đủ

## Input
- Wave 2 đã merge: pipeline hoàn chỉnh
- Cần: `.env` với API keys thật (hoặc mock)

## Task — Việc Cần Làm

### 1. Tạo `tests/test_integration.py`

**Test scenario:** Chạy pipeline cho 3-5 công ty mẫu VN.

```python
SAMPLE_COMPANIES = [
    "FPT Software",
    "Vinamilk",
    "Vietcombank",
    "Hoa Phat Group",
    "Techcombank",
]
```

**Test cases:**

1. **test_full_pipeline_flow**
   - Tạo DB mới (tmp)
   - Insert 5 công ty mẫu
   - Chạy pipeline.run()
   - Assert: tất cả company status = 'done'
   - Assert: ít nhất 3/5 có phone

2. **test_resume_after_interrupt**
   - Chạy pipeline cho 2 công ty
   - Giả lập interrupt (set company 3 = 'searched')
   - Gọi pipeline.resume()
   - Assert: company 3 tiếp tục từ filter, không search lại

3. **test_early_stop_in_search**
   - Mock search trả về 15 URL score > 35
   - Assert: step 4.3 và 4.4 KHÔNG được gọi

4. **test_no_phone_still_completes**
   - Mock: tất cả scrape trả về text không có SĐT
   - Assert: company status = 'done' (không bị stuck)

### 2. Tạo `tests/fixtures/sample_input.xlsx`

File Excel mẫu chứa 5 công ty ở trên.

### 3. Tạo `tests/conftest.py`

Shared fixtures: temp DB, mock API responses.

## Output Mong Đợi
- `tests/test_integration.py`
- `tests/conftest.py`
- `tests/fixtures/sample_input.xlsx`
- Chạy: `python -m pytest tests/test_integration.py -v`

## Constraints
- Có thể mock API nếu không muốn dùng credit thật
- Sử dụng tmp directory cho DB (không ảnh hưởng data/)
- Test PHẢI cleanup sau khi xong

## Git
```bash
git checkout -b ai/w3-integration-test
git commit -m "test(integration): add end-to-end pipeline test with 5 sample companies"
git push origin ai/w3-integration-test
```
