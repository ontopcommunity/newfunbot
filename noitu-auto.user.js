// ==UserScript==
// @name         Noitu.fun Auto Rank LV2 Multi-Acc
// @namespace    https://github.com/ontopcommunity/tuvungvn
// @version      3.0.0
// @description  Auto vào mode, cày nối từ đến LV2, xoay acc, tạo acc API, popup trạng thái
// @author       ontopcommunity
// @match        https://www.noitu.fun/*
// @match        https://noitu.fun/*
// @grant        none
// @run-at       document-idle
// ==/UserScript==

(async () => {
  "use strict";

  const API = "https://api.noitu.fun/api/v1";
  const DICT_URL = "https://raw.githubusercontent.com/ontopcommunity/tuvungvn/main/filtered_words.txt";
  const TARGET_LV = 2;
  const STORAGE_KEY = "noitu_bot_accounts_v3";
  const ACTIVE_KEY = "noitu_bot_active_code";
  const SUPABASE_URL = "https://tdlubyvugaucfexezhrk.supabase.co";
  const SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRkbHVieXZ1Z2F1Y2ZleGV6aHJrIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4Njc4NTcyMSwiZXhwIjoyMTAyMzYxNzIxfQ.7JkJVP9FzC51rZRwdKGL4IdY-m6ZGxyNoRE5WAGt2KU";
  const SB_TABLE = "noitu_accounts";

  // Mode card user specified
  const MODE_SEL =
    "div.main:nth-of-type(4) > div.main-center > div.page_mainContent__NQxPz:nth-of-type(1) > div.page_modeGridWrapper__J8Eq9:nth-of-type(3) > div.page_modeGrid__nPjbC > a.page_modeCard__bzgue.page_modeCoral__HD18C:nth-of-type(2)";
  const MODE_FALLBACKS = [
    MODE_SEL,
    "a.page_modeCard__bzgue.page_modeCoral__HD18C",
    "a[class*='modeCoral']",
    "a[class*='modeCard']",
  ];

  // ── state ──
  let dictionary = [];
  let byFirst = {};
  let usedAnswers = new Set();
  let currentTargetQuestion = "";
  let isProcessing = false;
  let running = true;
  let accounts = [];
  let activeCode = null;
  let statusMap = {}; // code -> { status, detail, level, xp }
  let modeEntered = false;

  // ── storage ──
  function loadAccounts() {
    try {
      accounts = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
    } catch {
      accounts = [];
    }
    activeCode = localStorage.getItem(ACTIVE_KEY) || (accounts[0] && accounts[0].code) || null;
    return accounts;
  }
  function saveAccounts() {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(accounts));
    if (activeCode) localStorage.setItem(ACTIVE_KEY, activeCode);
  }
  function upsertAcc(acc) {
    const i = accounts.findIndex((a) => a.code === acc.code);
    if (i >= 0) accounts[i] = { ...accounts[i], ...acc };
    else accounts.push(acc);
    saveAccounts();
    sbUpsert(acc);
    renderList();
  }
  function getActive() {
    return accounts.find((a) => a.code === activeCode) || accounts[0] || null;
  }
  function nextNeedGrind() {
    return accounts.find((a) => (parseInt(a.level) || 1) < TARGET_LV);
  }

  // ── Supabase (optional) ──
  async function sbUpsert(acc) {
    try {
      await fetch(`${SUPABASE_URL}/rest/v1/${SB_TABLE}?on_conflict=code`, {
        method: "POST",
        headers: {
          apikey: SUPABASE_KEY,
          Authorization: `Bearer ${SUPABASE_KEY}`,
          "Content-Type": "application/json",
          Prefer: "resolution=merge-duplicates,return=minimal",
        },
        body: JSON.stringify({
          code: acc.code,
          access_token: acc.accessToken,
          refresh_token: acc.refreshToken || "",
          name: acc.name || "",
          level: parseInt(acc.level) || 1,
          xp: parseInt(acc.xp) || 0,
          updated_at: new Date().toISOString(),
        }),
      });
    } catch {}
  }
  async function sbPull() {
    try {
      const r = await fetch(`${SUPABASE_URL}/rest/v1/${SB_TABLE}?select=*`, {
        headers: { apikey: SUPABASE_KEY, Authorization: `Bearer ${SUPABASE_KEY}` },
      });
      if (!r.ok) return;
      const rows = await r.json();
      for (const row of rows) {
        upsertAcc({
          code: row.code,
          accessToken: row.access_token,
          refreshToken: row.refresh_token,
          name: row.name,
          level: String(row.level ?? 1),
          xp: String(row.xp ?? 0),
        });
      }
      setGlobal("Đã pull Supabase: " + rows.length + " acc");
    } catch (e) {
      setGlobal("Pull SB lỗi: " + e.message);
    }
  }

  // ── API ──
  function hdr(token) {
    const h = {
      Origin: location.origin,
      Referer: location.href,
      "Content-Type": "application/json",
      Accept: "application/json",
    };
    if (token) h.Authorization = "Bearer " + token;
    return h;
  }
  async function apiCreate() {
    const r = await fetch(API + "/user/init", {
      method: "POST",
      headers: hdr(),
      body: JSON.stringify({ id: null, code: null }),
    });
    if (!r.ok) throw new Error("init " + r.status);
    return r.json();
  }
  async function apiGetUser(code, token) {
    const r = await fetch(API + "/user/get?code=" + encodeURIComponent(code), {
      headers: hdr(token),
    });
    if (!r.ok) throw new Error("get " + r.status);
    return r.json();
  }
  async function apiRefresh(refresh) {
    const r = await fetch(API + "/auth/refresh", {
      method: "POST",
      headers: hdr(),
      body: JSON.stringify({ refreshToken: refresh }),
    });
    if (!r.ok) throw new Error("refresh " + r.status);
    return r.json();
  }

  async function ensureToken(acc) {
    try {
      const u = await apiGetUser(acc.code, acc.accessToken);
      acc.level = String(u.level ?? acc.level);
      acc.xp = String(u.experiencePoints ?? acc.xp);
      upsertAcc(acc);
      return acc.accessToken;
    } catch {
      const d = await apiRefresh(acc.refreshToken);
      acc.accessToken = d.accessToken;
      if (d.refreshToken) acc.refreshToken = d.refreshToken;
      upsertAcc(acc);
      return acc.accessToken;
    }
  }

  async function refreshProgress(acc) {
    try {
      const tok = await ensureToken(acc);
      const u = await apiGetUser(acc.code, tok);
      acc.level = String(u.level ?? 1);
      acc.xp = String(u.experiencePoints ?? 0);
      acc.name = u.name || acc.name;
      upsertAcc(acc);
      setStatus(acc.code, {
        level: acc.level,
        xp: acc.xp,
        status: parseInt(acc.level) >= TARGET_LV ? "done" : statusMap[acc.code]?.status || "idle",
      });
      return u;
    } catch (e) {
      setStatus(acc.code, { status: "error", detail: e.message });
      return null;
    }
  }

  // Apply tokens into page storage so SPA uses this account
  function applyTokensToPage(acc) {
    const keys = [
      "accessToken",
      "token",
      "noitu_access_token",
      "authToken",
      "access_token",
      "refreshToken",
      "refresh_token",
      "userCode",
      "code",
    ];
    try {
      localStorage.setItem("accessToken", acc.accessToken);
      localStorage.setItem("token", acc.accessToken);
      localStorage.setItem("refreshToken", acc.refreshToken || "");
      localStorage.setItem("userCode", acc.code);
      localStorage.setItem("code", acc.code);
      sessionStorage.setItem("accessToken", acc.accessToken);
      sessionStorage.setItem("userCode", acc.code);
    } catch {}
    // Patch fetch Authorization for API calls
    if (!window.__noituFetchPatched) {
      window.__noituFetchPatched = true;
      const orig = window.fetch;
      window.fetch = function (input, init) {
        try {
          const url = typeof input === "string" ? input : input && input.url;
          if (url && url.includes("api.noitu.fun") && activeCode) {
            const a = getActive();
            if (a && a.accessToken) {
              init = init || {};
              const headers = new Headers(init.headers || {});
              headers.set("Authorization", "Bearer " + a.accessToken);
              init = { ...init, headers };
            }
          }
        } catch {}
        return orig.call(this, input, init);
      };
    }
  }

  async function switchAccount(acc) {
    activeCode = acc.code;
    saveAccounts();
    applyTokensToPage(acc);
    setStatus(acc.code, { status: "active", detail: "đang cày" });
    setGlobal("Chuyển acc: " + (acc.name || acc.code).slice(0, 20));
    modeEntered = false;
    usedAnswers.clear();
    currentTargetQuestion = "";
    // soft navigate home then mode
    try {
      if (!location.pathname.includes("/rank") && !location.pathname.includes("/word")) {
        // stay
      }
    } catch {}
    await sleep(500);
    await enterMode();
  }

  // ── DOM helpers ──
  function sleep(ms) {
    return new Promise((r) => setTimeout(r, ms));
  }
  function triggerEvent(el, type, Ctor, extra) {
    try {
      const ev = new Ctor(type, { bubbles: true, cancelable: true, view: window, ...extra });
      el.dispatchEvent(ev);
    } catch {}
  }
  function hardClick(el) {
    if (!el) return;
    ["pointerover", "pointerenter", "pointerdown", "pointerup"].forEach((t) =>
      triggerEvent(el, t, PointerEvent)
    );
    ["mouseover", "mouseenter", "mousemove", "mousedown", "mouseup", "click"].forEach((t) =>
      triggerEvent(el, t, MouseEvent)
    );
    try {
      el.click();
    } catch {}
    try {
      HTMLElement.prototype.click.call(el);
    } catch {}
  }

  async function enterMode() {
    for (const sel of MODE_FALLBACKS) {
      const el = document.querySelector(sel);
      if (el) {
        hardClick(el);
        modeEntered = true;
        setGlobal("Đã vào mode card");
        await sleep(800);
        // click random ranked / play buttons if present
        clickRandomPlayButtons();
        return true;
      }
    }
    // try text match Nối Từ
    const all = [...document.querySelectorAll("a, button, div[role=button], [class*=modeCard], [class*=rank]")];
    const t = all.find((e) => {
      const s = (e.innerText || "").trim();
      return s.includes("Nối Từ") && !s.includes("Mở Rộng") && s.length < 80;
    });
    if (t) {
      hardClick(t);
      modeEntered = true;
      setGlobal("Đã vào Nối Từ (text)");
      await sleep(800);
      clickRandomPlayButtons();
      return true;
    }
    setGlobal("Chưa thấy mode card — chờ DOM…");
    return false;
  }

  function clickRandomPlayButtons() {
    const candidates = [
      ...document.querySelectorAll(
        "button, a, [class*=rankedBtn], [class*=rankCard], [class*=WORD_LINK], [class*=play], [class*=start]"
      ),
    ].filter((e) => {
      const s = (e.innerText || e.getAttribute("title") || "").trim();
      return s.length > 0 && s.length < 60;
    });
    if (!candidates.length) return;
    const pick = candidates[Math.floor(Math.random() * Math.min(candidates.length, 8))];
    hardClick(pick);
  }

  // ── dictionary ──
  async function loadDict() {
    try {
      const r = await fetch(DICT_URL, { cache: "no-store" });
      const text = await r.text();
      dictionary = text
        .split("\n")
        .map((l) => l.trim().toLowerCase())
        .filter((w) => w && w.includes(" "));
      byFirst = {};
      for (const w of dictionary) {
        const f = w.split(/\s+/)[0];
        (byFirst[f] || (byFirst[f] = [])).push(w);
      }
      setGlobal("Từ điển: " + dictionary.length);
    } catch (e) {
      setGlobal("Dict lỗi: " + e.message);
    }
  }

  async function fetchApiSuggestions(q) {
    try {
      const r = await fetch(
        "https://dictionaryvip.vercel.app/api/v1/suggest?q=" + encodeURIComponent(q)
      );
      const j = await r.json();
      return Array.isArray(j) ? j.map((x) => String(x).toLowerCase()) : [];
    } catch {
      return [];
    }
  }

  // ── auto answer (tool.js core, no tiktok) ──
  async function processQuestion() {
    if (!running || isProcessing) return;
    isProcessing = true;
    try {
      if (!modeEntered) {
        await enterMode();
      }

      // Word-link classic
      const wordElement = document.querySelector(
        "a.word-detail_wordDetailWord__1DYml, [class*='wordDetailWord']"
      );
      const inputElement = document.querySelector(
        "input.word-link-answer-input_input__L6PK2, input[class*='word-link-answer-input']"
      );
      const svgElement = document.querySelector("svg.lucide-send, svg.lucide.lucide-send");

      if (wordElement && inputElement) {
        const currentQuestion = (wordElement.textContent || "").trim();
        if (currentQuestion) {
          if (currentQuestion !== currentTargetQuestion) {
            currentTargetQuestion = currentQuestion;
            usedAnswers.clear();
          }
          const lastWord = currentQuestion.split(/\s+/).pop().toLowerCase();
          let available = (byFirst[lastWord] || []).filter((a) => !usedAnswers.has(a));
          if (!available.length) {
            const apiRes = await fetchApiSuggestions(lastWord);
            available = apiRes.filter((phrase) => {
              const pw = phrase.toLowerCase().split(/\s+/);
              return pw[0] === lastWord && !usedAnswers.has(phrase);
            });
          }
          if (available.length) {
            const ans = available[Math.floor(Math.random() * available.length)];
            usedAnswers.add(ans);
            inputElement.focus();
            const setter = Object.getOwnPropertyDescriptor(
              window.HTMLInputElement.prototype,
              "value"
            ).set;
            setter.call(inputElement, ans);
            inputElement.dispatchEvent(new Event("input", { bubbles: true }));
            inputElement.dispatchEvent(new Event("change", { bubbles: true }));
            const btn = svgElement ? svgElement.closest("button") : null;
            if (btn) hardClick(btn);
            else {
              inputElement.dispatchEvent(
                new KeyboardEvent("keydown", { key: "Enter", bubbles: true, keyCode: 13 })
              );
            }
            const acc = getActive();
            if (acc) setStatus(acc.code, { status: "play", detail: ans.slice(0, 24) });
          }
        }
      }

      // Ranked lobby cards — keep clicking join-ish
      const lobby = document.querySelector(
        "[class*='rankedBtnWORD_LINK'], [class*='multiple-mode-lobby_rankedBtnWORD_LINK']"
      );
      if (lobby) hardClick(lobby);
    } catch (e) {
      /* ignore */
    }
    isProcessing = false;
  }

  // ── level loop: switch acc when done ──
  async function levelWatchLoop() {
    while (running) {
      const acc = getActive();
      if (!acc) {
        setGlobal("Chưa có acc — bấm Tạo acc");
        await sleep(3000);
        continue;
      }
      await refreshProgress(acc);
      const lv = parseInt(acc.level) || 1;
      if (lv >= TARGET_LV) {
        setStatus(acc.code, { status: "done", detail: "lv" + lv });
        const next = nextNeedGrind();
        if (next && next.code !== acc.code) {
          await switchAccount(next);
        } else if (!next) {
          setGlobal("Tất cả acc ≥ lv" + TARGET_LV + " ✓");
          running = false;
          break;
        }
      }
      await sleep(12000);
    }
  }

  // ── UI ──
  function setGlobal(msg) {
    const el = document.getElementById("nbt-global");
    if (el) el.textContent = msg;
  }
  function setStatus(code, patch) {
    statusMap[code] = { ...(statusMap[code] || {}), ...patch };
    renderList();
  }

  function renderList() {
    const box = document.getElementById("nbt-list");
    if (!box) return;
    const rows = accounts
      .map((a) => {
        const st = statusMap[a.code] || {};
        const lv = st.level || a.level || "?";
        const xp = st.xp || a.xp || "0";
        const status = st.status || "idle";
        const detail = st.detail || "";
        const active = a.code === activeCode;
        const done = parseInt(lv) >= TARGET_LV;
        const color = done ? "#0f0" : active ? "#0ff" : status === "error" ? "#f66" : "#ccc";
        return `<div class="nbt-row" data-code="${a.code}" style="
          padding:6px 8px;border-bottom:1px solid #333;cursor:pointer;
          background:${active ? "#1a2a3a" : "transparent"};color:${color};font-size:12px;
        ">
          <b>${(a.name || a.code).slice(0, 18)}</b>
          <span style="float:right">lv${lv} xp${xp}</span>
          <div style="opacity:.85;font-size:11px">${status} ${detail}</div>
        </div>`;
      })
      .join("");
    box.innerHTML =
      rows ||
      '<div style="padding:12px;color:#888;text-align:center">Chưa có acc</div>';
    box.querySelectorAll(".nbt-row").forEach((el) => {
      el.onclick = () => {
        const a = accounts.find((x) => x.code === el.dataset.code);
        if (a) switchAccount(a);
      };
    });
  }

  function buildUI() {
    const old = document.getElementById("noitu-bot-panel");
    if (old) old.remove();

    const style = document.createElement("style");
    style.textContent = `
      #noitu-bot-panel {
        position: fixed; top: 12px; right: 12px; width: 300px; max-height: 85vh;
        z-index: 2147483647; background: rgba(12,12,18,.96); color: #eee;
        font-family: ui-sans-serif, system-ui, sans-serif; border-radius: 12px;
        border: 1px solid #333; box-shadow: 0 8px 32px rgba(0,0,0,.5);
        display: flex; flex-direction: column; overflow: hidden;
      }
      #noitu-bot-panel .nbt-head {
        padding: 10px 14px; background: linear-gradient(90deg,#0ff3,#f0f3);
        color: #0ff; font-weight: 700; font-size: 13px; cursor: move;
        border-bottom: 1px solid #333;
      }
      #noitu-bot-panel .nbt-btns { display: flex; flex-wrap: wrap; gap: 6px; padding: 8px; }
      #noitu-bot-panel button {
        flex: 1; min-width: 70px; padding: 6px 8px; border: 0; border-radius: 6px;
        background: #222; color: #0ff; cursor: pointer; font-size: 11px;
      }
      #noitu-bot-panel button:hover { background: #333; }
      #noitu-bot-panel #nbt-list {
        overflow-y: auto; max-height: 50vh; border-top: 1px solid #333;
      }
      #nbt-global { padding: 6px 10px; font-size: 11px; color: #8f8; border-top: 1px solid #333; }
    `;
    document.head.appendChild(style);

    const panel = document.createElement("div");
    panel.id = "noitu-bot-panel";
    panel.innerHTML = `
      <div class="nbt-head">⚡ Noitu Auto · LV${TARGET_LV} Multi-Acc</div>
      <div class="nbt-btns">
        <button id="nbt-create">+ Tạo acc</button>
        <button id="nbt-pull">Pull DB</button>
        <button id="nbt-toggle">Tạm dừng</button>
        <button id="nbt-mode">Vào mode</button>
      </div>
      <div id="nbt-list"></div>
      <div id="nbt-global">Khởi động…</div>
    `;
    document.body.appendChild(panel);

    // drag
    const head = panel.querySelector(".nbt-head");
    let ox = 0,
      oy = 0,
      dragging = false;
    head.onmousedown = (e) => {
      dragging = true;
      ox = e.clientX - panel.getBoundingClientRect().left;
      oy = e.clientY - panel.getBoundingClientRect().top;
    };
    document.onmousemove = (e) => {
      if (!dragging) return;
      panel.style.right = "auto";
      panel.style.left = e.clientX - ox + "px";
      panel.style.top = e.clientY - oy + "px";
    };
    document.onmouseup = () => {
      dragging = false;
    };

    document.getElementById("nbt-create").onclick = async () => {
      try {
        setGlobal("Đang tạo acc…");
        const d = await apiCreate();
        const acc = {
          code: d.code,
          accessToken: d.accessToken,
          refreshToken: d.refreshToken,
          name: d.name || "",
          level: String(d.level || 1),
          xp: "0",
        };
        upsertAcc(acc);
        setStatus(acc.code, { status: "new", level: acc.level, xp: "0" });
        setGlobal("Tạo OK: " + acc.code.slice(-12));
        if (!getActive() || (parseInt(getActive().level) || 1) >= TARGET_LV) {
          await switchAccount(acc);
        }
      } catch (e) {
        setGlobal("Tạo lỗi: " + e.message);
      }
    };
    document.getElementById("nbt-pull").onclick = () => sbPull();
    document.getElementById("nbt-toggle").onclick = (ev) => {
      running = !running;
      ev.target.textContent = running ? "Tạm dừng" : "Chạy tiếp";
      setGlobal(running ? "Đang chạy" : "Đã tạm dừng");
    };
    document.getElementById("nbt-mode").onclick = () => enterMode();

    renderList();
  }

  // ── bootstrap ──
  loadAccounts();
  buildUI();
  await loadDict();

  // Capture current session if any token visible
  try {
    const t =
      localStorage.getItem("accessToken") ||
      localStorage.getItem("token") ||
      sessionStorage.getItem("accessToken");
    // optional: leave as is
  } catch {}

  if (!accounts.length) {
    try {
      setGlobal("Tạo acc đầu…");
      const d = await apiCreate();
      upsertAcc({
        code: d.code,
        accessToken: d.accessToken,
        refreshToken: d.refreshToken,
        name: d.name || "",
        level: String(d.level || 1),
        xp: "0",
      });
      activeCode = d.code;
      saveAccounts();
    } catch (e) {
      setGlobal("Cần bấm + Tạo acc (" + e.message + ")");
    }
  }

  const start = getActive() || nextNeedGrind() || accounts[0];
  if (start) {
    await switchAccount(start);
  }

  // Auto loops — no button needed
  setInterval(() => {
    if (running) processQuestion();
  }, 60);
  const obs = new MutationObserver(() => {
    if (running) processQuestion();
  });
  obs.observe(document.body, { childList: true, subtree: true });

  // Re-enter mode periodically if lost
  setInterval(() => {
    if (running && !document.querySelector("input[class*='word-link-answer'], a[class*='wordDetailWord']")) {
      modeEntered = false;
    }
  }, 5000);

  levelWatchLoop();
  setGlobal("Auto ON — cày đến lv" + TARGET_LV + " rồi xoay acc");
})();
