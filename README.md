# newfunbot — noitu.fun all-in-one + Supabase

File chính: **`noitubot.py`**

## Lưu trữ account

| Nơi | Mô tả |
|-----|--------|
| **Local** `accounts.txt` | Luôn giữ, không xoá |
| **Supabase** `noitu_accounts` | Đồng bộ cloud |

### Setup Supabase (1 lần)

1. Mở [SQL Editor](https://supabase.com/dashboard/project/tdlubyvugaucfexezhrk/sql)
2. Chạy file `setup_supabase.sql` (hoặc menu bot **[8] → [a]**)
3. Menu **[8] → [b]** kiểm tra kết nối
4. **[8] → [c]** push local → cloud

## Chạy

```bash
pip install requests websocket-client
python noitubot.py
```

```
[1] Tạo account mới
[2] Cày level 2 song song (≤10)
[3] Chat spam 100ms (Ctrl+C dừng)
[4] Full pipeline
[5] Xem danh sách (local + cloud merge)
[6] Báo cáo
[7] Xóa local + cloud
[8] Đồng bộ Supabase
[0] Thoát
```

Mỗi lần tạo / cập nhật level·xp → ghi **local + Supabase**.
