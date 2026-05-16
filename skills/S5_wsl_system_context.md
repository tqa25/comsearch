# S5: WSL System Context — Ràng Buộc Phần Cứng & Hệ Thống

> **MỤC ĐÍCH:** AI agent KHÔNG đề xuất tác vụ vượt quá resource hệ thống.

---

## 1. Phần Cứng

| Component | Spec |
|---|---|
| CPU | AMD Ryzen 5 4600H (6 Cores/12 Threads) |
| RAM Tổng | 16GB DDR4 |
| GPU | NVIDIA GTX 1650 (4GB VRAM) |
| Ổ cứng | Samsung SSD (~40GB trống) |

## 2. WSL 2 Configuration

| Setting | Giá trị |
|---|---|
| OS | Ubuntu on WSL 2 |
| Memory | **8GB** (50% RAM vật lý) |
| Processors | **4 Cores** |
| Swap | 4GB |
| Auto Memory Reclaim | gradual |

## 3. Quy Tắc Lưu Trữ (NGHIÊM NGẶT)

| Vùng | Đường dẫn | Quy tắc |
|---|---|---|
| ✅ **Ưu tiên** | `/home/baguf/workspaces/` | MỌI mã nguồn PHẢI nằm ở đây |
| ❌ **CẤM** | `/mnt/c/`, `/mnt/d/` | TUYỆT ĐỐI KHÔNG chạy code từ ổ Windows |
| 📁 Truy cập từ Windows | `\\wsl$\Ubuntu\home\baguf` | Dùng đường dẫn mạng |

## 4. Giới Hạn Quan Trọng

- **RAM WSL: 8GB** → Không đề xuất tác vụ cần >6GB RAM
- **Ổ cứng: ~40GB trống** → Ưu tiên giải pháp tiết kiệm dung lượng, dọn cache thường xuyên
- **DatabaseManager KHÔNG thread-safe** → Mỗi call mở connection riêng, KHÔNG share instance giữa threads
- **SQLite** → Phù hợp cho single-process pipeline, KHÔNG dùng cho concurrent writes

## 5. Package Management

| Tool | Mục đích |
|---|---|
| `apt` | System packages |
| `venv` | Python virtual environment |
| `pip` | Python dependencies |
| `nvm` | Node.js (nếu cần) |

## 6. Workflow Chuẩn

```bash
# 1. Mở terminal
wsl ~

# 2. Vào project
cd ~/workspaces/comsearch

# 3. Activate venv
source venv/bin/activate

# 4. Chạy pipeline
python scripts/run_batch.py --limit 100
```
