# Hướng Dẫn Sử Dụng Team Agent trong OpenCode AI

## Cấu trúc team đã tạo

```
.opencode/
├── opencode.json                    # Config chính
└── agents/
    ├── orchestrator.md              # MANAGER - nhận yêu cầu & điều phối
    ├── worker-frontend.md           # WORKER - frontend development
    ├── worker-backend.md            # WORKER - backend development
    ├── worker-database.md           # WORKER - database tasks
    ├── code-reviewer.md             # REVIEWER - review code + test
    └── prompt-optimizer.md          # OPTIMIZER - tối ưu prompt (có sẵn)
```

## Cách hoạt động

```
USER → @orchestrator → Phân tích yêu cầu
            ↓
    ┌───────┬──────────┬──────────┐
    ↓       ↓          ↓          ↓
  Frontend Backend  Database   Explorer   (CHẠY SONG SONG)
    ↓       ↓          ↓          ↓
         TỔNG HỢP KẾT QUẢ
            ↓
       Code Reviewer → Test + Review
            ↓
         USER (kết quả cuối cùng)
```

## Cách sử dụng

### 1. Khởi động OpenCode với orchestrator

Mở terminal và chạy:
```bash
opencode
```

Sau đó chuyển sang orchestrator agent bằng cách:
- Gõ `@orchestrator` trước prompt
- Hoặc nhấn `Tab` để cycle qua các agents và chọn `orchestrator`

### 2. Gửi yêu cầu

Cú pháp:
```
@orchestrator <mô tả yêu cầu của bạn>
```

---

## VÍ DỤ CỤ THỂ

### Ví dụ 1: Xây dựng tính năng Login

```
@orchestrator Xây dựng tính năng đăng nhập cho ứng dụng web bao gồm:
- Frontend: Form login với email/password, validation, loading state
- Backend: API endpoint POST /api/auth/login, JWT token generation
- Database: Users table với email, password hash, created_at

Yêu cầu:
1. Dùng explorer để kiểm tra cấu trúc project hiện tại
2. Dispatch 3 workers (frontend, backend, database) chạy song song
3. Sau khi xong, gửi code-reviewer để test và review toàn bộ
```

**Điều gì sẽ xảy ra:**
1. Orchestrator gọi `explorer` để hiểu project structure
2. Orchestrator dispatch cùng lúc 3 Task tool:
   - `worker-frontend`: Tạo login form UI
   - `worker-backend`: Tạo API endpoint login
   - `worker-database`: Tạo users table migration
3. Sau khi cả 3 xong → orchestrator tổng hợp
4. Orchestrator gọi `code-reviewer` để review + test
5. Trả kết quả cuối cùng cho user

---

### Ví dụ 2: Xây dựng CRUD Product

```
@orchestrator Tạo tính năng quản lý sản phẩm (Product CRUD):

Frontend:
- Danh sách sản phẩm (table với pagination)
- Form tạo/sửa sản phẩm (tên, giá, mô tả, hình ảnh)
- Nút xóa với confirmation dialog

Backend:
- GET /api/products (list với pagination)
- POST /api/products (tạo mới)
- PUT /api/products/:id (cập nhật)
- DELETE /api/products/:id (xóa)

Database:
- Products table: id, name, price, description, image_url, created_at, updated_at

Chạy song song tất cả workers, sau đó review code.
```

---

### Ví dụ 3: Chỉ review code (không tạo mới)

```
@orchestrator Kiểm tra toàn bộ code trong thư mục src/ và chạy test.
Gửi code-reviewer để review chi tiết.
```

---

### Ví dụ 4: Feature đăng ký với OAuth Google

```
@orchestrator Xây dựng tính năng đăng ký tài khoản với OAuth Google:

Frontend:
- Nút "Sign in with Google"
- Profile form sau khi đăng ký thành công (nhập thêm thông tin)
- Loading state và error handling

Backend:
- OAuth callback endpoint GET /api/auth/google/callback
- User creation logic từ Google profile
- Session/JWT management

Database:
- Thêm cột google_id vào users table
- OAuth tokens table để lưu refresh tokens

Chạy workers song song, review code sau khi hoàn thành.
```

---

## Mẹo sử dụng

### 1. Chạy song song hiệu quả
- Orchestrator tự động dispatch nhiều task trong 1 response → chạy song song
- Bạn KHÔNG cần làm gì thêm, chỉ cần mô tả rõ các task cần làm

### 2. Điều hướng giữa các sessions
Khi các workers đang chạy, bạn có thể xem tiến trình:
- `<Leader> + Down`: Vào child session đầu tiên
- `Right`: Chuyển sang child session tiếp theo
- `Left`: Quay lại child session trước
- `Up`: Quay về parent session (orchestrator)

### 3. Giới hạn worker có thể gọi
Trong `opencode.json`, phần `permission.task` quy định worker nào được phép gọi:
```json
"task": {
  "*": "deny",           // Mặc định: không gọi worker nào
  "worker-frontend": "allow",  // NGOẠI TRỪ các worker này
  "worker-backend": "allow",
  "code-reviewer": "allow"
}
```

### 4. Thêm worker mới
Tạo file `.opencode/agents/worker-<tên>.md`:
```markdown
---
description: Mô tả worker làm gì
mode: subagent
---
Bạn là... [instructions]
```

Sau đó thêm vào `opencode.json`:
```json
"task": {
  "worker-<tên>": "allow"
}
```

### 5. Permission của code-reviewer
Code-reviewer chỉ được phép chạy các lệnh:
- `npm test`, `npm run lint` - để test code
- `git diff`, `git log` - để xem thay đổi
- `cat`, `ls`, `find`, `grep` - để đọc file
- Tất cả lệnh khác bị DENY

---

## Troubleshooting

### Worker không được gọi
- Kiểm tra `opencode.json` đã `"allow"` worker đó chưa
- Kiểm tra file `.md` có `mode: subagent` không

### Code-reviewer không chạy được test
- Đảm bảo project có test script trong `package.json`
- Kiểm tra permission trong code-reviewer.md

### Agents chạy tuần tự thay vì song song
- Orchestrator phải dispatch TẤT CẢ task trong CÙNG 1 response
- Nếu orchestrator gọi task lần lượt, nhắc: "Dispatch tất cả workers cùng lúc"
