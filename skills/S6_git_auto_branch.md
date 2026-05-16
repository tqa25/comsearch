# S6: Git Auto-Branch & Push — Quy Trình Git Tự Động

> **MỤC ĐÍCH:** Mỗi khi AI agent hoàn thành task, tự động tạo nhánh mới và push lên GitHub.

---

## 1. Branch-per-Ask Strategy

**Nguyên tắc:** Một branch = Một task = Một kết quả rõ ràng.

### Branch Naming Convention

```
ai/dev
```

**Branch cho task cụ thể (nếu cần):**

| Task | Branch Name |
|---|---|
| T0: Foundation | `ai/w0-foundation` |
| T1A: Excel Handler | `ai/w1-excel-handler` |
| T1B: Gemini Quick Search | `ai/w1-gemini-quick-search` |
| T1C: Search & Filter | `ai/w1-search-and-filter` |
| T1D: Scrape & Extract | `ai/w1-scrape-and-extract` |
| T2E: Pipeline Orchestrator | `ai/w2-pipeline-orchestrator` |
| T2F: Infra Modules | `ai/w2-infra-modules` |
| T3G: Unit Tests | `ai/w3-unit-tests` |
| T3H: Integration Test | `ai/w3-integration-test` |
| T3I: CLI & Report | `ai/w3-cli-and-report` |

## 2. Commit Convention (Conventional Commits)

```
<type>(<scope>): <description>

feat(search): add 4-step deep search strategy
fix(filter): correct TLD bonus for .com.vn domains
refactor(pipeline): remove early stop from step 2
test(filter): add unit tests for URL scoring
docs(skills): update S3 with yellowpages.vn
chore(config): add SERPER_API_KEY to .env.example
```

**Types:**

| Type | Khi nào dùng |
|---|---|
| `feat` | Thêm feature mới |
| `fix` | Sửa bug |
| `refactor` | Thay đổi code không ảnh hưởng behavior |
| `test` | Thêm/sửa tests |
| `docs` | Chỉ thay đổi documentation |
| `chore` | Config, build, tooling |

## 3. Workflow Từng Bước

### Trước khi code:

```bash
# 1. Đảm bảo đang ở main mới nhất
git checkout main
git pull origin main

# 2. Chuyển sang branch dev
git checkout ai/dev
```

### Sau khi code xong:

```bash
# 3. Kiểm tra thay đổi
git status
git diff

# 4. Chạy test (nếu có)
python -m pytest tests/ -v

# 5. Stage và commit
git add .
git commit -m "feat(excel): add ExcelReader and ExcelWriter classes"

# 6. Push lên GitHub
git push origin ai/dev

# 7. Thông báo user review
echo "✅ Đã push branch ai/dev. Vui lòng review và merge."
```

## 4. Quy Tắc An Toàn

| ✅ ĐƯỢC PHÉP | ❌ KHÔNG BAO GIỜ |
|---|---|
| Tạo branch mới từ `main` | Force push (`git push -f`) |
| Push lên branch `ai/*` | Push trực tiếp lên `main` |
| Commit thường xuyên (mỗi logical unit) | Merge branch không qua review |
| Sửa conflict trên branch mình | Xóa branch của người khác |
| Rebase từ main nếu cần | Rewrite history đã push |

## 5. Merge Strategy

```
Tất cả code phát triển → Push lên ai/dev
Khi hoàn thành feature → User merge ai/dev vào main
```

> **QUAN TRỌNG:** Mọi thay đổi code đều push lên `ai/dev`. KHÔNG push trực tiếp lên `main`.

## 6. Pre-Push Checklist

Trước khi push, agent PHẢI kiểm tra:

- [ ] Code chạy không lỗi syntax: `python -c "import src.{module}"`
- [ ] Tests pass (nếu có): `python -m pytest tests/ -v`
- [ ] Không commit file `.env` (check `.gitignore`)
- [ ] Không commit `data/*.db` hoặc `output/*`
- [ ] Commit message đúng Conventional Commits format
