"""Fetch Taiwan-election prediction-market prices from Polymarket and Kalshi into data/markets.json."""
import json, os, urllib.request, urllib.parse, datetime

UA = {"User-Agent": "lx-term-markets/1.0", "Accept": "application/json"}
EN = {"chiang wan-an": "蒋万安", "puma shen": "沈伯洋", "shen pao-yang": "沈伯洋", "lee shu-chuan": "李四川",
      "lee shih-chuan": "李四川", "su chiao-hui": "苏巧慧", "johnny chiang": "江启臣", "chiang chi-chen": "江启臣",
      "ho hsin-chun": "何欣纯", "ko chih-en": "柯志恩", "lai jui-lung": "赖瑞隆",
      "shen bo-yang": "沈伯洋", "zhang jing": "张静", "chang ching": "张静"}
PM_Q = {"party": "Taiwanese Local Elections: Party Winner", "tpe": "Taipei Mayor Election Winner",
        "ntp": "New Taipei Mayor Election Winner", "txg": "Taichung Mayor Election Winner",
        "khh": "Kaohsiung Mayor Election Winner"}
KS_SERIES = {"tpe": ["KXTAIPEIMAYOR"], "ntp": ["KXNEWTAIPEIMAYOR"], "txg": ["KXTAICHUNGMAYOR"],
             "khh": ["KXKAOHSIUNGMAYOR"], "party": ["KXTAIWANLOCAL", "KXTAIWANLOCALELECTION"]}

def get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))

def cn(s):
    s = str(s or "").strip(); l = s.lower()
    if l in EN: return EN[l]
    if "kmt" in l or "kuomintang" in l: return "国民党"
    if "dpp" in l or "democratic progressive" in l: return "民进党"
    if "tpp" in l or "people's party" in l or "people’s party" in l: return "民众党"
    return s

def fmt_vol(v):
    try: v = float(v)
    except Exception: return ""
    return f"{v/1000:.1f}K" if v >= 1000 else str(int(v))

def polymarket(errs):
    out = {}
    for mid, q in PM_Q.items():
        try:
            j = get("https://gamma-api.polymarket.com/public-search?" + urllib.parse.urlencode({"q": q, "limit_per_type": 8}))
            evs = j.get("events") or []
            def ok(e):
                t = str(e.get("title", "")).lower()
                return ("party winner" in t and "taiwan" in t) if mid == "party" else t.startswith(q.lower())
            ev = next((e for e in evs if ok(e)), None)
            if not ev: errs.append(f"pm:{mid}:no-event"); continue
            rows = []
            for m in ev.get("markets") or []:
                try: p = float(json.loads(m.get("outcomePrices") or "[]")[0])
                except Exception: continue
                name = str(m.get("groupItemTitle") or "")
                if __import__("re").match(r"^(candidate|person|option|other)\s*[a-z0-9]?$", name.strip().lower()): continue
                if p > 0: rows.append({"n": cn(m.get("groupItemTitle") or m.get("question")), "p": round(p * 100, 1)})
            rows.sort(key=lambda x: -x["p"])
            if rows: out[mid] = {"top": rows[:3], "vol": fmt_vol(ev.get("volume")), "url": "https://polymarket.com/event/" + str(ev.get("slug", ""))}
        except Exception as e:
            errs.append(f"pm:{mid}:{type(e).__name__}:{e}"[:160])
    return out

def kalshi_price(m):
    for k in ("last_price_dollars", "yes_bid_dollars"):
        if m.get(k) not in (None, ""):
            try: return round(float(m[k]) * 100, 1)
            except Exception: pass
    for k in ("last_price", "yes_bid"):
        if isinstance(m.get(k), (int, float)) and m[k] > 0: return float(m[k])
    return None

def kalshi(errs):
    out = {}
    for mid, series in KS_SERIES.items():
        for s in series:
            try:
                j = get("https://api.elections.kalshi.com/trade-api/v2/markets?" + urllib.parse.urlencode({"series_ticker": s, "limit": 50}))
                ms = [m for m in (j.get("markets") or []) if m.get("status") in (None, "active", "open", "initialized")] or (j.get("markets") or [])
                rows, vol = [], 0
                for m in ms:
                    p = kalshi_price(m)
                    vol += float(m.get("volume_fp") or m.get("volume") or 0)
                    if p: rows.append({"n": cn(m.get("yes_sub_title") or m.get("subtitle") or m.get("title")), "p": p})
                rows.sort(key=lambda x: -x["p"])
                if rows:
                    out[mid] = {"top": rows[:3], "vol": fmt_vol(vol), "url": "https://kalshi.com/markets/" + s.lower()}
                    break
                errs.append(f"ks:{mid}:{s}:empty")
            except Exception as e:
                errs.append(f"ks:{mid}:{s}:{type(e).__name__}:{e}"[:160])
    return out

def main():
    errs = []
    res = {"ts": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "pm": polymarket(errs), "ks": kalshi(errs), "err": errs}
    path = os.path.join(os.path.dirname(__file__), "..", "data", "markets.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    old = {}
    if os.path.exists(path):
        try: old = json.load(open(path, encoding="utf-8"))
        except Exception: old = {}
    for k in ("pm", "ks"):  # keep last good values if a source failed this round
        for mid, v in (old.get(k) or {}).items():
            res[k].setdefault(mid, dict(v, stale=True))
    json.dump(res, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({"pm": list(res["pm"]), "ks": list(res["ks"]), "err": errs}, ensure_ascii=False))

if __name__ == "__main__":
    main()
