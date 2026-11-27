"""Step 4c: frozen scheduled/unscheduled labels (protocol section 4), written by hand after reading each confirmed
jump's question, event, category, direction, date and distance to the market's end date (labels_draft.csv).
Codes: U = unscheduled; S = scheduled; D = doubtful -> scheduled with doubt=1. Reasons in short. Keyed by the
row's (slug prefix, t0_iso) so the reading stays attached to the jump. Run once; writes out/labels.csv."""
import csv, sys
from common import OUT

# (t0_iso[:16], question prefix) -> (code, reason)
READ = {
 ("2026-09-01 11:01", "Will Trump praise Bryson"): ("D", "YES after the month ended: late confirmation/resolution"),
 ("2026-09-02 21:35", "Will Donald Trump publicly insult someone on September 3"): ("D", "jump before the counted day starts"),
 ("2026-09-04 03:26", "Will Donald Trump publicly insult someone on September 3"): ("S", "own deadline expiry"),
 ("2026-09-04 05:51", "Will Kim Ahern"): ("U", "4 days before the primary: candidate news"),
 ("2026-09-06 16:00", "Will the AfD win the 2026 Sachsen-Anhalt"): ("S", "election count"),
 ("2026-09-06 18:14", "Will SPD win at least 9%"): ("S", "election count"),
 ("2026-09-07 16:46", "Russia x Ukraine ceasefire agreement"): ("U", ""),
 ("2026-09-10 18:32", "Israel x Iran ceasefire continues through September 15"): ("U", ""),
 ("2026-09-13 18:02", "Will the Moderate Party"): ("S", "election count"),
 ("2026-09-13 18:02", "Will the Sweden Democrats (SD) win the second"): ("S", "election count"),
 ("2026-09-13 18:02", "Will the Sweden Democrats (SD) win the third"): ("S", "election count"),
 ("2026-09-14 21:02", "US x China agree to pace"): ("U", ""),
 ("2026-09-16 05:42", "Moscow air traffic suspended"): ("D", "YES after the deadline: late confirmation"),
 ("2026-09-18 21:11", "Trump x Greenland deal"): ("U", ""),
 ("2026-09-20 17:18", "Mecklenburg-Vorpommern Parliamentary Election"): ("S", "election count"),
 ("2026-09-20 17:20", "Will AfD win at least 38%"): ("S", "election count"),
 ("2026-09-21 22:53", "Will the US announce a diesel export ban"): ("U", ""),
 ("2026-09-22 09:57", "Saudi Oil Pipeline (East-West) restarts by September 30"): ("U", ""),
 ("2026-09-22 17:53", "Will the next diplomatic US-Iran meeting"): ("U", ""),
 ("2026-09-22 19:50", "Republican House odds dip"): ("D", "market on another market's odds"),
 ("2026-09-23 02:17", "Jon Ossoff Democratic nomination odds"): ("D", "market on another market's odds"),
 ("2026-09-23 16:51", "Will the US announce a diesel export ban"): ("U", ""),
 ("2026-09-23 19:03", "Will Mamdani freeze NYC rents"): ("U", ""),
 ("2026-09-23 22:57", "Will Russia capture Bilytske"): ("U", ""),
 ("2026-09-27 02:37", "Will Russia enter Malokaterynivka"): ("U", ""),
 ("2026-09-29 14:34", "Trump renames AI"): ("U", ""),
 ("2026-09-30 20:30", "Will Trump meet with Javier Milei in September"): ("D", "7 h before own deadline; meeting may be scheduled"),
 ("2026-10-01 13:44", "Will no next Israeli Minister of National Security"): ("U", ""),
 ("2026-10-01 16:17", "Houthi military action against Saudi Arabia on September 29"): ("D", "after the day: late confirmation"),
 ("2026-10-01 22:28", "Flávio Bolsonaro participates in debate"): ("S", "scheduled debate settles the market"),
 ("2026-10-02 03:24", "Will Mohammed bin Abdulrahman"): ("U", ""),
 ("2026-10-03 15:02", "US x Iran ceasefire continues through October 9"): ("U", ""),
 ("2026-10-04 23:58", "Will Iran target Iraq by September 30"): ("D", "after the deadline date in the question"),
 ("2026-10-06 09:06", "Saudi Oil Pipeline (East-West) restarts by October 15"): ("U", ""),
 ("2026-10-06 09:06", "Saudi Oil Pipeline (East-West) restarts by October 31"): ("U", ""),
 ("2026-10-11 17:00", "Will there be a Hormuz agreement and the Republicans"): ("D", "combo leg, jumps on the hour in several combos"),
 ("2026-10-11 17:00", "Will there be no Hormuz agreement"): ("D", "combo leg, jumps on the hour in several combos"),
 ("2026-10-11 17:10", "Will oil be below $80 on November 2 and the Republicans"): ("D", "combo leg"),
 ("2026-10-11 18:10", "Will there be a Hormuz agreement and the Republicans"): ("D", "combo leg"),
 ("2026-10-11 18:10", "Will there be no Hormuz agreement"): ("D", "combo leg"),
 ("2026-10-12 19:17", "Will there be a Hormuz agreement by October 23, oil below $80, and the Republicans"): ("D", "combo leg"),
 ("2026-10-12 19:20", "Will there be a Hormuz agreement by October 23, oil below $80, and the Democrats"): ("D", "combo leg"),
 ("2026-10-13 02:53", "Will Russia target Kyiv on October 17"): ("U", ""),
 ("2026-10-13 02:55", "Will Russia target Kyiv on October 16"): ("U", ""),
 ("2026-10-13 02:57", "Will Russia target Kyiv on October 20"): ("U", ""),
 ("2026-10-13 15:16", "Katie Zacharia out as Press Secretary by October 31"): ("U", ""),
 ("2026-10-14 06:11", "Saudi Arabia military action against Yemen on October 8"): ("D", "after the day: late resolution"),
 ("2026-10-15 15:02", "Will Aleksandar Repić"): ("U", "weeks before the vote"),
 ("2026-10-16 01:25", "China ballistic missile launch"): ("U", ""),
 ("2026-10-16 17:03", "Katie Zacharia out as Press Secretary by October 31"): ("U", ""),
 ("2026-10-16 17:36", "Katie Zacharia out as Press Secretary by October 19"): ("U", ""),
 ("2026-10-18 02:39", "Paris curfew by October 19"): ("U", ""),
 ("2026-10-18 14:24", "France declares state of siege"): ("U", ""),
 ("2026-10-18 15:16", "France declares state of emergency"): ("U", ""),
 ("2026-10-19 16:50", "Paris curfew by October 19"): ("U", ""),
 ("2026-10-19 16:51", "Paris curfew by October 24"): ("U", ""),
 ("2026-10-21 03:34", "Saudi Arabia military action against Yemen on October 6"): ("D", "after the day: late resolution"),
 ("2026-10-23 22:44", "Will Vox win the most seats"): ("U", "weeks before the vote"),
 ("2026-10-25 15:33", "Will María Corina Machado enter Venezuela by December 31"): ("U", ""),
 ("2026-10-25 15:33", "Will María Corina Machado enter Venezuela by October 31"): ("U", ""),
 ("2026-10-25 20:30", "Will Student List"): ("S", "election count"),
 ("2026-10-25 20:31", "Will Aleksandar Vučić be the next Prime Minister"): ("S", "election night"),
 ("2026-10-26 19:42", "Will Russia target Kyiv on October 26"): ("U", "attack during the day"),
 ("2026-10-27 18:54", "Will Trump meet with Flávio Bolsonaro"): ("U", ""),
 ("2026-10-27 19:59", "Will Likud win the second-most seats"): ("S", "election count"),
 ("2026-10-28 01:00", "Reserve Bank of New Zealand increases"): ("S", "central-bank decision"),
 ("2026-10-28 01:00", "No change in Reserve Bank of New Zealand"): ("S", "central-bank decision"),
 ("2026-10-29 09:57", "Christine Lagarde out"): ("U", ""),
 ("2026-10-29 17:55", "Will Russia target Kyiv on October 28"): ("D", "after the day: late confirmation"),
 ("2026-10-29 19:00", "Will Russia capture Svitle"): ("U", ""),
 ("2026-10-30 21:31", "Will Russia capture Svitle"): ("U", ""),
 ("2026-11-03 00:40", "US-Iran ceasefire continues through the midterms"): ("U", ""),
 ("2026-11-03 00:41", "US x Iran ceasefire continues through November 2"): ("U", ""),
 ("2026-11-03 00:41", "US x Iran ceasefire continues through November 6"): ("U", ""),
 ("2026-11-03 00:41", "US x Iran ceasefire continues through November 3"): ("U", ""),
 ("2026-11-03 09:25", "Saudi coalition strike in Yemen on November 5"): ("U", ""),
 ("2026-11-04 00:23", "Will the Democratic Party win the FL-13"): ("S", "election count"),
 ("2026-11-04 02:21", "Will Loranne Ausley"): ("S", "election count"),
 ("2026-11-04 03:39", "Will the Democratic Party win the TX-27"): ("S", "election count"),
 ("2026-11-04 03:49", "Will the Republican Party win the SC-02"): ("S", "election count"),
 ("2026-11-04 03:50", "Will the Republican Party win the TX-32"): ("S", "election count"),
 ("2026-11-04 03:58", "Will the Democratic Party win the TN-04"): ("S", "election count"),
 ("2026-11-04 04:18", "Will Karen Bass"): ("S", "election count"),
 ("2026-11-04 04:18", "Will Nithya Raman"): ("S", "election count"),
 ("2026-11-04 05:24", "Will the Democratic Party candidate win the 2026 Texas Senate"): ("S", "election count"),
 ("2026-11-04 06:45", "Will the Republican Party win the AK-AL"): ("S", "election count"),
 ("2026-11-04 21:27", "Will the Democratic Party win the AZ-02"): ("S", "election count"),
 ("2026-11-05 18:28", "Will the USS Theodore Roosevelt arrive"): ("U", ""),
 ("2026-11-05 21:00", "Will Donald Trump publicly insult Ken Paxton"): ("D", "after the deadline: late resolution"),
 ("2026-11-06 16:52", "Will Ivanka Popović"): ("U", "coalition news 12 days after the vote"),
 ("2026-11-06 18:51", "Will Susie Wiles leave"): ("U", ""),
 ("2026-11-07 19:55", "Will the Houthis enter Saudi Arabia by October 31"): ("D", "after the deadline"),
 ("2026-11-09 15:43", "Will Teddy Riner"): ("U", ""),
 ("2026-11-09 16:37", "Israel x Iran ceasefire continues through November 11"): ("U", ""),
 ("2026-11-09 18:34", "Will the Houthis enter Saudi Arabia by October 31"): ("D", "after the deadline"),
 ("2026-11-13 11:19", "China ballistic missile launch"): ("U", ""),
 ("2026-11-13 21:44", "FAA outage attributed to Iran"): ("U", ""),
 ("2026-11-14 01:15", "Will the FAA's nationwide ground stop be lifted"): ("U", "the lifting itself is the news"),
 ("2026-11-15 18:49", "Will Ulf Kristersson"): ("D", "PM vote/coalition timing may be scheduled"),
 ("2026-11-15 18:49", "Will Magdalena Andersson"): ("D", "PM vote/coalition timing may be scheduled"),
 ("2026-11-15 22:19", "Will the USS Theodore Roosevelt arrive"): ("U", "arrival reported"),
 ("2026-11-18 09:06", "Will Trump and Xi hug at APEC"): ("D", "at a scheduled summit"),
 ("2026-11-23 02:54", "Will Trump call for Jensen Huang"): ("U", ""),
 ("2026-09-03 11:09", "Will Russia enter Ternuvate again"): ("U", ""),
 ("2026-09-03 22:02", "Will the Democratic Party win the MO-05"): ("U", "two years before the vote"),
 ("2026-09-06 15:35", "Will Grüne win at least 7%"): ("S", "election day"),
 ("2026-09-09 15:47", "LAPTOP FDV above"): ("D", "token launch date may be scheduled"),
 ("2026-09-10 00:23", "Will Elaine Pelino"): ("S", "within 3 days after the primary"),
 ("2026-09-14 16:27", "Will the next governing coalition of Sweden"): ("S", "day after the election"),
 ("2026-09-21 09:20", "Will Russia enter Dobropillia"): ("U", ""),
 ("2026-09-21 12:23", "Will Russia enter Mykolaivka"): ("U", ""),
 ("2026-09-22 09:57", "Saudi Oil Pipeline (East-West) restarts by September 22"): ("U", ""),
 ("2026-09-22 17:53", "Will no qualifying diplomatic US-Iran meeting"): ("U", ""),
 ("2026-09-22 17:53", "US x Iran diplomatic meeting by September 30"): ("U", ""),
 ("2026-09-22 17:54", "US x Iran diplomatic meeting by October 31"): ("U", ""),
 ("2026-09-22 20:10", "Will Ted Cruz win the 2028"): ("U", ""),
 ("2026-09-23 18:53", "Will Christine Lagarde win the 2027 French"): ("U", ""),
 ("2026-09-23 21:15", "Will Mitch Landrieu"): ("U", ""),
 ("2026-09-23 21:15", "Will Chris Van Hollen"): ("U", ""),
 ("2026-09-24 11:18", "Will Russia and Ukraine hold any diplomatic meeting"): ("U", ""),
 ("2026-09-24 13:19", "U.S. anti-cartel operation"): ("U", ""),
 ("2026-09-29 03:21", "Will Russia enter Mykolaivka"): ("U", ""),
 ("2026-09-29 15:25", "Will Ohio enact a data center moratorium"): ("D", "a legislative vote may be scheduled"),
 ("2026-09-30 14:35", "Will Russia enter Mykolaivka"): ("U", "YES: the event itself"),
 ("2026-10-01 17:36", "Will Rahm Emanuel win the 2028"): ("U", ""),
 ("2026-10-03 16:14", "Will Russia capture all of Kostyantynivka"): ("U", ""),
 ("2026-10-05 01:46", "Will Trump name an AI czar"): ("U", "YES: the naming itself"),
 ("2026-10-05 20:29", "Saudi Arabia military action against Yemen on October 1"): ("D", "after the day: late resolution"),
 ("2026-10-06 12:08", "Will fewer than 20 ships transit"): ("D", "count published after the period"),
 ("2026-10-12 16:44", "Will oil be below $85 on November 2 and the Republicans"): ("D", "combo leg"),
 ("2026-10-12 16:50", "Will there be a Hormuz agreement, oil below $80, and the Republicans"): ("D", "combo leg"),
 ("2026-10-16 17:04", "Katie Zacharia out as Press Secretary by December 31"): ("U", ""),
 ("2026-10-18 02:46", "Paris curfew by October 21"): ("U", ""),
 ("2026-10-19 16:51", "Paris curfew by October 21"): ("U", ""),
 ("2026-10-25 20:30", "Will Aleksandar Vučić – United Serbia"): ("S", "election count"),
 ("2026-10-27 19:59", "Will Yashar win the most seats"): ("S", "election count"),
 ("2026-10-29 17:42", "Will voter turnout in the 2026 Serbian"): ("D", "official result after the vote"),
 ("2026-10-29 17:53", "Will J.D. Vance attend"): ("U", ""),
 ("2026-11-02 16:21", "Will Adam Hamilton"): ("U", ""),
 ("2026-11-03 00:39", "US x Iran ceasefire continues through November 8"): ("U", ""),
 ("2026-11-03 00:40", "US x Iran ceasefire continues through November 15"): ("U", ""),
 ("2026-11-03 00:40", "US x Iran ceasefire continues through November 4"): ("U", ""),
 ("2026-11-03 00:41", "US x Iran ceasefire continues through November 5"): ("U", ""),
 ("2026-11-04 00:23", "Will the Republican Party win the FL-13"): ("S", "election count"),
 ("2026-11-04 02:24", "Will the Democratic Party candidate win the 2026 Texas Senate election by 9%"): ("S", "election count"),
 ("2026-11-04 03:49", "Will the Democratic Party win the SC-02"): ("S", "election count"),
 ("2026-11-04 21:27", "Will the Republican Party win the AZ-02"): ("S", "election count"),
 ("2026-11-05 20:56", "Will Abdul El-Sayed win the 2028 Democratic"): ("U", ""),
 ("2026-11-05 23:46", "Will Scott Colom"): ("U", ""),
 ("2026-11-06 18:51", "Susie Wiles out as White House Chief of Staff"): ("U", ""),
 ("2026-11-07 00:10", "US x Iran effective ceasefire continues through November 8"): ("U", ""),
 ("2026-11-09 15:27", "Will Abdul El-Sayed win the 2028 US Presidential"): ("U", ""),
 ("2026-11-09 15:50", "Will Shawn Fain"): ("U", ""),
 ("2026-11-12 18:56", "Will Trump pardon Jensen Huang"): ("U", ""),
 ("2026-11-13 17:56", "Will Rob Sand"): ("U", ""),
 ("2026-11-13 22:45", "Will the FAA's nationwide ground stop be lifted by November 13, 7:00 PM ET"): ("D", "NO 1 h before own deadline"),
 ("2026-11-14 01:14", "Will the FAA's nationwide ground stop be lifted by November 13, 10:00 PM ET"): ("U", "the lifting itself"),
 ("2026-11-14 01:14", "Will the FAA's nationwide ground stop be lifted by November 14, 12:00 AM ET"): ("U", "the lifting itself"),
}


def main():
    rows = list(csv.DictReader(open(OUT / "labels_draft.csv")))
    out, missing, used = [], [], set()
    for r in rows:
        hit = [k for k in READ if k[0] == r["t0_iso"][:16] and r["question"].startswith(k[1])]
        if len(hit) != 1:
            missing.append(r)
            continue
        used.add(hit[0])
        code, why = READ[hit[0]]
        out.append({"c": r["c"], "t0": r["t0"], "t0_iso": r["t0_iso"], "status": r["status"], "cat": r["cat"],
                    "label": "unscheduled" if code == "U" else "scheduled", "doubt": "1" if code == "D" else "",
                    "reason": why, "question": r["question"]})
    if missing:
        for r in missing:
            print("UNREAD", r["t0_iso"][:16], r["cat"][:5], r["dir"], r["end_minus_t0_h"], r["hint"], "|", r["question"][:110], "|", r["event"])
        print(len(missing), "unread rows: labels.csv NOT written")
        sys.exit(1)
    if (OUT / "labels.csv").exists() and "--force" not in sys.argv:
        print("labels.csv exists (frozen); not overwritten"); sys.exit(1)
    with open(OUT / "labels.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
    print("labels", len(out), "unused readings", len(READ) - len(used))


if __name__ == "__main__":
    main()
