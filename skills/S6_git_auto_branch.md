# S6: Git Auto-Branch & Push — Quy Trình Git Tự Động

> **MỤC ĐÍCH:** Mỗi khi AI agent hoàn thành task, tự động tạo nhánh, code, và push lên GitHub theo mô hình "branch-on-branch".

---

## 1. Cấu Trúc Branch

```
main (ổn định — chỉ user mới merge vào đây)
  └── ai/dev (nhánh tích hợp chính — gộp tất cả task)
        ├── ai/task-{tên-1} (nhánh con — task cụ thể 1)
        ├── ai/task-{tên-2} (nhánh con — task cụ thể 2)
        └── ai/task-{tên-3} (nhánh con — task cụ thể 3)
```

### Branch Naming Convention

| Loại | Tên | Mô tả |
|---|---|---|
| Tích hợp chính | `ai/dev` | Gộp tất cả task đã hoàn thành |
| Task con | `ai/task-{mô-tả-ngắn}` | Ví dụ: `ai/task-login-form`, `ai/task-user-api` |

---

## 2. Phân Vai Rõ Ràng

### WORKER (worker-frontend, worker-backend, worker-database)
- **Được làm:** Code → commit → push branch task → báo cáo cho orchestrator
- **KHÔNG được:** Tự merge branch, tự xóa branch, push lên `ai/dev` hoặc `main`

### ORCHESTRATOR
- **Được làm:** Nhận báo cáo từ worker → gọi code-reviewer → nếu PASS thì merge vào `ai/dev` → xóa branch task → push `ai/dev`
- **Quyết định:** Khi nào task đủ điều kiện để merge

### CODE-REVIEWER
- **Được làm:** Review code trên branch task → báo cáo PASS/FAIL cho orchestrator
- **KHÔNG được:** Tự merge, tự push

---

## 3. Commit Convention (Conventional Commits)

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

---

## 4. Workflow Chi Tiết

### BƯỚC 1: Orchestrator tạo branch task

```bash
# Đảm bảo đang trên ai/dev mới nhất
git checkout ai/dev
git pull origin ai/dev

# Tạo branch task từ ai/dev
git checkout -b ai/task-{tên-task}
```

### BƯỚC 2: Worker code trên branch task

Worker nhận branch đã tạo, thực hiện:
1. Code theo yêu cầu
2. Test locally (nếu có test)
3. Commit từng logical unit

```bash
git add .
git commit -m "feat(auth): add login form with validation"
```

### BƯỚC 3: Worker push branch task

```bash
git push origin ai/task-{tên-task}
```

### BƯỚC 4: Worker báo cáo cho Orchestrator

Worker gửi báo cáo:
```
Task: {tên task}
Branch: ai/task-{tên-task}
Trạng thái: Hoàn thành
Files thay đổi: [list files]
Test result: PASS/FAIL
```

### BƯỚC 5: Orchestrator gọi Code-Reviewer

Orchestrator dispatch code-reviewer để review branch task.

### BƯỚC 6: Xử lý kết quả review

**Nếu PASS:**
```bash
# 1. Chuyển về ai/dev
git checkout ai/dev
git pull origin ai/dev

# 2. Merge branch task vào ai/dev
git merge ai/task-{tên-task} --no-ff -m "merge: {tên task} into ai/dev"

# 3. Push ai/dev lên remote
git push origin ai/dev

# 4. Xóa branch task (local + remote)
git branch -d ai/task-{tên-task}
git push origin --delete ai/task-{tên-task}
```

**Nếu FAIL:**
- Orchestrator gửi feedback lại worker
- Worker checkout lại branch task → sửa → commit → push → báo cáo lại
- Lặp lại bước 5-6 cho đến khi PASS

---

## 5. Quy Tắc An Toàn

| ✅ ĐƯỢC PHÉP | ❌ KHÔNG BAO GIỜ |
|---|---|
| Tạo branch task từ `ai/dev` | Force push (`git push -f`) |
| Push branch task lên remote | Push trực tiếp lên `main` |
| Commit thường xuyên (mỗi logical unit) | Merge branch không qua review |
| Sửa conflict trên branch mình | Xóa branch của người khác |
| Rebase từ ai/dev nếu cần | Rewrite history đã push |
| Orchestrator merge sau khi review PASS | Worker tự merge |

---

## 6. Merge Strategy

```
Task hoàn thành → Worker push branch task
                 → Code-Reviewer review
                 → Nếu PASS: Orchestrator merge vào ai/dev → xóa branch task
                 → Nếu FAIL: Worker sửa → review lại

Khi tất cả task xong → User review ai/dev → merge vào main (nếu muốn)
```

> **QUAN TRỌNG:**
> - Worker KHÔNG tự merge. Chỉ orchestrator mới được merge.
> - Branch task tồn tại ngắn: tạo → code → review → merge → xóa.
> - `ai/dev` là nguồn sự thật duy nhất cho code đã tích hợp.

---

## 7. Pre-Push Checklist

Trước khi push branch task, worker PHẢI kiểm tra:

- [ ] Code chạy không lỗi syntax: `python -c "import src.{module}"`
- [ ] Tests pass (nếu có): `python -m pytest tests/ -v`
- [ ] Không commit file `.env` (check `.gitignore`)
- [ ] Không commit `data/*.db` hoặc `output/*`
- [ ] Commit message đúng Conventional Commits format
- [ ] Đã báo cáo đầy đủ cho orchestrator

---

## 8. Xử Lý Conflict

Nếu có conflict khi merge branch task vào `ai/dev`:

1. Orchestrator checkout `ai/dev` → pull mới nhất
2. Thử merge: `git merge ai/task-{tên-task}`
3. Nếu conflict → orchestrator tự resolve hoặc yêu cầu worker resolve
4. Sau khi resolve xong → commit merge → push `ai/dev`
5. Xóa branch task
