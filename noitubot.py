#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════╗
║              NOITU.FUN BOT  —  all-in-one                    ║
║  Tạo acc · Cày lv2 (song song ≤10) · Chat spam · Báo cáo     ║
╚══════════════════════════════════════════════════════════════╝

Chạy:  python noitubot.py
"""
from __future__ import annotations

import json
import os
import random
import re
import signal
import string
import sys
import threading
import time
import uuid
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

try:
    import requests
except ImportError:
    print("Cần: pip install requests websocket-client")
    sys.exit(1)

try:
    import websocket
except ImportError:
    websocket = None  # type: ignore

# ═══════════════════════════════════════════════════════════════
#  CONFIG
# ═══════════════════════════════════════════════════════════════
BASE = "https://api.noitu.fun/api/v1"
WS_BASE = "wss://api.noitu.fun/ws"
ORIGIN = "https://www.noitu.fun"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
try:
    HERE = os.path.dirname(os.path.abspath(__file__))
except NameError:
    HERE = os.getcwd()  # chạy qua curl | python
ACCOUNTS_FILE = os.path.join(HERE, "accounts.txt")
DICT_FILE = os.path.join(HERE, "filtered_words.txt")
DICT_URL = "https://raw.githubusercontent.com/ontopcommunity/tuvungvn/main/filtered_words.txt"

# ── Supabase (cloud DB) — local accounts.txt vẫn giữ ──
SUPABASE_URL = "https://tdlubyvugaucfexezhrk.supabase.co"
SUPABASE_KEY = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRkbHVieXZ1Z2F1Y2ZleGV6aHJrIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIs"
    "ImlhdCI6MTc4Njc4NTcyMSwiZXhwIjoyMTAyMzYxNzIxfQ.7JkJVP9FzC51rZRwdKGL4IdY-m6ZGxyNoRE5WAGt2KU"
)
SB_TABLE = "noitu_accounts"
# SQL tạo bảng (chạy 1 lần trong Supabase → SQL Editor nếu chưa có):
# create table if not exists public.noitu_accounts (
#   code text primary key,
#   access_token text not null,
#   refresh_token text not null,
#   name text default '',
#   level int default 1,
#   xp int default 0,
#   updated_at timestamptz default now(),
#   created_at timestamptz default now()
# );

TARGET_LEVEL = 2
MAX_PARALLEL = 50
MAX_GAMES_PER_ACC = 100
CHAT_INTERVAL = 0.1  # 100ms
STALL_BACKOFF = 35

# ═══════════════════════════════════════════════════════════════
#  TERMINAL COLORS / UI
# ═══════════════════════════════════════════════════════════════
class C:
    R = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[91m"
    GRN = "\033[92m"
    YEL = "\033[93m"
    BLU = "\033[94m"
    MAG = "\033[95m"
    CYN = "\033[96m"
    WHT = "\033[97m"
    BG = "\033[48;5;235m"


_print_lock = threading.Lock()


def ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


def log(msg: str, color: str = C.WHT) -> None:
    with _print_lock:
        print(f"{C.DIM}[{ts()}]{C.R} {color}{msg}{C.R}", flush=True)


def attach_tty() -> None:
    """Khi chạy curl|python, stdin là pipe → gắn lại /dev/tty để safe_input() hoạt động."""
    try:
        if not sys.stdin.isatty():
            sys.stdin = open("/dev/tty", "r")
    except Exception:
        pass


def safe_safe_input(prompt: str = "") -> str:
    try:
        return safe_input(prompt)
    except EOFError:
        log("Không đọc được bàn phím (EOF). Chạy lại bằng:", C.RED)
        log("  curl -sL ... -o /tmp/noitubot.py && python3 /tmp/noitubot.py", C.YEL)
        raise SystemExit(1)



def banner() -> None:
    art = f"""
{C.CYN}{C.BOLD}
    ╔══════════════════════════════════════════════════════════╗
    ║                                                          ║
    ║   ███╗   ██╗ ██████╗ ██╗████████╗██╗   ██╗               ║
    ║   ████╗  ██║██╔═══██╗██║╚══██╔══╝██║   ██║               ║
    ║   ██╔██╗ ██║██║   ██║██║   ██║   ██║   ██║               ║
    ║   ██║╚██╗██║██║   ██║██║   ██║   ██║   ██║               ║
    ║   ██║ ╚████║╚██████╔╝██║   ██║   ╚██████╔╝               ║
    ║   ╚═╝  ╚═══╝ ╚═════╝ ╚═╝   ╚═╝    ╚═════╝                ║
    ║                                                          ║
    ║          . F U N   B O T   ·   all-in-one                ║
    ║     Tạo acc · Cày LV2 · Chat spam · Báo cáo              ║
    ╚══════════════════════════════════════════════════════════╝
{C.R}"""
    print(art)


def box(title: str, lines: List[str], color: str = C.CYN) -> None:
    width = max(len(title) + 4, max((len(_strip(l)) for l in lines), default=20) + 4, 40)
    top = "╔" + "═" * (width - 2) + "╗"
    mid = "╠" + "═" * (width - 2) + "╣"
    bot = "╚" + "═" * (width - 2) + "╝"
    print(f"{color}{top}{C.R}")
    pad = width - 4 - len(title)
    print(f"{color}║{C.R} {C.BOLD}{title}{C.R}{' ' * pad} {color}║{C.R}")
    print(f"{color}{mid}{C.R}")
    for line in lines:
        plain = _strip(line)
        pad = width - 4 - len(plain)
        print(f"{color}║{C.R} {line}{' ' * max(0, pad)} {color}║{C.R}")
    print(f"{color}{bot}{C.R}")


def _strip(s: str) -> str:
    return re.sub(r"\033\[[0-9;]*m", "", s)


def menu() -> None:
    box(
        "MENU CHÍNH",
        [
            f"{C.GRN}[1]{C.R}  Tạo account mới          (nhập số lượng)",
            f"{C.GRN}[2]{C.R}  Cày level 2 song song     (tối đa {MAX_PARALLEL} acc)",
            f"{C.GRN}[3]{C.R}  Chat spam tất cả acc      (100ms / tin, Ctrl+C dừng)",
            f"{C.GRN}[4]{C.R}  Cày + Chat (full pipeline)",
            f"{C.GRN}[5]{C.R}  Xem danh sách account    (local + Supabase)",
            f"{C.GRN}[6]{C.R}  Báo cáo tổng hợp",
            f"{C.GRN}[7]{C.R}  Xóa account local (+ cloud)",
            f"{C.CYN}[8]{C.R}  Đồng bộ Supabase         (SQL setup / push / pull)",
            f"{C.YEL}[0]{C.R}  Thoát",
        ],
        C.BLU,
    )


# ═══════════════════════════════════════════════════════════════
#  DICTIONARY  (logic gần tool.js: first-syllable index)
# ═══════════════════════════════════════════════════════════════
class WordDict:
    def __init__(self) -> None:
        self.words: List[str] = []
        self.by_first: Dict[str, List[str]] = defaultdict(list)
        self._load()

    def _load(self) -> None:
        path = DICT_FILE
        if not os.path.isfile(path):
            log("Đang tải từ điển từ GitHub...", C.YEL)
            try:
                r = requests.get(DICT_URL, timeout=60)
                r.raise_for_status()
                with open(path, "w", encoding="utf-8") as f:
                    f.write(r.text)
            except Exception as e:
                log(f"Không tải được từ điển: {e}", C.RED)
                return
        seen: Set[str] = set()
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                w = line.strip().lower()
                if not w or " " not in w or w in seen:
                    continue
                # tool.js filters 2-word phrases primarily
                parts = w.split()
                if len(parts) < 2:
                    continue
                seen.add(w)
                self.words.append(w)
                self.by_first[parts[0]].append(w)
        for k in self.by_first:
            random.shuffle(self.by_first[k])
        log(f"Từ điển: {C.GRN}{len(self.words)}{C.R} từ", C.CYN)

    def pick(self, last: str, used: Set[str], n: int = 25) -> List[str]:
        key = last.lower().strip()
        return [w for w in self.by_first.get(key, []) if w not in used][:n]


# ═══════════════════════════════════════════════════════════════
#  HTTP HELPERS
# ═══════════════════════════════════════════════════════════════
def _hdr(token: Optional[str] = None) -> Dict[str, str]:
    h = {
        "Origin": ORIGIN,
        "Referer": ORIGIN + "/",
        "Content-Type": "application/json",
        "Accept": "application/json, text/plain, */*",
        "User-Agent": UA,
    }
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def robust(fn: Callable, tries: int = 5, label: str = "") -> Any:
    delay = 1.2
    last = None
    for i in range(tries):
        try:
            return fn()
        except (requests.exceptions.RequestException, OSError) as e:
            last = e
            log(f"  net {label} {type(e).__name__} retry {delay:.0f}s ({i+1}/{tries})", C.DIM)
            time.sleep(delay)
            delay = min(delay * 1.6, 18)
    if last:
        raise last
    return None


# ═══════════════════════════════════════════════════════════════
#  ACCOUNT STORE  (local file + Supabase)
# ═══════════════════════════════════════════════════════════════
_acc_lock = threading.Lock()
_sb_ok: Optional[bool] = None  # None=unknown, True=ready, False=unavailable


def _sb_headers() -> Dict[str, str]:
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def sb_check() -> bool:
    """True nếu bảng noitu_accounts tồn tại và truy cập được."""
    global _sb_ok
    if _sb_ok is not None:
        return _sb_ok
    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/{SB_TABLE}",
            params={"select": "code", "limit": "1"},
            headers=_sb_headers(),
            timeout=15,
        )
        if r.status_code == 200:
            _sb_ok = True
            log(f"Supabase OK → bảng {SB_TABLE}", C.GRN)
        else:
            _sb_ok = False
            log(
                f"Supabase bảng '{SB_TABLE}' chưa có (HTTP {r.status_code}). "
                f"Chạy SQL trong README / menu [8]. Local vẫn hoạt động.",
                C.YEL,
            )
    except Exception as e:
        _sb_ok = False
        log(f"Supabase offline: {e} — dùng local", C.YEL)
    return _sb_ok


def sb_fetch_all() -> List[Dict[str, str]]:
    if not sb_check():
        return []
    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/{SB_TABLE}",
            params={"select": "*"},
            headers=_sb_headers(),
            timeout=30,
        )
        r.raise_for_status()
        rows = []
        for row in r.json():
            rows.append({
                "code": row["code"],
                "accessToken": row.get("access_token") or "",
                "refreshToken": row.get("refresh_token") or "",
                "name": row.get("name") or "",
                "level": str(row.get("level") if row.get("level") is not None else 1),
                "xp": str(row.get("xp") if row.get("xp") is not None else 0),
            })
        return rows
    except Exception as e:
        log(f"sb_fetch: {e}", C.YEL)
        return []


def sb_upsert(acc: Dict[str, str]) -> bool:
    if not sb_check():
        return False
    payload = {
        "code": acc["code"],
        "access_token": acc["accessToken"],
        "refresh_token": acc["refreshToken"],
        "name": acc.get("name") or "",
        "level": int(acc.get("level") or 1),
        "xp": int(acc.get("xp") or 0),
        "updated_at": datetime.utcnow().isoformat() + "Z",
    }
    try:
        h = _sb_headers()
        h["Prefer"] = "resolution=merge-duplicates,return=minimal"
        r = requests.post(
            f"{SUPABASE_URL}/rest/v1/{SB_TABLE}",
            params={"on_conflict": "code"},
            headers=h,
            json=payload,
            timeout=20,
        )
        if r.status_code not in (200, 201, 204):
            # fallback PATCH
            r2 = requests.patch(
                f"{SUPABASE_URL}/rest/v1/{SB_TABLE}",
                params={"code": f"eq.{acc['code']}"},
                headers=_sb_headers(),
                json=payload,
                timeout=20,
            )
            if r2.status_code not in (200, 204):
                log(f"sb_upsert fail {r.status_code}/{r2.status_code}: {r.text[:120]}", C.YEL)
                return False
        return True
    except Exception as e:
        log(f"sb_upsert: {e}", C.YEL)
        return False


def sb_delete(code: str) -> None:
    if not sb_check():
        return
    try:
        requests.delete(
            f"{SUPABASE_URL}/rest/v1/{SB_TABLE}",
            params={"code": f"eq.{code}"},
            headers=_sb_headers(),
            timeout=15,
        )
    except Exception:
        pass


def sb_clear_all() -> None:
    if not sb_check():
        return
    try:
        requests.delete(
            f"{SUPABASE_URL}/rest/v1/{SB_TABLE}",
            params={"code": "neq."},  # delete all (code not equal empty - hack)
            headers=_sb_headers(),
            timeout=30,
        )
        # safer: fetch then delete each
        for a in sb_fetch_all():
            sb_delete(a["code"])
    except Exception:
        pass


def load_local() -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    if not os.path.isfile(ACCOUNTS_FILE):
        return rows
    with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            p = line.split("|")
            if len(p) < 3:
                continue
            rows.append({
                "code": p[0],
                "accessToken": p[1],
                "refreshToken": p[2],
                "name": p[3] if len(p) > 3 else "",
                "level": p[4] if len(p) > 4 else "1",
                "xp": p[5] if len(p) > 5 else "0",
            })
    return rows


def save_local(rows: List[Dict[str, str]]) -> None:
    with open(ACCOUNTS_FILE, "w", encoding="utf-8") as f:
        f.write("# code|accessToken|refreshToken|name|level|xp\n")
        for r in rows:
            f.write(
                f"{r['code']}|{r['accessToken']}|{r['refreshToken']}|"
                f"{r.get('name','')}|{r.get('level','1')}|{r.get('xp','0')}\n"
            )


def _merge_accounts(local: List[Dict[str, str]], cloud: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """Gộp local + Supabase, ưu tiên level/xp cao hơn, token mới hơn từ cloud nếu level bằng."""
    by_code: Dict[str, Dict[str, str]] = {}
    for r in local:
        by_code[r["code"]] = dict(r)
    for r in cloud:
        if r["code"] not in by_code:
            by_code[r["code"]] = dict(r)
        else:
            cur = by_code[r["code"]]
            try:
                if int(r.get("level") or 0) > int(cur.get("level") or 0):
                    by_code[r["code"]] = dict(r)
                elif int(r.get("level") or 0) == int(cur.get("level") or 0):
                    if int(r.get("xp") or 0) >= int(cur.get("xp") or 0):
                        # keep cloud tokens if fresher progress
                        by_code[r["code"]] = {
                            **cur,
                            "accessToken": r.get("accessToken") or cur.get("accessToken", ""),
                            "refreshToken": r.get("refreshToken") or cur.get("refreshToken", ""),
                            "level": r.get("level", cur.get("level")),
                            "xp": r.get("xp", cur.get("xp")),
                            "name": r.get("name") or cur.get("name", ""),
                        }
            except ValueError:
                pass
    return list(by_code.values())


def load_accounts() -> List[Dict[str, str]]:
    """Load local + Supabase, merge, sync cả 2 chiều nhẹ."""
    local = load_local()
    cloud = sb_fetch_all()
    merged = _merge_accounts(local, cloud)
    # write-back local so file luôn đủ
    if merged:
        save_local(merged)
    return merged


def upsert_account(acc: Dict[str, str]) -> None:
    """Lưu local VÀ Supabase (không xoá local)."""
    with _acc_lock:
        rows = load_local()
        found = False
        for i, r in enumerate(rows):
            if r["code"] == acc["code"]:
                rows[i] = acc
                found = True
                break
        if not found:
            rows.append(acc)
        save_local(rows)
    # cloud async-ish (same thread, quick)
    sb_upsert(acc)


def sync_local_to_cloud() -> Tuple[int, int]:
    """Đẩy toàn bộ local → Supabase."""
    rows = load_local()
    ok = fail = 0
    for r in rows:
        if sb_upsert(r):
            ok += 1
        else:
            fail += 1
    return ok, fail


def sync_cloud_to_local() -> int:
    """Kéo Supabase → local (merge)."""
    cloud = sb_fetch_all()
    local = load_local()
    merged = _merge_accounts(local, cloud)
    save_local(merged)
    return len(cloud)


# ═══════════════════════════════════════════════════════════════
#  API
# ═══════════════════════════════════════════════════════════════
def create_guest() -> Dict[str, Any]:
    def _do():
        r = requests.post(
            f"{BASE}/user/init",
            json={"id": None, "code": None},
            headers=_hdr(),
            timeout=25,
        )
        r.raise_for_status()
        return r.json()

    return robust(_do, label="init")


def refresh_token(refresh: str) -> Dict[str, Any]:
    def _do():
        r = requests.post(
            f"{BASE}/auth/refresh",
            json={"refreshToken": refresh},
            headers=_hdr(),
            timeout=20,
        )
        r.raise_for_status()
        return r.json()

    return robust(_do, label="refresh")


def get_user(code: str, token: str) -> Dict[str, Any]:
    def _do():
        r = requests.get(
            f"{BASE}/user/get",
            params={"code": code},
            headers=_hdr(token),
            timeout=20,
        )
        r.raise_for_status()
        return r.json()

    return robust(_do, label="user/get")


def ensure_token(acc: Dict[str, str]) -> str:
    try:
        u = get_user(acc["code"], acc["accessToken"])
        if u and "level" in u:
            return acc["accessToken"]
    except Exception:
        pass
    data = refresh_token(acc["refreshToken"])
    tok = data.get("accessToken")
    if not tok:
        raise RuntimeError("refresh failed")
    acc["accessToken"] = tok
    if data.get("refreshToken"):
        acc["refreshToken"] = data["refreshToken"]
    upsert_account(acc)
    return tok


def progress(acc: Dict[str, str], token: str) -> Tuple[int, int, int]:
    u = get_user(acc["code"], token)
    level = int(u.get("level", 1))
    xp = int(u.get("experiencePoints", 0))
    need = int(u.get("nextLevelRequirement", 50))
    acc["level"] = str(level)
    acc["xp"] = str(xp)
    upsert_account(acc)
    return level, xp, need


def solo_start(token: str) -> Tuple[str, Dict]:
    sid = str(uuid.uuid4())

    def _do():
        r = requests.get(
            f"{BASE}/word-link/start",
            params={"sessionId": sid},
            headers=_hdr(token),
            timeout=25,
        )
        r.raise_for_status()
        return r.json()

    return sid, robust(_do, label="start")


def solo_answer(token: str, sid: str, answer: str) -> Dict:
    def _do():
        r = requests.post(
            f"{BASE}/word-link/answer",
            json={"sessionId": sid, "answer": answer},
            headers=_hdr(token),
            timeout=25,
        )
        r.raise_for_status()
        return r.json()

    return robust(_do, label="answer")


def solo_skip(token: str, sid: str) -> Dict:
    def _do():
        r = requests.get(
            f"{BASE}/word-link/skip",
            params={"sessionId": sid},
            headers=_hdr(token),
            timeout=20,
        )
        r.raise_for_status()
        return r.json()

    return robust(_do, label="skip")


def solo_result(token: str, code: str, sid: str) -> Dict:
    def _do():
        r = requests.get(
            f"{BASE}/word-link/result",
            params={"userCode": code, "sessionId": sid},
            headers=_hdr(token),
            timeout=20,
        )
        r.raise_for_status()
        return r.json()

    return robust(_do, label="result")


# ═══════════════════════════════════════════════════════════════
#  SOLO PLAY  (inspired by tool.js word selection)
# ═══════════════════════════════════════════════════════════════
def play_solo(token: str, code: str, wdict: WordDict, max_turns: int = 45) -> Dict[str, Any]:
    sid, data = solo_start(token)
    wd = data.get("wordDescription") or {}
    cur = (wd.get("word") or "").strip().lower()
    if not cur:
        return {"score": 0, "sessionId": sid, "error": "no_word"}

    used: Set[str] = {cur}
    score = 0
    finished = False

    for _ in range(max_turns):
        last = cur.split()[-1]
        cands = wdict.pick(last, used)
        if not cands:
            try:
                data = solo_skip(token, sid)
            except Exception:
                break
            score = data.get("score", score)
            if data.get("isFinished"):
                finished = True
                break
            nwd = data.get("wordDescription") or {}
            if nwd.get("word"):
                cur = nwd["word"].strip().lower()
                used.add(cur)
            continue

        answered = False
        for ans in cands[:8]:
            used.add(ans)
            try:
                data = solo_answer(token, sid, ans)
            except Exception:
                continue
            if data.get("isSuccessful"):
                score = data.get("score", score)
                answered = True
                if data.get("isFinished"):
                    finished = True
                nwd = data.get("wordDescription") or {}
                if nwd.get("word"):
                    cur = nwd["word"].strip().lower()
                    used.add(cur)
                break
            score = data.get("score", score)
            if data.get("isFinished"):
                finished = True
                answered = True
                break

        if finished:
            break
        if not answered:
            try:
                data = solo_skip(token, sid)
                score = data.get("score", score)
                if data.get("isFinished"):
                    finished = True
                    break
                nwd = data.get("wordDescription") or {}
                if nwd.get("word"):
                    cur = nwd["word"].strip().lower()
                    used.add(cur)
            except Exception:
                break
        time.sleep(0.08 + random.random() * 0.12)

    try:
        result = solo_result(token, code, sid)
    except Exception:
        result = {}

    return {"sessionId": sid, "score": score, "finished": finished, "result": result}


# ═══════════════════════════════════════════════════════════════
#  STOMP CHAT
# ═══════════════════════════════════════════════════════════════
class StompClient:
    def __init__(self, token: str):
        self.token = token
        self.ws = None
        self.connected = False
        self._frames: List[Tuple[str, Any]] = []
        self._lock = threading.Lock()
        self._sub = 0

    def connect(self, timeout: float = 10.0) -> bool:
        if websocket is None:
            return False
        server = str(random.randint(100, 999))
        session = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
        url = f"{WS_BASE}/{server}/{session}/websocket"
        done = threading.Event()

        def on_open(ws):
            frame = (
                "CONNECT\n"
                f"Authorization:Bearer {self.token}\n"
                "accept-version:1.1,1.0\n"
                "heart-beat:10000,10000\n\n\x00"
            )
            ws.send(frame)

        def on_message(ws, message):
            if not message:
                return
            if message.startswith(("o", "h")):
                return
            if message.startswith("c"):
                self.connected = False
                return
            if message.startswith("a"):
                try:
                    arr = json.loads(message[1:])
                except Exception:
                    return
                for raw in arr:
                    self._stomp(raw)
            else:
                self._stomp(message)

        def on_connected():
            self.connected = True
            done.set()

        self._on_ok = on_connected

        def on_error(ws, err):
            pass

        def on_close(ws, *a):
            self.connected = False

        self.ws = websocket.WebSocketApp(
            url,
            header=[f"Origin: {ORIGIN}"],
            on_open=on_open,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close,
        )
        threading.Thread(
            target=lambda: self.ws.run_forever(ping_interval=25),
            daemon=True,
        ).start()
        done.wait(timeout)
        return self.connected

    def _stomp(self, raw: str) -> None:
        if not isinstance(raw, str):
            return
        if raw.startswith("CONNECTED"):
            if hasattr(self, "_on_ok"):
                self._on_ok()
            return
        if raw.startswith("MESSAGE"):
            dest, body = "", ""
            parts = raw.split("\n\n", 1)
            for line in parts[0].split("\n"):
                if line.lower().startswith("destination:"):
                    dest = line.split(":", 1)[1].strip()
            if len(parts) > 1:
                body = parts[1].rstrip("\x00")
            payload: Any = body
            try:
                payload = json.loads(body)
            except Exception:
                pass
            with self._lock:
                self._frames.append((dest, payload))

    def subscribe(self, dest: str) -> None:
        if not self.ws:
            return
        self._sub += 1
        self.ws.send(f"SUBSCRIBE\nid:sub-{self._sub}\ndestination:{dest}\n\n\x00")

    def send(self, dest: str, body: dict) -> None:
        if not self.ws:
            return
        payload = json.dumps(body, ensure_ascii=False)
        self.ws.send(
            f"SEND\ndestination:{dest}\ncontent-type:application/json\n\n{payload}\x00"
        )

    def drain(self) -> List[Tuple[str, Any]]:
        with self._lock:
            out = list(self._frames)
            self._frames.clear()
        return out

    def close(self) -> None:
        try:
            if self.ws:
                self.ws.close()
        except Exception:
            pass
        self.connected = False


# ═══════════════════════════════════════════════════════════════
#  FEATURES
# ═══════════════════════════════════════════════════════════════
def feature_create() -> None:
    try:
        n = int(safe_input(f"  {C.CYN}Số account cần tạo{C.R} [1]: ").strip() or "1")
    except ValueError:
        n = 1
    n = max(1, min(n, 50))
    log(f"Đang tạo {n} account...", C.YEL)
    ok = 0
    for i in range(n):
        try:
            data = create_guest()
            acc = {
                "code": data["code"],
                "accessToken": data["accessToken"],
                "refreshToken": data["refreshToken"],
                "name": data.get("name", ""),
                "level": str(data.get("level", 1)),
                "xp": "0",
            }
            upsert_account(acc)
            ok += 1
            log(f"  [{ok}/{n}] {C.GRN}{acc['code']}{C.R}  {acc['name']}", C.WHT)
        except Exception as e:
            log(f"  Lỗi tạo acc: {e}", C.RED)
        time.sleep(0.35)
    box("KẾT QUẢ TẠO ACC", [f"Thành công: {C.GRN}{ok}/{n}{C.R}", f"File: {ACCOUNTS_FILE}"], C.GRN)


def _grind_worker(acc: Dict[str, str], wdict: WordDict, report: Dict) -> None:
    code = acc["code"]
    tag = code[-8:]
    try:
        token = ensure_token(acc)
        level, xp, need = progress(acc, token)
        log(f"[{tag}] bắt đầu lv={level} xp={xp}/{need}", C.CYN)

        if level >= TARGET_LEVEL:
            log(f"[{tag}] đã đạt lv{level}", C.GRN)
            report[code] = {"ok": True, "level": level, "xp": xp, "games": 0}
            return

        games = 0
        stall = 0
        last_xp = xp

        while level < TARGET_LEVEL and games < MAX_GAMES_PER_ACC:
            games += 1
            try:
                res = play_solo(token, code, wdict)
                sc = res.get("score", 0)
                log(f"[{tag}] game#{games} score={sc}", C.DIM)
            except Exception as e:
                log(f"[{tag}] lỗi game: {e}", C.YEL)
                time.sleep(2)
                try:
                    token = ensure_token(acc)
                except Exception:
                    pass
                continue

            time.sleep(0.6)
            try:
                level, xp, need = progress(acc, token)
            except Exception:
                try:
                    token = ensure_token(acc)
                    level, xp, need = progress(acc, token)
                except Exception:
                    time.sleep(4)
                    continue

            if xp <= last_xp:
                stall += 1
                if stall >= 3:
                    log(f"[{tag}] XP đứng → chờ {STALL_BACKOFF}s", C.YEL)
                    time.sleep(STALL_BACKOFF)
                    stall = 0
            else:
                stall = 0
                last_xp = xp
                log(f"[{tag}] → lv={level} xp={xp}/{need}", C.GRN)

            time.sleep(0.4)

        report[code] = {
            "ok": level >= TARGET_LEVEL,
            "level": level,
            "xp": xp,
            "games": games,
        }
        color = C.GRN if level >= TARGET_LEVEL else C.RED
        log(f"[{tag}] xong lv={level} games={games}", color)
    except Exception as e:
        log(f"[{tag}] FATAL: {e}", C.RED)
        report[code] = {"ok": False, "error": str(e)}


def feature_grind() -> None:
    rows = load_accounts()
    if not rows:
        log("Chưa có account. Chọn [1] tạo trước.", C.RED)
        return
    wdict = WordDict()
    if not wdict.words:
        log("Không có từ điển!", C.RED)
        return

    print(f"\n  Có {C.GRN}{len(rows)}{C.R} account. Cày tối đa {MAX_PARALLEL} song song.")
    try:
        n = int(safe_input(f"  {C.CYN}Số acc cần cày{C.R} [tất cả, max {MAX_PARALLEL}]: ").strip() or str(min(len(rows), MAX_PARALLEL)))
    except ValueError:
        n = min(len(rows), MAX_PARALLEL)
    n = max(1, min(n, MAX_PARALLEL, len(rows)))
    targets = rows[:n]

    box("BẮT ĐẦU CÀY", [f"Acc: {n}", f"Target: Level {TARGET_LEVEL}", f"Parallel: {n}"], C.MAG)
    report: Dict[str, Any] = {}
    t0 = time.time()

    with ThreadPoolExecutor(max_workers=n) as pool:
        futs = [pool.submit(_grind_worker, acc, wdict, report) for acc in targets]
        for f in as_completed(futs):
            try:
                f.result()
            except Exception as e:
                log(f"worker err: {e}", C.RED)

    elapsed = time.time() - t0
    ok_n = sum(1 for v in report.values() if v.get("ok"))
    lines = [
        f"Thời gian: {elapsed:.0f}s",
        f"Thành công lv≥{TARGET_LEVEL}: {C.GRN}{ok_n}/{n}{C.R}",
        "",
    ]
    for code, v in report.items():
        status = f"{C.GRN}OK{C.R}" if v.get("ok") else f"{C.RED}FAIL{C.R}"
        lines.append(
            f"{code[-10:]}  {status}  lv={v.get('level','?')}  "
            f"xp={v.get('xp','?')}  games={v.get('games','?')}"
        )
    box("BÁO CÁO CÀY", lines, C.CYN)


def feature_chat_spam() -> None:
    rows = load_accounts()
    if not rows:
        log("Chưa có account.", C.RED)
        return
    if websocket is None:
        log("Cần: pip install websocket-client", C.RED)
        return

    msg = safe_input(f"  {C.CYN}Nội dung tin nhắn{C.R}: ").strip()
    if not msg:
        log("Tin nhắn trống.", C.YEL)
        return

    try:
        n = int(safe_input(f"  {C.CYN}Số acc dùng chat{C.R} [tất cả, max {MAX_PARALLEL}]: ").strip() or str(min(len(rows), MAX_PARALLEL)))
    except ValueError:
        n = min(len(rows), MAX_PARALLEL)
    n = max(1, min(n, MAX_PARALLEL, len(rows)))
    targets = rows[:n]

    box(
        "CHAT SPAM",
        [
            f"Nội dung: {C.YEL}{msg}{C.R}",
            f"Acc: {n}",
            f"Interval: {int(CHAT_INTERVAL * 1000)}ms",
            f"{C.RED}Ctrl+C để dừng{C.R}",
        ],
        C.MAG,
    )

    stop = threading.Event()
    stats = {"sent": 0, "fail": 0}

    def _on_sig(*_):
        stop.set()
        log("Đang dừng chat...", C.YEL)

    old = signal.signal(signal.SIGINT, _on_sig)

    def chat_worker(acc: Dict[str, str]) -> None:
        tag = acc["code"][-8:]
        try:
            token = ensure_token(acc)
        except Exception as e:
            log(f"[{tag}] token fail: {e}", C.RED)
            return
        client = StompClient(token)
        if not client.connect():
            log(f"[{tag}] STOMP connect fail", C.RED)
            stats["fail"] += 1
            return
        client.subscribe("/room/chat-room")
        client.subscribe("/user/queue/user-notification")
        time.sleep(0.4)
        client.send("/app/chat/join", {"chatType": "JOIN"})
        time.sleep(0.3)
        log(f"[{tag}] connected, bắt đầu spam", C.GRN)

        while not stop.is_set():
            try:
                client.send("/app/chat", {"message": msg})
                stats["sent"] += 1
                if stats["sent"] % 50 == 0:
                    log(f"  đã gửi ~{stats['sent']} tin", C.DIM)
            except Exception:
                stats["fail"] += 1
                # reconnect
                client.close()
                time.sleep(1)
                if stop.is_set():
                    break
                try:
                    token = ensure_token(acc)
                    client = StompClient(token)
                    if client.connect():
                        client.subscribe("/room/chat-room")
                        client.send("/app/chat/join", {"chatType": "JOIN"})
                except Exception:
                    time.sleep(2)
            time.sleep(CHAT_INTERVAL)
        client.close()
        log(f"[{tag}] dừng", C.DIM)

    threads = []
    for acc in targets:
        t = threading.Thread(target=chat_worker, args=(acc,), daemon=True)
        t.start()
        threads.append(t)
        time.sleep(0.15)

    try:
        while any(t.is_alive() for t in threads):
            time.sleep(0.5)
            if stop.is_set():
                break
    finally:
        stop.set()
        signal.signal(signal.SIGINT, old)
        for t in threads:
            t.join(timeout=3)

    box(
        "BÁO CÁO CHAT",
        [
            f"Đã gửi: {C.GRN}{stats['sent']}{C.R}",
            f"Lỗi: {C.RED}{stats['fail']}{C.R}",
            f"Nội dung: {msg}",
        ],
        C.CYN,
    )


def feature_full() -> None:
    feature_create()
    feature_grind()
    ans = safe_input(f"  {C.CYN}Tiếp tục chat spam? (y/N): {C.R}").strip().lower()
    if ans == "y":
        feature_chat_spam()


def feature_list() -> None:
    rows = load_accounts()
    if not rows:
        log("Trống.", C.YEL)
        return
    lines = []
    for i, r in enumerate(rows, 1):
        lv = r.get("level", "?")
        xp = r.get("xp", "?")
        color = C.GRN if int(lv or 0) >= TARGET_LEVEL else C.WHT
        lines.append(f"{i:2}. {color}{r['code']}{C.R}  lv={lv} xp={xp}  {r.get('name','')}")
    box(f"DANH SÁCH ({len(rows)} acc)", lines, C.BLU)


def feature_report() -> None:
    rows = load_accounts()
    if not rows:
        log("Trống.", C.YEL)
        return
    total = len(rows)
    lv2 = sum(1 for r in rows if int(r.get("level") or 0) >= TARGET_LEVEL)
    xp_sum = sum(int(r.get("xp") or 0) for r in rows)
    lines = [
        f"Tổng account : {C.CYN}{total}{C.R}",
        f"Đã ≥ lv{TARGET_LEVEL}  : {C.GRN}{lv2}{C.R}",
        f"Chưa đủ level: {C.YEL}{total - lv2}{C.R}",
        f"Tổng XP lưu  : {xp_sum}",
        "",
    ]
    for r in rows:
        lv = int(r.get("level") or 0)
        mark = f"{C.GRN}✓{C.R}" if lv >= TARGET_LEVEL else f"{C.RED}·{C.R}"
        lines.append(f"  {mark} {r['code'][-12:]}  lv={lv}  xp={r.get('xp')}")
    box("BÁO CÁO TỔNG HỢP", lines, C.MAG)


def feature_clear() -> None:
    ans = safe_input(f"  {C.RED}Xóa hết local + Supabase? (yes/N): {C.R}").strip().lower()
    if ans == "yes":
        rows = load_local()
        for r in rows:
            sb_delete(r["code"])
        if os.path.isfile(ACCOUNTS_FILE):
            os.remove(ACCOUNTS_FILE)
        log("Đã xóa local + cloud.", C.YEL)
    else:
        log("Hủy.", C.DIM)


SQL_CREATE = """
-- Chạy 1 lần trong Supabase Dashboard → SQL Editor
create table if not exists public.noitu_accounts (
  code text primary key,
  access_token text not null,
  refresh_token text not null,
  name text default '',
  level int default 1,
  xp int default 0,
  updated_at timestamptz default now(),
  created_at timestamptz default now()
);

alter table public.noitu_accounts enable row level security;

-- service_role bỏ qua RLS; anon chỉ đọc nếu cần:
drop policy if exists "allow_service" on public.noitu_accounts;
create policy "allow_all_service" on public.noitu_accounts
  for all using (true) with check (true);
"""


def feature_supabase() -> None:
    box(
        "SUPABASE",
        [
            f"URL: {SUPABASE_URL}",
            f"Table: {SB_TABLE}",
            f"{C.GRN}[a]{C.R} In SQL tạo bảng (copy)",
            f"{C.GRN}[b]{C.R} Kiểm tra kết nối",
            f"{C.GRN}[c]{C.R} Push local → cloud",
            f"{C.GRN}[d]{C.R} Pull cloud → local",
            f"{C.YEL}[x]{C.R} Quay lại",
        ],
        C.CYN,
    )
    sub = safe_input(f"  {C.BOLD}Chọn{C.R} › ").strip().lower()
    if sub == "a":
        print("\n" + C.YEL + SQL_CREATE + C.R)
        log("Copy SQL trên → Supabase Dashboard → SQL Editor → Run", C.CYN)
    elif sub == "b":
        global _sb_ok
        _sb_ok = None
        if sb_check():
            n = len(sb_fetch_all())
            box("SUPABASE OK", [f"Bảng tồn tại", f"Số acc trên cloud: {C.GRN}{n}{C.R}"], C.GRN)
        else:
            box("SUPABASE LỖI", ["Chưa có bảng hoặc sai key", "Chọn [a] để lấy SQL tạo bảng"], C.RED)
    elif sub == "c":
        if not sb_check():
            log("Cloud chưa sẵn sàng. Tạo bảng trước ([a]).", C.RED)
            return
        ok, fail = sync_local_to_cloud()
        box("PUSH XONG", [f"OK: {ok}", f"Fail: {fail}"], C.GRN)
    elif sub == "d":
        n = sync_cloud_to_local()
        box("PULL XONG", [f"Cloud rows: {n}", f"Đã merge vào {ACCOUNTS_FILE}"], C.GRN)
    else:
        log("Quay lại menu.", C.DIM)


# ═══════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════
def main() -> None:
    attach_tty()  # fix EOF khi chạy curl | python3
    if sys.platform != "win32":
        pass
    banner()
    sb_check()  # probe cloud (local vẫn dùng nếu fail)
    while True:
        menu()
        choice = safe_input(f"  {C.BOLD}Chọn{C.R} › ").strip()
        print()
        if choice == "1":
            feature_create()
        elif choice == "2":
            feature_grind()
        elif choice == "3":
            feature_chat_spam()
        elif choice == "4":
            feature_full()
        elif choice == "5":
            feature_list()
        elif choice == "6":
            feature_report()
        elif choice == "7":
            feature_clear()
        elif choice == "8":
            feature_supabase()
        elif choice == "0":
            log("Bye!", C.CYN)
            break
        else:
            log("Lựa chọn không hợp lệ.", C.YEL)
        print()


if __name__ == "__main__":
    main()
