#!/usr/bin/env python3
"""Collect the outcomes of the pre-registered gap studies (study verdict + sceptic's audit) in one place.

  python3 tools/merge_studies.py <workflow-output.json> [...] [--print]

Input: result files of the pm-gap-studies workflow, whose `result` is a list of {key, title, study, audit}.
Writes studies/results.json (keyed by study). --print shows a compact summary of everything collected so far.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "studies" / "results.json"


def main() -> None:
    files = [a for a in sys.argv[1:] if not a.startswith("--")]
    res = json.loads(OUT.read_text()) if OUT.exists() else {}
    for f in files:
        d = json.loads(Path(f).read_text())
        for r in d.get("result") or []:
            res[r["key"]] = {"title": r.get("title"), "study": r.get("study"), "audit": r.get("audit")}
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(res, indent=1, ensure_ascii=False))
    print(f"studies collected: {len(res)}")
    if "--print" in sys.argv:
        for k, r in res.items():
            s, a = r.get("study") or {}, r.get("audit") or {}
            print(f"\n=== {k}: study says {s.get('verdict')}; audit says {a.get('verdict')}  (variants {s.get('variants_run')})")
            print(f"  {r.get('title')}")
            print(f"  headline: {s.get('headline')}")
            print(f"  numbers: {(s.get('key_numbers') or '')[:1500]}")
            print(f"  audit corrected: {(a.get('corrected_numbers') or '')[:900]}")
            for p in (a.get("problems") or [])[:6]:
                print(f"   - [{p.get('severity')}] {p.get('issue', '')[:300]} => {p.get('effect', '')[:200]}")
            print(f"  audit notes: {(a.get('notes') or '')[:700]}")
            if s.get("ideas"):
                print("  ideas: " + " | ".join(i[:160] for i in s["ideas"][:6]))


if __name__ == "__main__":
    main()
