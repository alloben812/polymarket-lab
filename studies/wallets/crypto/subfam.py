"""Sub-family of a crypto market from its slug/title."""
import re
_UD = re.compile(r"^([a-z0-9]+)-updown-(\d+[mh])-(\d{9,})$")
_ASSET = [("btc", ("bitcoin", "btc")), ("eth", ("ethereum", "eth")), ("sol", ("solana", "sol")), ("xrp", ("xrp", "ripple")),
          ("doge", ("dogecoin", "doge")), ("hype", ("hyperliquid", "hype")), ("bnb", ("bnb",))]

def asset_of(slug: str, title: str = "") -> str:
    s = (slug or "").lower()
    for a, keys in _ASSET:
        for k in keys:
            if re.search(rf"(^|-){k}(-|$)", s):
                return a
    t = (title or "").lower()
    for a, keys in _ASSET:
        if any(k in t for k in keys):
            return a
    return "?"

def subfam(slug: str, title: str = "") -> str:
    s = (slug or "").lower()
    m = _UD.match(s)
    if m:
        return f"{m.group(1)}-ud-{m.group(2)}"
    a = asset_of(s, title)
    t = (title or "").lower()
    if "up-or-down" in s or "up or down" in t:
        if re.search(r"\d(am|pm)-et", s) or re.search(r"\d(am|pm) et", t):
            return f"{a}-ud-1h"
        return f"{a}-ud-daily"
    if "-above-" in s or " above " in t or "-below-" in s or "greater-than" in s:
        return f"{a}-above"
    if "price-of" in s or "-between-" in s or " between " in t or "less-than" in s:
        return f"{a}-range"
    if "reach" in s or "-dip-" in s or "-hit-" in s or " hit " in t or " reach " in t or " dip " in t:
        return f"{a}-hit"
    if a != "?":
        return f"{a}-other"
    return "non-crypto"
