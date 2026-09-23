#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""NOITU.FUN BOT — Rank thật + tool.js logic + Playwright optional + Supabase."""
from __future__ import annotations

import json, os, random, re, signal, string, sys, threading, time, uuid
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

try:
    import requests
except ImportError:
    print("pip install requests"); sys.exit(1)
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None
try:
    import websocket
except ImportError:
    websocket = None

BASE = "https://api.noitu.fun/api/v1"
SITE = "https://www.noitu.fun"
WS_BASE = "wss://api.noitu.fun/ws"
ORIGIN = SITE
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
try:
    HERE = os.path.dirname(os.path.abspath(__file__))
except NameError:
    HERE = os.getcwd()
ACCOUNTS_FILE = os.path.join(HERE, "accounts.txt")
DICT_FILE = os.path.join(HERE, "filtered_words.txt")
DICT_URL = "https://raw.githubusercontent.com/ontopcommunity/tuvungvn/main/filtered_words.txt"
SUPABASE_URL = "https://tdlubyvugaucfexezhrk.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRkbHVieXZ1Z2F1Y2ZleGV6aHJrIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4Njc4NTcyMSwiZXhwIjoyMTAyMzYxNzIxfQ.7JkJVP9FzC51rZRwdKGL4IdY-m6ZGxyNoRE5WAGt2KU"
SB_TABLE = "noitu_accounts"
TARGET_LEVEL = 2
MAX_PARALLEL = 100
MAX_GAMES = 120
CHAT_INTERVAL = 0.1
STALL_BACKOFF = 25
MATCH_WAIT = 60
HEADLESS = True

class C:
    R="\033[0m"; BOLD="\033[1m"; DIM="\033[2m"; RED="\033[91m"; GRN="\033[92m"
    YEL="\033[93m"; BLU="\033[94m"; MAG="\033[95m"; CYN="\033[96m"; WHT="\033[97m"

_print_lock = threading.Lock()
def ts(): return datetime.now().strftime("%H:%M:%S")
def log(msg, color=C.WHT):
    with _print_lock:
        print(f"{C.DIM}[{ts()}]{C.R} {color}{msg}{C.R}", flush=True)
def attach_tty():
    try:
        if not sys.stdin.isatty():
            sys.stdin = open("/dev/tty","r")
    except Exception:
        pass
def safe_input(prompt=""):
    try: return input(prompt)
    except EOFError:
        log("EOF — dùng: curl ... -o /tmp/noitubot.py && python3 /tmp/noitubot.py", C.RED)
        raise SystemExit(1)
def banner():
    print(f"""
{C.CYN}{C.BOLD}╔══════════════════════════════════════════════════════════╗
║  NOITU.FUN BOT · Rank 1v1 thật · tool.js · PW optional   ║
║  Parallel ≤{MAX_PARALLEL} · Skip lv≥{TARGET_LEVEL} · Local+Supabase              ║
╚══════════════════════════════════════════════════════════╝{C.R}
""")
def _strip(s): return re.sub(r"\033\[[0-9;]*m","",s)
def box(title, lines, color=C.CYN):
    w = max(len(title)+4, max((len(_strip(l)) for l in lines), default=20)+4, 44)
    print(f"{color}╔{'═'*(w-2)}╗{C.R}")
    print(f"{color}║{C.R} {C.BOLD}{title}{C.R}{' '*(w-4-len(title))} {color}║{C.R}")
    print(f"{color}╠{'═'*(w-2)}╣{C.R}")
    for line in lines:
        print(f"{color}║{C.R} {line}{' '*max(0,w-4-len(_strip(line)))} {color}║{C.R}")
    print(f"{color}╚{'═'*(w-2)}╝{C.R}")
def menu():
    box("MENU CHÍNH", [
        f"{C.GRN}[1]{C.R}  Tạo account mới (không giới hạn)",
        f"{C.GRN}[2]{C.R}  Cày RANK lv{TARGET_LEVEL} song song (max {MAX_PARALLEL}, bỏ qua đã lv{TARGET_LEVEL})",
        f"{C.GRN}[3]{C.R}  Chat spam acc có sẵn (100ms, Ctrl+C)",
        f"{C.GRN}[4]{C.R}  Xem danh sách account",
        f"{C.GRN}[5]{C.R}  Báo cáo tổng hợp",
        f"{C.GRN}[6]{C.R}  Đồng bộ Supabase",
        f"{C.GRN}[7]{C.R}  Xóa account local+cloud",
        f"{C.YEL}[0]{C.R}  Thoát",
    ], C.BLU)

class WordDict:
    def __init__(self):
        self.words=[]; self.by_first=defaultdict(list); self._load()
    def _load(self):
        path=DICT_FILE
        if not os.path.isfile(path):
            log("Tải từ điển...", C.YEL)
            try:
                r=requests.get(DICT_URL,timeout=60); r.raise_for_status()
                open(path,"w",encoding="utf-8").write(r.text)
            except Exception as e:
                log(f"Dict fail: {e}", C.RED); return
        seen=set()
        for line in open(path,encoding="utf-8"):
            w=line.strip().lower()
            if not w or " " not in w or w in seen: continue
            parts=w.split()
            if len(parts)<2: continue
            seen.add(w); self.words.append(w); self.by_first[parts[0]].append(w)
        for k in self.by_first: random.shuffle(self.by_first[k])
        log(f"Từ điển: {C.GRN}{len(self.words)}{C.R}", C.CYN)
    def pick(self, last, used, n=20):
        return [w for w in self.by_first.get(last.lower().strip(),[]) if w not in used][:n]

def _hdr(token=None):
    h={"Origin":ORIGIN,"Referer":ORIGIN+"/","Content-Type":"application/json","Accept":"application/json","User-Agent":UA}
    if token: h["Authorization"]=f"Bearer {token}"
    return h

def robust(fn, tries=5, label=""):
    delay=1.2; last=None
    for i in range(tries):
        try: return fn()
        except requests.exceptions.HTTPError as e:
            last=e; code=getattr(getattr(e,"response",None),"status_code","?")
            body=""
            try: body=(e.response.text or "")[:80]
            except Exception: pass
            log(f"  net {label} HTTP {code} {body!r} ({i+1}/{tries})", C.DIM)
            if code in (400,401,403,404): break
            time.sleep(delay); delay=min(delay*1.6,15)
        except (requests.exceptions.RequestException, OSError) as e:
            last=e; log(f"  net {label} {type(e).__name__} ({i+1}/{tries})", C.DIM)
            time.sleep(delay); delay=min(delay*1.6,15)
    if last: raise last

_acc_lock=threading.Lock(); _sb_ok=None
def _sb_h():
    return {"apikey":SUPABASE_KEY,"Authorization":f"Bearer {SUPABASE_KEY}","Content-Type":"application/json","Prefer":"return=representation"}
def sb_check():
    global _sb_ok
    if _sb_ok is not None: return _sb_ok
    try:
        r=requests.get(f"{SUPABASE_URL}/rest/v1/{SB_TABLE}",params={"select":"code","limit":"1"},headers=_sb_h(),timeout=15)
        _sb_ok = r.status_code==200
        log(f"Supabase {'OK' if _sb_ok else 'fail — local only'}", C.GRN if _sb_ok else C.YEL)
    except Exception as e:
        _sb_ok=False; log(f"Supabase: {e}", C.YEL)
    return bool(_sb_ok)
def sb_fetch_all():
    if not sb_check(): return []
    try:
        r=requests.get(f"{SUPABASE_URL}/rest/v1/{SB_TABLE}",params={"select":"*"},headers=_sb_h(),timeout=30); r.raise_for_status()
        return [{"code":x["code"],"accessToken":x.get("access_token") or "","refreshToken":x.get("refresh_token") or "",
                 "name":x.get("name") or "","level":str(x.get("level") if x.get("level") is not None else 1),
                 "xp":str(x.get("xp") if x.get("xp") is not None else 0)} for x in r.json()]
    except Exception as e:
        log(f"sb_fetch: {e}", C.YEL); return []
def sb_upsert(acc):
    if not sb_check(): return False
    payload={"code":acc["code"],"access_token":acc["accessToken"],"refresh_token":acc["refreshToken"],
             "name":acc.get("name") or "","level":int(acc.get("level") or 1),"xp":int(acc.get("xp") or 0),
             "updated_at":datetime.now(timezone.utc).isoformat()}
    try:
        h=_sb_h(); h["Prefer"]="resolution=merge-duplicates,return=minimal"
        r=requests.post(f"{SUPABASE_URL}/rest/v1/{SB_TABLE}",params={"on_conflict":"code"},headers=h,json=payload,timeout=20)
        if r.status_code not in (200,201,204):
            r2=requests.patch(f"{SUPABASE_URL}/rest/v1/{SB_TABLE}",params={"code":f"eq.{acc['code']}"},headers=_sb_h(),json=payload,timeout=20)
            return r2.status_code in (200,204)
        return True
    except Exception as e:
        log(f"sb_upsert: {e}", C.YEL); return False
def sb_delete(code):
    if not sb_check(): return
    try: requests.delete(f"{SUPABASE_URL}/rest/v1/{SB_TABLE}",params={"code":f"eq.{code}"},headers=_sb_h(),timeout=15)
    except Exception: pass
def load_local():
    rows=[]
    if not os.path.isfile(ACCOUNTS_FILE): return rows
    for line in open(ACCOUNTS_FILE,encoding="utf-8"):
        line=line.strip()
        if not line or line.startswith("#"): continue
        p=line.split("|")
        if len(p)<3: continue
        rows.append({"code":p[0],"accessToken":p[1],"refreshToken":p[2],"name":p[3] if len(p)>3 else "",
                     "level":p[4] if len(p)>4 else "1","xp":p[5] if len(p)>5 else "0"})
    return rows
def save_local(rows):
    with open(ACCOUNTS_FILE,"w",encoding="utf-8") as f:
        f.write("# code|accessToken|refreshToken|name|level|xp\n")
        for r in rows:
            f.write(f"{r['code']}|{r['accessToken']}|{r['refreshToken']}|{r.get('name','')}|{r.get('level','1')}|{r.get('xp','0')}\n")
def _merge(local, cloud):
    by={r["code"]:dict(r) for r in local}
    for r in cloud:
        if r["code"] not in by: by[r["code"]]=dict(r)
        else:
            cur=by[r["code"]]
            try:
                if int(r.get("level") or 0)>int(cur.get("level") or 0) or (int(r.get("level") or 0)==int(cur.get("level") or 0) and int(r.get("xp") or 0)>=int(cur.get("xp") or 0)):
                    by[r["code"]]={**cur,"accessToken":r.get("accessToken") or cur.get("accessToken",""),"refreshToken":r.get("refreshToken") or cur.get("refreshToken",""),
                                   "level":r.get("level",cur.get("level")),"xp":r.get("xp",cur.get("xp")),"name":r.get("name") or cur.get("name","")}
            except ValueError: pass
    return list(by.values())
def load_accounts():
    m=_merge(load_local(), sb_fetch_all())
    if m: save_local(m)
    return m
def upsert_account(acc):
    with _acc_lock:
        rows=load_local()
        for i,r in enumerate(rows):
            if r["code"]==acc["code"]: rows[i]=acc; save_local(rows); break
        else:
            rows.append(acc); save_local(rows)
    sb_upsert(acc)
def accounts_need_grind():
    return [r for r in load_accounts() if int(r.get("level") or 1)<TARGET_LEVEL]

def api_create_guest():
    def _do():
        r=requests.post(f"{BASE}/user/init",json={"id":None,"code":None},headers=_hdr(),timeout=25)
        r.raise_for_status(); return r.json()
    return robust(_do, label="init")
def api_refresh(ref):
    def _do():
        r=requests.post(f"{BASE}/auth/refresh",json={"refreshToken":ref},headers=_hdr(),timeout=20)
        r.raise_for_status(); return r.json()
    return robust(_do, label="refresh")
def api_get_user(code, token):
    def _do():
        r=requests.get(f"{BASE}/user/get",params={"code":code},headers=_hdr(token),timeout=20)
        r.raise_for_status(); return r.json()
    return robust(_do, label="user/get")
def ensure_token(acc):
    try:
        u=api_get_user(acc["code"], acc["accessToken"])
        if u and "level" in u: return acc["accessToken"]
    except Exception: pass
    data=api_refresh(acc["refreshToken"]); tok=data.get("accessToken")
    if not tok: raise RuntimeError("refresh failed")
    acc["accessToken"]=tok
    if data.get("refreshToken"): acc["refreshToken"]=data["refreshToken"]
    upsert_account(acc); return tok
def progress(acc, token):
    u=api_get_user(acc["code"], token)
    level=int(u.get("level",1)); xp=int(u.get("experiencePoints",0)); need=int(u.get("nextLevelRequirement",50))
    acc["level"]=str(level); acc["xp"]=str(xp); upsert_account(acc)
    return level,xp,need
def ranked_join(token, code):
    def _do():
        r=requests.post(f"{BASE}/ranked/queue/join",params={"userCode":code,"game":"WORD_LINK"},headers=_hdr(token),timeout=20)
        r.raise_for_status(); return r.text.strip().strip('"')
    return robust(_do, label="rank/join")
def ranked_leave(token, code):
    try: requests.post(f"{BASE}/ranked/queue/leave",params={"userCode":code},headers=_hdr(token),timeout=12)
    except Exception: pass
def word_start(token, sid):
    def _do():
        r=requests.get(f"{BASE}/word-link/start",params={"sessionId":sid},headers=_hdr(token),timeout=25)
        r.raise_for_status(); return r.json()
    return robust(_do, label="wl/start")
def word_answer(token, sid, answer):
    def _do():
        r=requests.post(f"{BASE}/word-link/answer",json={"sessionId":sid,"answer":answer},headers=_hdr(token),timeout=25)
        if r.status_code==400:
            try: return r.json()
            except Exception: pass
        r.raise_for_status(); return r.json()
    return robust(_do, tries=2, label="wl/answer")
def word_result(token, code, sid):
    def _do():
        r=requests.get(f"{BASE}/word-link/result",params={"userCode":code,"sessionId":sid},headers=_hdr(token),timeout=20)
        r.raise_for_status(); return r.json()
    return robust(_do, label="wl/result")

def play_tooljs_session(token, code, wdict, sid=None):
    """Chơi 1 session word-link theo logic tool.js (từ điển âm tiết đầu)."""
    sid = sid or str(uuid.uuid4())
    data = word_start(token, sid)
    cur = ((data.get("wordDescription") or {}).get("word") or "").lower()
    used=set([cur] if cur else [])
    score=0
    for _ in range(40):
        if not cur: break
        last=cur.split()[-1]
        cands=wdict.pick(last, used)
        if not cands: break
        ans=cands[0]; used.add(ans)
        try: data=word_answer(token, sid, ans)
        except Exception: break
        msg=data.get("message") or ""
        if "Time is up" in msg:
            score=data.get("score", score); break
        if data.get("isSuccessful"):
            score=data.get("score", score)
            nwd=data.get("wordDescription") or {}
            if nwd.get("word"):
                cur=nwd["word"].lower(); used.add(cur)
        if data.get("isFinished"): break
        time.sleep(0.05)
    try: word_result(token, code, sid)
    except Exception: pass
    return {"sessionId":sid,"score":score}

def grind_one(acc, wdict):
    """Rank queue thật (WORD_LINK) + chơi; fallback session tool.js nếu chưa match."""
    code=acc["code"]; tag=code[-8:]
    token=ensure_token(acc)
    level,xp,need=progress(acc, token)
    if level>=TARGET_LEVEL:
        return {"ok":True,"level":level,"xp":xp,"games":0,"skipped":True}
    games=0; stall=0; last_xp=xp
    while level<TARGET_LEVEL and games<MAX_GAMES:
        games+=1
        ranked_leave(token, code); time.sleep(0.3)
        try:
            st=ranked_join(token, code)
            log(f"[{tag}] rank queue #{games} → {st}", C.DIM)
        except Exception as e:
            log(f"[{tag}] join: {e}", C.YEL); time.sleep(2); continue
        # chờ match status
        sid=None; t0=time.time()
        while time.time()-t0 < MATCH_WAIT:
            try:
                r=requests.get(f"{BASE}/ranked/queue/status",params={"userCode":code},headers=_hdr(token),timeout=12)
                if r.status_code==200:
                    body=r.text
                    try:
                        jd=r.json() if body.startswith("{") or body.startswith("[") else {}
                    except Exception:
                        jd={}
                    if isinstance(jd, dict):
                        sid=(jd.get("sessionId") or jd.get("roomId") or jd.get("matchId")
                             or (jd.get("data") or {}).get("sessionId"))
                    if sid: break
                    if body and body not in ("QUEUED",'"QUEUED"',"null"):
                        log(f"[{tag}] status {body[:100]}", C.DIM)
            except Exception: pass
            time.sleep(2)
        ranked_leave(token, code)
        # chơi session ranked nếu có, không thì tool.js session (1 acc — không 2-acc)
        try:
            res=play_tooljs_session(token, code, wdict, sid)
            log(f"[{tag}] played score={res.get('score')} sid={str(res.get('sessionId'))[:8]}", C.DIM)
        except Exception as e:
            log(f"[{tag}] play: {e}", C.YEL)
        time.sleep(0.6)
        try: level,xp,need=progress(acc, token)
        except Exception:
            try: token=ensure_token(acc); level,xp,need=progress(acc, token)
            except Exception: continue
        if xp<=last_xp:
            stall+=1
            if stall>=3:
                log(f"[{tag}] XP stall {STALL_BACKOFF}s", C.YEL); time.sleep(STALL_BACKOFF); stall=0
        else:
            stall=0; last_xp=xp; log(f"[{tag}] lv={level} xp={xp}/{need}", C.GRN)
    return {"ok":level>=TARGET_LEVEL,"level":level,"xp":xp,"games":games}

# Playwright path (khi user chạy local, CF cho phép)
def grind_one_pw(acc, wdict):
    if sync_playwright is None:
        return grind_one(acc, wdict)
    code=acc["code"]; tag=code[-8:]
    try:
        token=ensure_token(acc); level,xp,_=progress(acc, token)
    except Exception as e:
        return {"ok":False,"error":str(e)}
    if level>=TARGET_LEVEL:
        return {"ok":True,"level":level,"xp":xp,"games":0,"skipped":True}
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=HEADLESS, args=["--no-sandbox","--disable-dev-shm-usage","--disable-blink-features=AutomationControlled"])
            ctx=browser.new_context(viewport={"width":1280,"height":800}, locale="vi-VN", user_agent=UA)
            ctx.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined});")
            ctx.add_init_script(f"try{{localStorage.setItem('accessToken',{json.dumps(token)});}}catch(e){{}}")
            page=ctx.new_page()
            page.goto(SITE+"/", wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(3000)
            title=page.title() or ""
            if "Cloudflare" in title or "Attention" in title:
                browser.close(); log(f"[{tag}] CF → API", C.YEL); return grind_one(acc, wdict)
            games=0
            while level<TARGET_LEVEL and games<MAX_GAMES:
                games+=1
                page.goto(SITE+"/rank", wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(1500)
                page.evaluate("""() => {
                  const els=[...document.querySelectorAll('button,a,div,[class*=WORD_LINK],[class*=rank]')];
                  const t=els.find(e=>{const s=(e.innerText||'').trim(); return s.includes('Nối Từ') && !s.includes('Mở Rộng') && s.length<100;});
                  if(t) t.click();
                }""")
                used=set(); t0=time.time()
                while time.time()-t0<90:
                    try:
                        we=page.query_selector("a.word-detail_wordDetailWord__1DYml, [class*='wordDetailWord']")
                        ie=page.query_selector("input.word-link-answer-input_input__L6PK2, input[class*='word-link-answer-input']")
                        if we and ie:
                            q=(we.inner_text() or "").strip()
                            if q:
                                last=q.split()[-1].lower()
                                cands=wdict.pick(last, used)
                                if cands:
                                    ans=cands[0]; used.add(ans)
                                    ie.click(); ie.fill(""); ie.type(ans, delay=12)
                                    btn=page.query_selector("svg.lucide-send")
                                    if btn: btn.click()
                                    else: page.keyboard.press("Enter")
                    except Exception: pass
                    page.wait_for_timeout(350)
                try: level,xp,_=progress(acc, token)
                except Exception: pass
                log(f"[{tag}] PW game#{games} lv={level} xp={xp}", C.CYN)
            browser.close()
    except Exception as e:
        log(f"[{tag}] PW {e} → API", C.YEL); return grind_one(acc, wdict)
    return {"ok":level>=TARGET_LEVEL,"level":level,"xp":xp,"games":games}

class StompClient:
    def __init__(self, token):
        self.token=token; self.ws=None; self.connected=False
    def connect(self, timeout=10):
        if websocket is None: return False
        server=str(random.randint(100,999)); session="".join(random.choices(string.ascii_lowercase+string.digits,k=8))
        url=f"{WS_BASE}/{server}/{session}/websocket"; done=threading.Event()
        def on_open(ws):
            ws.send(f"CONNECT\nAuthorization:Bearer {self.token}\naccept-version:1.1,1.0\nheart-beat:10000,10000\n\n\x00")
        def on_message(ws, message):
            if message and message.startswith("a"):
                try:
                    for raw in json.loads(message[1:]):
                        if isinstance(raw,str) and raw.startswith("CONNECTED"):
                            self.connected=True; done.set()
                except Exception: pass
        self.ws=websocket.WebSocketApp(url, header=[f"Origin: {ORIGIN}"], on_open=on_open, on_message=on_message,
                                       on_error=lambda *a:None, on_close=lambda *a:None)
        threading.Thread(target=lambda: self.ws.run_forever(ping_interval=25), daemon=True).start()
        done.wait(timeout); return self.connected
    def send(self, dest, body):
        if not self.ws: return
        payload=json.dumps(body, ensure_ascii=False)
        self.ws.send(f"SEND\ndestination:{dest}\ncontent-type:application/json\n\n{payload}\x00")
    def close(self):
        try:
            if self.ws: self.ws.close()
        except Exception: pass

def feature_create():
    raw=safe_input(f"  {C.CYN}Số account{C.R} [1]: ").strip() or "1"
    try: n=max(1,int(raw))
    except ValueError: n=1
    ok=0
    for i in range(n):
        try:
            d=api_create_guest()
            acc={"code":d["code"],"accessToken":d["accessToken"],"refreshToken":d["refreshToken"],
                 "name":d.get("name") or "","level":str(d.get("level",1)),"xp":"0"}
            upsert_account(acc); ok+=1
            log(f"  [{ok}/{n}] {C.GRN}{acc['code']}{C.R} {acc['name']}")
        except Exception as e:
            log(f"  Lỗi: {e}", C.RED)
        time.sleep(0.25)
    box("TẠO ACC", [f"OK {ok}/{n}"], C.GRN)

def feature_grind():
    need=accounts_need_grind(); alln=len(load_accounts()); done=alln-len(need)
    if not need:
        log(f"Không còn acc cần cày (đã lv≥{TARGET_LEVEL}: {done})", C.YEL); return
    wdict=WordDict()
    if not wdict.words: log("Thiếu dict", C.RED); return
    print(f"\n  Cần cày {C.GRN}{len(need)}{C.R} | Đã lv{TARGET_LEVEL}: {done} | max {MAX_PARALLEL}")
    raw=safe_input(f"  {C.CYN}Số acc{C.R} [{min(len(need),MAX_PARALLEL)}]: ").strip()
    try: n=int(raw) if raw else min(len(need),MAX_PARALLEL)
    except ValueError: n=min(len(need),MAX_PARALLEL)
    n=max(1,min(n,MAX_PARALLEL,len(need)))
    targets=need[:n]
    mode=safe_input(f"  {C.CYN}1=API rank  2=Playwright{C.R} [1]: ").strip() or "1"
    use_pw = mode=="2"
    box("CÀY RANK THẬT", [f"acc={n}", f"mode={'PW' if use_pw else 'API'}", f"skip lv≥{TARGET_LEVEL}"], C.MAG)
    report={}; t0=time.time()
    def worker(a):
        fn=grind_one_pw if use_pw else grind_one
        try: report[a["code"]]=fn(a, wdict)
        except Exception as e: report[a["code"]]={"ok":False,"error":str(e)}
    with ThreadPoolExecutor(max_workers=n) as pool:
        list(as_completed([pool.submit(worker,a) for a in targets]))
    ok=sum(1 for v in report.values() if v.get("ok"))
    lines=[f"{time.time()-t0:.0f}s", f"OK lv{TARGET_LEVEL}: {ok}/{n}", ""]
    for c,v in report.items():
        lines.append(f"{c[-10:]} {'OK' if v.get('ok') else 'FAIL'} lv={v.get('level')} xp={v.get('xp')} g={v.get('games')}")
    box("BÁO CÁO", lines, C.CYN)

def feature_chat():
    rows=load_accounts()
    if not rows: log("Chưa có acc — [1] tạo trước", C.RED); return
    msg=safe_input(f"  {C.CYN}Nội dung{C.R}: ").strip()
    if not msg: return
    raw=safe_input(f"  {C.CYN}Số acc{C.R}: ").strip()
    try: n=int(raw) if raw else min(len(rows),MAX_PARALLEL)
    except ValueError: n=min(len(rows),MAX_PARALLEL)
    n=max(1,min(n,MAX_PARALLEL,len(rows)))
    targets=rows[:n]; stop=threading.Event(); stats={"sent":0,"fail":0}
    def _sig(*a): stop.set()
    old=signal.signal(signal.SIGINT,_sig)
    def worker(acc):
        tag=acc["code"][-8:]
        try: token=ensure_token(acc)
        except Exception: stats["fail"]+=1; return
        cl=StompClient(token)
        if not cl.connect(): stats["fail"]+=1; return
        cl.send("/app/chat/join",{"chatType":"JOIN"}); time.sleep(0.3)
        log(f"[{tag}] chat on", C.GRN)
        while not stop.is_set():
            try: cl.send("/app/chat",{"message":msg}); stats["sent"]+=1
            except Exception: stats["fail"]+=1
            time.sleep(CHAT_INTERVAL)
        cl.close()
    th=[threading.Thread(target=worker,args=(a,),daemon=True) for a in targets]
    for t in th: t.start(); time.sleep(0.08)
    try:
        while any(t.is_alive() for t in th) and not stop.is_set(): time.sleep(0.4)
    finally:
        stop.set(); signal.signal(signal.SIGINT,old)
        for t in th: t.join(timeout=2)
    box("CHAT", [f"sent={stats['sent']}", f"fail={stats['fail']}"], C.CYN)

def feature_list():
    rows=load_accounts()
    if not rows: log("Trống", C.YEL); return
    lines=[]
    for i,r in enumerate(rows,1):
        lv=int(r.get("level") or 0); col=C.GRN if lv>=TARGET_LEVEL else C.WHT
        lines.append(f"{i:2}. {col}{r['code']}{C.R} lv={lv} xp={r.get('xp')} {r.get('name','')}")
    box(f"LIST ({len(rows)})", lines, C.BLU)

def feature_report():
    rows=load_accounts()
    if not rows: log("Trống", C.YEL); return
    lv2=sum(1 for r in rows if int(r.get("level") or 0)>=TARGET_LEVEL)
    box("REPORT", [f"Tổng {len(rows)}", f"≥lv{TARGET_LEVEL} {lv2}", f"Còn cày {len(rows)-lv2}"], C.MAG)

def feature_supabase():
    global _sb_ok; _sb_ok=None
    if sb_check():
        n=len(sb_fetch_all()); box("SB", [f"OK {n} rows"], C.GRN)
        a=safe_input("  [c]push [d]pull Enter=skip: ").strip().lower()
        if a=="c":
            log(f"push {sum(1 for r in load_local() if sb_upsert(r))}", C.GRN)
        elif a=="d":
            save_local(_merge(load_local(), sb_fetch_all())); log("pulled", C.GRN)
    else:
        box("SB LỖI", ["Chạy setup_supabase.sql"], C.RED)

def feature_clear():
    if safe_input("  Xóa hết? (yes/N): ").strip().lower()!="yes": return
    for r in load_local(): sb_delete(r["code"])
    if os.path.isfile(ACCOUNTS_FILE): os.remove(ACCOUNTS_FILE)
    log("Đã xóa", C.YEL)

def main():
    attach_tty(); banner(); sb_check()
    while True:
        menu()
        c=safe_input(f"  {C.BOLD}Chọn{C.R} › ").strip(); print()
        if c=="1": feature_create()
        elif c=="2": feature_grind()
        elif c=="3": feature_chat()
        elif c=="4": feature_list()
        elif c=="5": feature_report()
        elif c=="6": feature_supabase()
        elif c=="7": feature_clear()
        elif c=="0": log("Bye", C.CYN); break
        else: log("?", C.YEL)
        print()

if __name__=="__main__":
    main()
