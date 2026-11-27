"""Shared loader for the tech wallet study: 88 days of labelled fills + per-market books for the seven accounts."""
import sys, os, re, json, pickle, time, collections, datetime as dt
sys.path.insert(0, "/home/user/polymarket-lab")
from pmlab import wallet as W, gamma, dataapi, fees
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = "/home/user/polymarket-lab/data/tech_wallets"; os.makedirs(DATA, exist_ok=True)
END = 1795795200  # 2026-11-27 16:00 UTC
START = END - 88 * 86400
ACC = {
    "iutwpfal": "0xb89f5425341719d298dc2f5b9a92374f5fde1c44", "lamyk": "0xc004b035b67be284e0d1db56c39e865df6cac095",
    "KimchiCapital": "0x9578af80708f271f705e27867dcf6ec653acf066", "NoTeacher": "0xcb48f490d8579832e56954cb31dfee630d59be6d",
    "0xAee8611B": "0xaee811b7c7e5d961b545ac0e3f62f5f1cb181154", "fountaim": "0x4b72b21f7e9999d568d9b93f0be110257d9938d5",
    "melonmanm": "0x0787a58e205a70320db638113fe8da18c8800ca3",
}
TECH = {"tech", "ai", "big-tech", "openai", "technology", "artificial-intelligence", "spacex", "apple", "tesla", "nvidia", "elon-musk-ai", "gpt", "chatgpt"}
SUB = [("arena", r"arena|best-ai-model|ai-lab-end|best-chinese-ai|style-control|webdev|ai-company-end"), ("hle", r"hle-|frontiermath|benchmark|swe-bench|arc-agi"),
       ("openrouter", r"openrouter"), ("gpu", r"average-rental-price|rentable"), ("release", r"released|release|launch|announce.*product|on-the-free-plan"),
       ("ipo", r"ipo|valuation|raise-in"), ("jensen", r"jensen|nvidia"), ("millennium", r"millennium"), ("searched", r"searched"),
       ("mcap", r"largest-company|market-cap"), ("outage", r"go-down|outage|faa")]
def sub(slug, ev=""):
    s = f"{ev} {slug}"
    for n, p in SUB:
        if re.search(p, s): return n
    return "other"
def load(name):
    fp = f"{DATA}/{name}.pkl"
    if os.path.exists(fp): return pickle.load(open(fp, "rb"))
    d = W.analyse(ACC[name], START, END, max_fills=150000, verbose=False)
    conds = [m["condition"] for m in d["_markets"]]
    meta = gamma.markets_by_condition(conds)
    ev = {}
    for r in d["_fills"]: ev[r["condition_id"]] = r.get("event_slug") or r.get("slug")
    for m in d["_markets"]:
        md = meta.get(m["condition"]) or {}
        m["tags"] = gamma.tag_slugs(md); m["tech"] = bool(set(m["tags"]) & TECH); m["event"] = ev.get(m["condition"]) or m["slug"]
        m["sub"] = sub(m["slug"] or "", m["event"] or "") if m["tech"] else "non-tech"
        m["created"] = W._ts(md.get("createdAt")); m["vol"] = float(md.get("volumeNum") or 0); m["question"] = md.get("question")
        m["tokens"] = dict(zip(gamma.jfield(md.get("outcomes")) or [], gamma.jfield(md.get("clobTokenIds")) or []))
        m["uma"] = md.get("umaResolutionStatus")
    pickle.dump(d, open(fp, "wb")); return d
def meta_for(conds): return gamma.markets_by_condition(conds)
f = lambda t: dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%m-%d %H:%M") if t else "-"
fs = lambda t: dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%m-%d %H:%M:%S") if t else "-"
