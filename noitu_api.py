#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""noitu.fun API client: guest accounts, solo grind, ranked queue, STOMP chat."""
from __future__ import annotations

import json
import random
import string
import threading
import time
import uuid
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

import requests

try:
    import websocket
except ImportError:  # pragma: no cover
    websocket = None  # type: ignore

BASE = "https://api.noitu.fun/api/v1"
WS_BASE = "wss://api.noitu.fun/ws"
ORIGIN = "https://www.noitu.fun"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def _headers(token: Optional[str] = None) -> Dict[str, str]:
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


def robust(fn: Callable, tries: int = 5, label: str = "", base_delay: float = 1.5):
    delay = base_delay
    last_exc = None
    for i in range(tries):
        try:
            return fn()
        except (requests.exceptions.RequestException, OSError) as e:
            last_exc = e
            log(f"    [net] {label} {type(e).__name__} -> retry {delay:.0f}s ({i+1}/{tries})")
            time.sleep(delay)
            delay = min(delay * 1.6, 20)
    if last_exc:
        raise last_exc
    return None


# ---------------------------------------------------------------------------
# Account / auth
# ---------------------------------------------------------------------------

def create_guest() -> Dict[str, Any]:
    """POST /user/init -> guest account with accessToken + refreshToken."""

    def _do():
        r = requests.post(
            f"{BASE}/user/init",
            json={"id": None, "code": None},
            headers=_headers(),
            timeout=20,
        )
        r.raise_for_status()
        return r.json()

    data = robust(_do, label="user/init")
    return data


def refresh_token(refresh: str) -> Dict[str, Any]:
    def _do():
        r = requests.post(
            f"{BASE}/auth/refresh",
            json={"refreshToken": refresh},
            headers=_headers(),
            timeout=20,
        )
        r.raise_for_status()
        return r.json()

    return robust(_do, label="auth/refresh")


def get_user(code: str, token: str) -> Dict[str, Any]:
    def _do():
        r = requests.get(
            f"{BASE}/user/get",
            params={"code": code},
            headers=_headers(token),
            timeout=20,
        )
        r.raise_for_status()
        return r.json()

    return robust(_do, label="user/get")


# ---------------------------------------------------------------------------
# Solo word-link grind
# ---------------------------------------------------------------------------

def solo_start(token: str, session_id: Optional[str] = None) -> Tuple[str, Dict[str, Any]]:
    sid = session_id or str(uuid.uuid4())

    def _do():
        r = requests.get(
            f"{BASE}/word-link/start",
            params={"sessionId": sid},
            headers=_headers(token),
            timeout=25,
        )
        r.raise_for_status()
        return r.json()

    data = robust(_do, label="word-link/start")
    return sid, data


def solo_answer(token: str, session_id: str, answer: str) -> Dict[str, Any]:
    def _do():
        r = requests.post(
            f"{BASE}/word-link/answer",
            json={"sessionId": session_id, "answer": answer},
            headers=_headers(token),
            timeout=25,
        )
        r.raise_for_status()
        return r.json()

    return robust(_do, label="word-link/answer")


def solo_skip(token: str, session_id: str) -> Dict[str, Any]:
    def _do():
        r = requests.get(
            f"{BASE}/word-link/skip",
            params={"sessionId": session_id},
            headers=_headers(token),
            timeout=25,
        )
        r.raise_for_status()
        return r.json()

    return robust(_do, label="word-link/skip")


def solo_result(token: str, code: str, session_id: str) -> Dict[str, Any]:
    def _do():
        r = requests.get(
            f"{BASE}/word-link/result",
            params={"userCode": code, "sessionId": session_id},
            headers=_headers(token),
            timeout=25,
        )
        r.raise_for_status()
        return r.json()

    return robust(_do, label="word-link/result")


def play_solo_game(token: str, code: str, word_dict, max_turns: int = 50) -> Dict[str, Any]:
    """Play one solo game, return result + final score."""
    sid, data = solo_start(token)
    wd = data.get("wordDescription") or {}
    cur = (wd.get("word") or "").strip().lower()
    if not cur:
        return {"score": 0, "sessionId": sid, "error": "no_start_word"}

    used: Set[str] = {cur}
    score = 0
    finished = False

    for turn in range(max_turns):
        last = cur.split()[-1]
        ans = word_dict.pick(last, used)
        if not ans:
            try:
                data = solo_skip(token, sid)
            except Exception:
                break
            if data.get("isFinished"):
                finished = True
                score = data.get("score", score)
                break
            nwd = data.get("wordDescription") or {}
            if nwd.get("word"):
                cur = nwd["word"].strip().lower()
                used.add(cur)
            continue

        used.add(ans)
        try:
            data = solo_answer(token, sid, ans)
        except Exception as e:
            log(f"    answer error: {e}")
            break

        ok = data.get("isSuccessful")
        score = data.get("score", score)
        if data.get("isFinished"):
            finished = True
            break
        if not ok:
            # try a few more candidates
            for alt in word_dict.next_words(last, used, limit=5):
                used.add(alt)
                try:
                    data = solo_answer(token, sid, alt)
                except Exception:
                    continue
                if data.get("isSuccessful"):
                    score = data.get("score", score)
                    nwd = data.get("wordDescription") or {}
                    if nwd.get("word"):
                        cur = nwd["word"].strip().lower()
                        used.add(cur)
                    if data.get("isFinished"):
                        finished = True
                    break
            if finished:
                break
            continue

        nwd = data.get("wordDescription") or {}
        if nwd.get("word"):
            cur = nwd["word"].strip().lower()
            used.add(cur)
        time.sleep(0.12 + random.random() * 0.15)

    try:
        result = solo_result(token, code, sid)
    except Exception:
        result = {}

    return {
        "sessionId": sid,
        "score": score,
        "finished": finished,
        "result": result,
    }


# ---------------------------------------------------------------------------
# Ranked queue (1v1 WORD_LINK)
# ---------------------------------------------------------------------------

def ranked_join(token: str, code: str, game: str = "WORD_LINK") -> str:
    def _do():
        r = requests.post(
            f"{BASE}/ranked/queue/join",
            params={"userCode": code, "game": game},
            headers=_headers(token),
            timeout=20,
        )
        r.raise_for_status()
        return r.text.strip().strip('"')

    return robust(_do, label="ranked/join")


def ranked_leave(token: str, code: str) -> None:
    def _do():
        r = requests.post(
            f"{BASE}/ranked/queue/leave",
            params={"userCode": code},
            headers=_headers(token),
            timeout=15,
        )
        return r.status_code

    try:
        robust(_do, tries=2, label="ranked/leave")
    except Exception:
        pass


def ranked_status(token: str, code: str) -> Any:
    def _do():
        r = requests.get(
            f"{BASE}/ranked/queue/status",
            params={"userCode": code},
            headers=_headers(token),
            timeout=15,
        )
        r.raise_for_status()
        try:
            return r.json()
        except Exception:
            return r.text

    return robust(_do, label="ranked/status")


# ---------------------------------------------------------------------------
# STOMP over SockJS WebSocket (chat + notifications)
# ---------------------------------------------------------------------------

class StompClient:
    """Minimal STOMP client over SockJS websocket for noitu.fun."""

    def __init__(self, token: str):
        self.token = token
        self.ws = None
        self.connected = False
        self._frames: List[Tuple[str, Any]] = []
        self._lock = threading.Lock()
        self._sub_id = 0

    def connect(self, timeout: float = 12.0) -> bool:
        if websocket is None:
            log("[stomp] websocket-client not installed")
            return False

        # SockJS websocket URL
        server = str(random.randint(100, 999))
        session = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
        url = f"{WS_BASE}/{server}/{session}/websocket"

        done = threading.Event()
        self.connected = False

        def on_open(ws):
            # SockJS open frame is handled by library; send STOMP CONNECT
            connect_frame = (
                "CONNECT\n"
                f"Authorization:Bearer {self.token}\n"
                "accept-version:1.1,1.0\n"
                "heart-beat:10000,10000\n"
                "\n\x00"
            )
            ws.send(connect_frame)

        def on_message(ws, message):
            # SockJS wraps: a["..."] or o / h / c
            if not message:
                return
            if message.startswith("o"):
                return
            if message.startswith("h"):
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
                    self._handle_stomp(raw)
            else:
                self._handle_stomp(message)

        def _handle_connected():
            self.connected = True
            done.set()

        self._on_connected = _handle_connected

        def on_error(ws, err):
            log(f"[stomp] error: {err}")

        def on_close(ws, *args):
            self.connected = False

        self.ws = websocket.WebSocketApp(
            url,
            header=[f"Origin: {ORIGIN}"],
            on_open=on_open,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close,
        )

        t = threading.Thread(target=lambda: self.ws.run_forever(ping_interval=20), daemon=True)
        t.start()
        done.wait(timeout=timeout)
        return self.connected

    def _handle_stomp(self, raw: str):
        if not isinstance(raw, str):
            return
        if raw.startswith("CONNECTED"):
            if hasattr(self, "_on_connected"):
                self._on_connected()
            return
        # MESSAGE\nheaders\n\nbody\x00
        if raw.startswith("MESSAGE"):
            dest = ""
            body = ""
            parts = raw.split("\n\n", 1)
            headers = parts[0]
            if len(parts) > 1:
                body = parts[1].rstrip("\x00")
            for line in headers.split("\n"):
                if line.lower().startswith("destination:"):
                    dest = line.split(":", 1)[1].strip()
            payload: Any = body
            try:
                payload = json.loads(body)
            except Exception:
                pass
            with self._lock:
                self._frames.append((dest, payload))

    def subscribe(self, destination: str) -> None:
        if not self.ws:
            return
        self._sub_id += 1
        frame = (
            f"SUBSCRIBE\nid:sub-{self._sub_id}\n"
            f"destination:{destination}\n\n\x00"
        )
        try:
            self.ws.send(frame)
        except Exception as e:
            log(f"[stomp] subscribe failed: {e}")

    def send(self, destination: str, body: dict) -> None:
        if not self.ws:
            return
        payload = json.dumps(body, ensure_ascii=False)
        frame = (
            f"SEND\ndestination:{destination}\n"
            f"content-type:application/json\n\n{payload}\x00"
        )
        try:
            self.ws.send(frame)
        except Exception as e:
            log(f"[stomp] send failed: {e}")

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


def send_chat_test(token: str, message: str = "test", wait: float = 8.0) -> Dict[str, Any]:
    """Connect STOMP, join chat, send message, report delivery / gate."""
    ws = StompClient(token)
    ok = ws.connect()
    if not ok:
        return {"connected": False, "delivered": False, "gated": False, "frames": 0}

    for d in ("/room/chat-room", "/user/queue/user-notification"):
        ws.subscribe(d)
    time.sleep(0.8)
    ws.drain()

    ws.send("/app/chat/join", {"chatType": "JOIN"})
    time.sleep(0.6)
    ws.send("/app/chat", {"message": message})
    log(f"[chat] sent message={message!r}")

    got: List[Tuple[str, Any]] = []
    t0 = time.time()
    while time.time() - t0 < wait:
        for dest, payload in ws.drain():
            got.append((dest, payload))
            s = json.dumps(payload, ensure_ascii=False) if isinstance(payload, (dict, list)) else str(payload)
            log(f"    <- [{dest}] {s[:200]}")
        time.sleep(0.4)
    ws.close()

    delivered = any(
        (d.endswith("/room/chat-room") or "chat-room" in d)
        and message in (json.dumps(p, ensure_ascii=False) if not isinstance(p, str) else p)
        for d, p in got
    )
    gated = any(
        "CHAT_LEVEL_REQUIREMENT" in (json.dumps(p, ensure_ascii=False) if not isinstance(p, str) else p)
        for _, p in got
    )
    return {
        "connected": True,
        "delivered": delivered,
        "gated": gated,
        "frames": len(got),
        "raw": got,
    }
