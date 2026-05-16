# Prompt Files — Hướng Dẫn Sử Dụng

## Cách dùng

Mỗi file `.md` trong thư mục này là một prompt dành cho **một AI agent** thực hiện **một task** cụ thể.

### Quy trình:
1. Mở AI chatbox (Antigravity, Cursor, Claude Code...)
2. **Drag & drop** file prompt tương ứng vào ô chat
3. Agent sẽ đọc prompt và thực hiện task
4. Sau khi xong, agent tự tạo branch + commit + push (theo skill S6)

### Thứ tự thực hiện:

```
Wave 0: T0_foundation.md              ← Chạy TRƯỚC, một mình
         ↓ (merge vào main)
Wave 1: T1A + T1B + T1C + T1D         ← 4 agent chạy SONG SONG
         ↓ (merge tất cả vào main)
Wave 2: T2E + T2F                     ← 2 agent chạy SONG SONG
         ↓ (merge vào main)
Wave 3: T3G + T3H + T3I               ← 3 agent chạy SONG SONG
```

### Lưu ý:
- Wave N+1 chỉ bắt đầu SAU KHI Wave N đã merge vào `main`
- Mỗi prompt đã chứa sẵn context cần thiết (skills, references)
- Agent PHẢI đọc skill files được liệt kê trong phần "Context" của prompt
