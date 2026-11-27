#!/usr/bin/env python3
"""Merge the candidate lists returned by the discovery workflows into one catalog.

  python3 tools/merge_catalog.py <workflow-output.json> [...]  [--print [KEY]]

Each input is a workflow result file whose `result` is a list of
{key, title, raw_file, leads, coverage, verified: {candidates, dropped, notes}}.
Writes catalog/candidates.json (all verified candidates with their channel key), catalog/leads.json and
catalog/channels.json (coverage and verifier notes per channel); re-running with more files replaces channels
by key. --print shows a compact table (optionally one channel).
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CAT = ROOT / "catalog"


def load(path: Path, default):
    return json.loads(path.read_text()) if path.exists() else default


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    show = "--print" in sys.argv
    only = None
    if show:
        i = sys.argv.index("--print")
        if i + 1 < len(sys.argv) and not sys.argv[i + 1].endswith(".output") and not sys.argv[i + 1].endswith(".json"):
            only = sys.argv[i + 1]
            args = [a for a in args if a != only]
    cands = load(CAT / "candidates.json", [])
    leads = load(CAT / "leads.json", [])
    chans = load(CAT / "channels.json", {})
    for f in args:
        d = json.loads(Path(f).read_text())
        for ch in d.get("result") or []:
            key = ch["key"]
            cands = [c for c in cands if c.get("channel") != key]
            leads = [x for x in leads if x.get("channel") != key]
            v = ch.get("verified") or {}
            for c in v.get("candidates") or []:
                c["channel"] = key
                cands.append(c)
            for x in ch.get("leads") or []:
                leads.append({**x, "channel": key})
            chans[key] = {"title": ch.get("title"), "raw_file": ch.get("raw_file"), "coverage": ch.get("coverage"),
                          "found": ch.get("found_count"), "kept": len(v.get("candidates") or []),
                          "dropped": v.get("dropped") or [], "verifier_notes": v.get("notes")}
    CAT.mkdir(exist_ok=True)
    (CAT / "candidates.json").write_text(json.dumps(cands, indent=1, ensure_ascii=False))
    (CAT / "leads.json").write_text(json.dumps(leads, indent=1, ensure_ascii=False))
    (CAT / "channels.json").write_text(json.dumps(chans, indent=1, ensure_ascii=False))
    print(f"catalog: {len(cands)} candidates from {len(chans)} channels, {len(leads)} leads")
    if show:
        rows = [c for c in cands if not only or c.get("channel") == only]
        rows.sort(key=lambda c: (-int(c.get("credibility") or 0), c.get("family") or ""))
        for c in rows:
            ver = (c.get("verification") or "NOT CHECKED").split()[0].strip(":,.")
            print(f"\n[{c.get('credibility')}] {c.get('family')} | {c.get('name')}  ({c.get('channel')}; {ver})")
            print(f"    how: {(c.get('mechanism') or '')[:420]}")
            if c.get("time_gap"):
                print(f"    gap: {c['time_gap'][:220]}")
            if c.get("evidence"):
                print(f"    evidence: {c['evidence'][:520]}")
            if c.get("fee_sensitivity"):
                print(f"    fees: {c['fee_sensitivity'][:220]}")
            if c.get("red_flags"):
                print(f"    flags: {c['red_flags'][:260]}")
            if c.get("wallets"):
                print(f"    wallets: {', '.join(c['wallets'][:6])}")


if __name__ == "__main__":
    main()
