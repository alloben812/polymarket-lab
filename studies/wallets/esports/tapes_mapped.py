import json, lib, sys
mp = json.load(open(f"{lib.HERE}/out/od_map.json")); n = 0; rows = 0
for c in mp:
    T = lib.tape(c); n += 1; rows += len(T)
print("tapes", n, "rows", rows)
