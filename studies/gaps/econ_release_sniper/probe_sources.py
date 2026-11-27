"""Part 2: response time and cache behaviour of the agencies' release pages / APIs, measured from this sandbox.
6 plain requests + 2 cache-busting requests per URL, >= 2 s apart. Output: out/sources.json (small)."""
import json, subprocess, time, random, sys

OUT = "/home/user/polymarket-lab/studies/gaps/econ_release_sniper/out/sources.json"
URLS = [
    ("BLS CPI release page", "https://www.bls.gov/news.release/cpi.nr0.htm"),
    ("BLS Employment release page", "https://www.bls.gov/news.release/empsit.nr0.htm"),
    ("BLS API v1 (no key) CPI-U SA", "https://api.bls.gov/publicAPI/v1/timeseries/data/CUSR0000SA0"),
    ("BEA current releases", "https://www.bea.gov/news/current-releases"),
    ("BEA PCE page", "https://www.bea.gov/data/personal-consumption-expenditures-price-index"),
    ("Fed press releases page", "https://www.federalreserve.gov/newsevents/pressreleases.htm"),
    ("Fed monetary RSS", "https://www.federalreserve.gov/feeds/press_monetary.xml"),
    ("DOL weekly claims PDF", "https://www.dol.gov/ui/data.pdf"),
    ("ISM PMI reports", "https://www.ismworld.org/supply-management-news-and-reports/reports/ism-pmi-reports/"),
    ("UMich SCA home", "https://www.sca.isr.umich.edu/"),
    ("ONS CPI page", "https://www.ons.gov.uk/economy/inflationandpriceindices"),
    ("Polymarket CLOB time (reference)", "https://clob.polymarket.com/time"),
]
HDRS = ["cache-control", "age", "etag", "last-modified", "x-cache", "cf-cache-status", "server", "via", "expires",
        "x-akamai-transformed", "akamai-cache-status", "x-served-by", "x-cache-hits", "date", "content-type", "x-amz-cf-pop", "cf-ray"]
FMT = "%{http_code} %{time_namelookup} %{time_connect} %{time_appconnect} %{time_starttransfer} %{time_total} %{size_download}"


def one(url):
    p = subprocess.run(["curl", "-s", "-o", "/dev/null", "-D", "-", "-w", "\n@@" + FMT, "--max-time", "20",
                        "-A", "Mozilla/5.0 (research; release-timing probe)", "-H", "Accept-Encoding: gzip", url],
                       capture_output=True, text=True)
    out = p.stdout
    head, _, w = out.rpartition("\n@@")
    h = {}
    for line in head.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            if k.strip().lower() in HDRS:
                h[k.strip().lower()] = v.strip()[:120]
    parts = w.split()
    if len(parts) < 7:
        return {"err": out[-200:] + p.stderr[-200:]}
    code, dns, conn, tls, ttfb, tot, size = parts
    return {"code": code, "connect": float(conn), "tls": float(tls), "ttfb": float(ttfb), "total": float(tot),
            "bytes": int(float(size)), "h": h, "t": time.time()}


res = {}
for name, url in URLS:
    rows = []
    for i in range(8):
        u = url
        if i >= 6:
            u = url + ("&" if "?" in url else "?") + "_=%d" % random.randrange(10**9)
        r = one(u); r["bust"] = i >= 6
        rows.append(r)
        time.sleep(2)
    res[name] = {"url": url, "rows": rows}
    ok = [r for r in rows if "ttfb" in r]
    print(name, [r.get("code") for r in rows], "ttfb", sorted(round(r["ttfb"], 3) for r in ok)[:8], file=sys.stderr)
trace = subprocess.run(["curl", "-s", "--max-time", "10", "https://www.cloudflare.com/cdn-cgi/trace"], capture_output=True, text=True).stdout
res["_trace"] = {k: v for k, v in (l.split("=", 1) for l in trace.splitlines() if "=" in l) if k in ("colo", "loc", "http", "tls")}
json.dump(res, open(OUT, "w"), indent=1)
