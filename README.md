# newfunbot — noitu.fun all-in-one

Một file duy nhất: **`noitubot.py`**

## Chức năng

1. **Tạo account** guest (lưu `accounts.txt`)
2. **Cày level 2** song song tối đa **10 acc**
3. **Chat spam** — nhập nội dung, tất cả acc nhắn mỗi **100ms**, Ctrl+C dừng
4. **Báo cáo** sau mỗi lần chạy
5. Menu chọn số, terminal có màu + khung

## Cài đặt

```bash
pip install requests websocket-client
```

(File `filtered_words.txt` cùng thư mục — nếu thiếu bot tự tải từ GitHub)

## Chạy

```bash
python noitubot.py
```

```
[1] Tạo account mới
[2] Cày level 2 song song
[3] Chat spam tất cả acc
[4] Cày + Chat (full)
[5] Xem danh sách account
[6] Báo cáo tổng hợp
[7] Xóa account local
[0] Thoát
```

## File accounts.txt

```
code|accessToken|refreshToken|name|level|xp
```

## Logic nối từ

Dựa trên cách chọn từ của `tool.js` (repo tuvungvn): index theo âm tiết đầu, thử lần lượt ứng viên hợp lệ khi trả lời solo `word-link/answer`.
