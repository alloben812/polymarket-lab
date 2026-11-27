"""Step 4b: keyword pre-label for the scheduled / unscheduled split. Output is a draft; the final labels are written by
hand into out/labels.csv after reading every row (protocol section 4), before s6_rule.py is run."""
import csv, json, re
from common import *

SCHED_Q = re.compile(r"\b(win|wins|won|election|elections|seats|votes|vote share|runoff|referendum|primary|nominee|"
                     r"debate|nobel|prize|award|fed|rate cut|rate hike|interest rate|cpi|inflation|gdp|jobs|court|ruling|verdict|"
                     r"sentenced|convicted|confirm|confirmed|vote on|pass|passes|bill|resolution|speech|address|summit|"
                     r"budget|shutdown|approval|poll|polling)\b", re.I)


def main():
    jumps = [j for j in json.load(open(OUT / "jumps.json")) if j["status"] in ("main", "R")]
    with open(OUT / "labels_draft.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["c", "t0", "t0_iso", "status", "cat", "dir", "pf_pre", "p10", "end_minus_t0_h", "hint", "question", "event"])
        for j in jumps:
            end = parse_time(j.get("endDate"))
            dh = None if end is None else round((end - j["t0"]) / 3600, 1)
            hint = []
            if j["cat"] == "elections":
                hint.append("elections-tag")
            if SCHED_Q.search(j["question"] or ""):
                hint.append("kw:" + SCHED_Q.search(j["question"]).group(0).lower())
            if dh is not None and -30 <= dh <= 30:
                hint.append("near-deadline")
            w.writerow([j["c"], j["t0"], j["t0_iso"], j["status"], j["cat"], "YES" if j["dir"] > 0 else "NO", j["pf_pre"], j["p10"], dh,
                        "|".join(hint), j["question"], j["event"]])
    print("rows", len(jumps))


if __name__ == "__main__":
    main()
