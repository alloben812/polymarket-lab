"""Print the rules text of the most traded tech event types (one market per event prefix) for the studied accounts."""
import re, collections
from common import *
seen = {}; tot = collections.Counter()
for name in ACC:
    for m in load(name)["_markets"]:
        if not m["tech"] or m["sub"] in ("jensen", "ipo"): continue
        key = re.sub(r"\d{6,}.*$|-(january|february|march|april|may|june|july|august|september|october|november|december).*$|-\d+$", "", m["event"] or "")
        key = re.sub(r"(gpt|claude|gemini|grok|kimi|qwen|deepseek|fable|astra|carbon|hydrogen|terra|opus|sonnet|llama|mistral)[a-z0-9-]*?-(?=text-arena|hle|released|code-arena|arena)", "X-", key)
        tot[key] += m["turnover"]; seen.setdefault(key, m)
conds = [seen[k]["condition"] for k, _ in tot.most_common(14)]
meta = meta_for(conds)
for k, v in tot.most_common(40):
    print(f"{v:9.0f} {k}")
for k, v in tot.most_common(14):
    m = seen[k]; md = meta.get(m["condition"], {})
    print(f"\n### {k}  ({v:.0f} usd over the 7 accounts)\n  slug {m['slug']} | event {m['event']} | q: {md.get('question')}\n  created {md.get('createdAt')} start {md.get('startDate')} end {md.get('endDate')} closed {md.get('closedTime')} uma {md.get('umaResolutionStatus')} negRisk {md.get('negRisk')} vol {md.get('volumeNum')} fee {md.get('feeSchedule')} src {md.get('resolutionSource')}")
    print("  " + (md.get("description") or "").replace("\n", " ")[:1100])
