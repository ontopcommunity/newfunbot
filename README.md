# newfunbot — noitu.fun automation

Bot Python tự động:

1. **Tạo guest account** (POST `/api/v1/user/init`) — không cần email/password
2. **Lưu phiên** vào `accounts.txt` (code + accessToken + refreshToken)
3. **Cày solo nối từ** đến **level 2**
4. **Nhắn `test`** lên chat qua STOMP WebSocket

## Cài đặt

```bash
pip install -r requirements.txt
```

## Lệnh

```bash
# Tạo 3 account
python bot.py create 3

# Xem danh sách
python bot.py list

# Cày toàn bộ account đến lv2 rồi chat "test"
python bot.py grind

# Cày 1 account cụ thể
python bot.py grind <userCode>

# Chỉ gửi chat
python bot.py chat

# Full pipeline: tạo N + cày + chat
python bot.py full 2
```

## File accounts.txt

```
code|accessToken|refreshToken|name|level|xp
```

Token được refresh tự động khi hết hạn.

## API chính (đã reverse)

| Endpoint | Mô tả |
|----------|--------|
| `POST /api/v1/user/init` | Tạo guest, trả JWT |
| `POST /api/v1/auth/refresh` | Refresh access token |
| `GET /api/v1/user/get?code=` | Level / XP |
| `GET /api/v1/word-link/start?sessionId=` | Bắt đầu solo |
| `POST /api/v1/word-link/answer` | Trả lời nối từ |
| `GET /api/v1/word-link/result` | Kết quả ván |
| `POST /api/v1/ranked/queue/join?game=WORD_LINK` | Hàng chờ rank 1v1 |
| STOMP `/app/chat` + `/room/chat-room` | Chat realtime |

## Ghi chú

- Solo mode dùng để farm XP ổn định hơn ranked (ranked cần matchmaking 2 người).
- Level 1 → 2 cần **50 XP**. Chat có gate `CHAT_LEVEL_REQUIREMENT` nếu chưa đủ level.
- Từ điển: `filtered_words.txt` (từ repo tuvungvn).

## Repo tham khảo

- https://github.com/ontopcommunity/tuvungvn (`tool.js` — bot DOM phía browser)
