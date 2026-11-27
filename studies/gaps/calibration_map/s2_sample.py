"""Step 2: universe (protocol: Universe 2-3, Families), per-family stratified sample, random fetch order."""
import collections
import json
import random
from datetime import datetime, timezone

from common import CAPS, DATA, OUT, P_END, P_START, SEED, classify, read_jsonl, ts, write_jsonl


def resolved_vec(op):
    try:
        v = [float(x) for x in op]
    except Exception:  # noqa
        return None
    if len(v) == 2 and tuple(v) in {(1.0, 0.0), (0.0, 1.0), (0.5, 0.5)}:
        return v
    return None


def main():
    seen = {}
    for p in sorted((DATA / "listing").glob("*.jsonl.gz")):
        for m in read_jsonl(p):
            seen[m["cid"]] = m
    drop = collections.Counter()
    uni = collections.defaultdict(list)
    for m in seen.values():
        if not (isinstance(m.get("outcomes"), list) and len(m["outcomes"]) == 2 and isinstance(m.get("tokens"), list)
                and len(m["tokens"]) == 2):
            drop["not_binary"] += 1
            continue
        fam, rate, anchor = classify(m)
        if fam is None:
            drop["updown-5m"] += 1
            continue
        if anchor is None or not (P_START <= anchor < P_END):
            drop["anchor_outside"] += 1
            continue
        w = resolved_vec(m.get("op"))
        if w is None:
            drop["not_resolved"] += 1
            continue
        m.update(fam=fam, rate=rate, anchor=anchor, win=w)
        uni[fam].append(m)
    rng = random.Random(SEED)
    sample = []
    summary = {"listed_unique": len(seen), "dropped": dict(drop), "families": {}}
    for fam in sorted(uni):
        rows = uni[fam]
        byday = collections.defaultdict(list)
        for m in rows:
            byday[int(m["anchor"] // 86400)].append(m)
        ndays = int((P_END - P_START) // 86400)
        quota = -(-CAPS[fam] // ndays)
        pick = []
        for d in sorted(byday):
            lst = sorted(byday[d], key=lambda x: x["cid"])
            rng.shuffle(lst)
            pick += lst[:quota]
        if len(pick) > CAPS[fam]:
            rng.shuffle(pick)
            pick = pick[:CAPS[fam]]
        wk = sum(1 for m in rows if datetime.fromtimestamp(m["anchor"], timezone.utc).weekday() >= 5)
        summary["families"][fam] = {"universe": len(rows), "per_day": round(len(rows) / ndays, 1),
                                    "weekend_share": round(wk / len(rows), 3), "sampled": len(pick)}
        sample += pick
    rng.shuffle(sample)
    write_jsonl(DATA / "sample.jsonl.gz", sample)
    json.dump(summary, open(OUT / "universe.json", "w"), indent=1)
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
