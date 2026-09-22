#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
noitu.fun automation bot
------------------------
- Tạo guest account (không cần đăng ký email)
- Lưu phiên (code + tokens) vào accounts.txt
- Cày solo nối từ đến level 2
- Nhắn "test" lên chat (STOMP)

Usage:
  python bot.py create [N]          # tạo N acc (mặc định 1), lưu accounts.txt
  python bot.py grind [code]        # cày 1 acc (hoặc tất cả) đến lv2 rồi chat test
  python bot.py chat [code]         # chỉ gửi chat test (cần đã lv>=2)
  python bot.py list                # liệt kê accounts đã lưu
  python bot.py full [N]            # tạo N acc, cày hết đến lv2 + chat

Accounts file format (accounts.txt):
  code|accessToken|refreshToken|name|level|xp
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from typing import Any, Dict, List, Optional

from word_dict import WordDict
import noitu_api as api

ACCOUNTS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "accounts.txt")
TARGET_LEVEL = 2
CHAT_MSG = "test"
MAX_GAMES = 80
STALL_BACKOFF = 40


def load_accounts() -> List[Dict[str, str]]:
    rows = []
    if not os.path.isfile(ACCOUNTS_FILE):
        return rows
    with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("|")
            if len(parts) < 3:
                continue
            rows.append({
                "code": parts[0],
                "accessToken": parts[1],
                "refreshToken": parts[2],
                "name": parts[3] if len(parts) > 3 else "",
                "level": parts[4] if len(parts) > 4 else "1",
                "xp": parts[5] if len(parts) > 5 else "0",
            })
    return rows


def save_accounts(rows: List[Dict[str, str]]) -> None:
    with open(ACCOUNTS_FILE, "w", encoding="utf-8") as f:
        f.write("# code|accessToken|refreshToken|name|level|xp\n")
        for r in rows:
            f.write(
                f"{r['code']}|{r['accessToken']}|{r['refreshToken']}|"
                f"{r.get('name','')}|{r.get('level','1')}|{r.get('xp','0')}\n"
            )


def upsert_account(acc: Dict[str, str]) -> None:
    rows = load_accounts()
    found = False
    for i, r in enumerate(rows):
        if r["code"] == acc["code"]:
            rows[i] = acc
            found = True
            break
    if not found:
        rows.append(acc)
    save_accounts(rows)


def ensure_token(acc: Dict[str, str]) -> str:
    """Return valid access token, refresh if needed."""
    code = acc["code"]
    try:
        u = api.get_user(code, acc["accessToken"])
        if u and "level" in u:
            return acc["accessToken"]
    except Exception:
        pass
    api.log(f"[auth] refreshing token for {code}")
    data = api.refresh_token(acc["refreshToken"])
    new_tok = data.get("accessToken")
    if not new_tok:
        raise RuntimeError(f"Cannot refresh token for {code}")
    acc["accessToken"] = new_tok
    if data.get("refreshToken"):
        acc["refreshToken"] = data["refreshToken"]
    upsert_account(acc)
    return new_tok


def cmd_create(n: int = 1) -> None:
    for i in range(n):
        data = api.create_guest()
        acc = {
            "code": data["code"],
            "accessToken": data["accessToken"],
            "refreshToken": data["refreshToken"],
            "name": data.get("name", ""),
            "level": str(data.get("level", 1)),
            "xp": "0",
        }
        upsert_account(acc)
        api.log(f"[+] created {i+1}/{n}: {acc['code']} name={acc['name']}")
        time.sleep(0.4)
    api.log(f"Saved -> {ACCOUNTS_FILE}")


def cmd_list() -> None:
    rows = load_accounts()
    if not rows:
        print("(empty)")
        return
    for r in rows:
        print(f"  {r['code']}  lv={r.get('level')}  xp={r.get('xp')}  name={r.get('name')}")


def progress(acc: Dict[str, str], token: str):
    u = api.get_user(acc["code"], token)
    level = u.get("level", 1)
    xp = u.get("experiencePoints", 0)
    need = u.get("nextLevelRequirement", 50)
    acc["level"] = str(level)
    acc["xp"] = str(xp)
    upsert_account(acc)
    return level, xp, need


def grind_one(acc: Dict[str, str], wdict: WordDict) -> bool:
    code = acc["code"]
    token = ensure_token(acc)
    level, xp, need = progress(acc, token)
    api.log(f"[grind] {code} start level={level} xp={xp}/{need}")

    if level >= TARGET_LEVEL:
        api.log(f"[grind] already level {level}")
        return True

    games = 0
    stall = 0
    last_xp = xp

    while level < TARGET_LEVEL and games < MAX_GAMES:
        games += 1
        api.log(f"[grind] game #{games} (lv={level} xp={xp})")
        try:
            res = api.play_solo_game(token, code, wdict)
        except Exception as e:
            api.log(f"    game error: {e}")
            time.sleep(3)
            try:
                token = ensure_token(acc)
            except Exception:
                pass
            continue

        api.log(f"    score={res.get('score')} finished={res.get('finished')} result={res.get('result')}")
        time.sleep(1.0)

        try:
            level, xp, need = progress(acc, token)
        except Exception as e:
            api.log(f"    progress error: {e}")
            try:
                token = ensure_token(acc)
                level, xp, need = progress(acc, token)
            except Exception:
                time.sleep(5)
                continue

        api.log(f"    -> level={level} xp={xp}/{need}")

        if xp <= last_xp:
            stall += 1
            if stall >= 3:
                api.log(f"    XP stalled, backoff {STALL_BACKOFF}s")
                time.sleep(STALL_BACKOFF)
                stall = 0
        else:
            stall = 0
            last_xp = xp

        time.sleep(0.8)

    ok = level >= TARGET_LEVEL
    api.log(f"[grind] done {code} level={level} ok={ok}")
    return ok


def chat_one(acc: Dict[str, str]) -> None:
    token = ensure_token(acc)
    level, xp, need = progress(acc, token)
    api.log(f"[chat] {acc['code']} level={level}")
    if level < TARGET_LEVEL:
        api.log(f"[!] level {level} < {TARGET_LEVEL}, chat may be gated")
    result = api.send_chat_test(token, CHAT_MSG)
    api.log(
        f"[chat] connected={result.get('connected')} "
        f"delivered={result.get('delivered')} gated={result.get('gated')} "
        f"frames={result.get('frames')}"
    )
    if result.get("delivered") and not result.get("gated"):
        api.log("[+] VERIFIED: chat 'test' delivered")
    elif result.get("gated"):
        api.log("[!] still gated by CHAT_LEVEL_REQUIREMENT")
    else:
        api.log("[?] inconclusive (check frames / websocket)")


def cmd_grind(code: Optional[str] = None) -> None:
    wdict = WordDict()
    rows = load_accounts()
    if not rows:
        api.log("No accounts. Run: python bot.py create 1")
        return
    targets = [r for r in rows if (not code or r["code"] == code)]
    if not targets:
        api.log(f"Account not found: {code}")
        return
    for acc in targets:
        ok = grind_one(acc, wdict)
        if ok:
            chat_one(acc)


def cmd_chat(code: Optional[str] = None) -> None:
    rows = load_accounts()
    targets = [r for r in rows if (not code or r["code"] == code)]
    if not targets:
        api.log("No matching accounts")
        return
    for acc in targets:
        chat_one(acc)


def cmd_full(n: int = 1) -> None:
    cmd_create(n)
    cmd_grind()


def main():
    p = argparse.ArgumentParser(description="noitu.fun bot - create / grind / chat")
    sub = p.add_subparsers(dest="cmd")

    c = sub.add_parser("create", help="Create N guest accounts")
    c.add_argument("n", nargs="?", type=int, default=1)

    g = sub.add_parser("grind", help="Grind account(s) to level 2 then chat")
    g.add_argument("code", nargs="?", default=None)

    ch = sub.add_parser("chat", help="Send chat 'test'")
    ch.add_argument("code", nargs="?", default=None)

    sub.add_parser("list", help="List saved accounts")

    f = sub.add_parser("full", help="Create N + grind all + chat")
    f.add_argument("n", nargs="?", type=int, default=1)

    args = p.parse_args()
    if not args.cmd:
        p.print_help()
        return

    if args.cmd == "create":
        cmd_create(args.n)
    elif args.cmd == "grind":
        cmd_grind(args.code)
    elif args.cmd == "chat":
        cmd_chat(args.code)
    elif args.cmd == "list":
        cmd_list()
    elif args.cmd == "full":
        cmd_full(args.n)


if __name__ == "__main__":
    main()
