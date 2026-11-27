"""Poll the IEM 'latest run' service to time when new MOS/NBM runs become visible (evidence for the dissemination delay).
Logs one line per change to data/gaps_weather_fc/poll_availability.log. Gentle: 4 requests every 4 minutes."""
import time, urllib.request, datetime as dt
LOG = "/home/user/polymarket-lab/data/gaps_weather_fc/poll_availability.log"
last = {}
t_end = time.time() + 5.5 * 3600
while time.time() < t_end:
    for m in ("GFS", "MEX", "NBS", "NBE"):
        try:
            txt = urllib.request.urlopen(urllib.request.Request(
                f"https://mesonet.agron.iastate.edu/api/1/mos.txt?station=KLGA&model={m}", headers={"User-Agent": "research-script"}), timeout=40).read().decode()
            rt = txt.splitlines()[1].split(",")[2]
        except Exception as e:  # noqa: BLE001
            rt = None
        now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        if rt and last.get(m) != rt:
            with open(LOG, "a") as f:
                f.write(f"{now} {m} latest_runtime={rt} previous={last.get(m)}\n")
            last[m] = rt
        time.sleep(3)
    time.sleep(228)
