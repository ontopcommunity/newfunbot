# newfunbot — Rank thật + tool.js + Playwright

## Chức năng
- **[1] Tạo acc** — không giới hạn số lượng
- **[2] Cày RANK** `WORD_LINK` 1v1 với người thật (không 2-acc tự match)
  - Song song tối đa **100**
  - Acc đã **lv≥2 bị bỏ qua**
  - Logic nối từ theo **tool.js** (âm tiết đầu + dictionary)
  - Mode: `1=API hybrid` | `2=Playwright DOM click`
- **[3] Chat spam** — chỉ dùng acc có sẵn
- Local `accounts.txt` + **Supabase**

## Cài đặt (máy/Cloud Shell của bạn)

```bash
python3 -m pip install -q requests websocket-client playwright
python3 -m playwright install chromium
```

## Chạy

```bash
python3 -m pip install -q requests websocket-client playwright && python3 -m playwright install chromium && curl -sL https://raw.githubusercontent.com/ontopcommunity/newfunbot/main/noitubot.py -o /tmp/noitubot.py && python3 /tmp/noitubot.py
```

> IP datacenter có thể bị Cloudflare chặn API/web. Chạy trên IP sạch / máy cá nhân.
