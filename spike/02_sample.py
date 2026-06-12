"""Step 2: stratified sample of ~30 shows from attendance.json -> sample.json.

Strata:
  A. repeat artists  - 2 shows each from the 5 most-seen artists
  B. festival sets   - days with >=3 attended sets, or venue/event ~ /fest/i
  C. empty setlists  - shows with no songs (exercises I4/R3/R5)
  D. one-off artists - artists seen exactly once, with a setlist (club gigs)
  E. random filler   - anything else, up to ~30 total
"""
import json
import os
import random
import re
from collections import Counter, defaultdict
from datetime import datetime

import spikelib

HERE = os.path.dirname(os.path.abspath(__file__))
random.seed(42)

shows = json.load(open(os.path.join(HERE, "attendance.json")))
for s in shows:
    s["_date"] = datetime.strptime(s["eventDate"], "%d-%m-%Y").date().isoformat()
    s["_songs"] = spikelib.setlist_songs(s)

dates = sorted(s["_date"] for s in shows)
print(f"true date range: {dates[0]} .. {dates[-1]}")

by_day = Counter(s["_date"] for s in shows)
artist_count = Counter(s["artist"]["name"] for s in shows)

def is_festival(s):
    blob = " ".join([s["venue"]["name"], (s.get("tour") or {}).get("name") or "",
                     s.get("info") or ""])
    return by_day[s["_date"]] >= 3 or re.search(r"fest", blob, re.I)

picked, picked_ids = [], set()

def take(candidates, n, stratum):
    random.shuffle(candidates)
    got = 0
    for s in candidates:
        if s["id"] in picked_ids:
            continue
        s["_stratum"] = stratum
        picked.append(s)
        picked_ids.add(s["id"])
        got += 1
        if got >= n:
            break

# A: 2 shows each from top-5 artists, spread across time
by_artist = defaultdict(list)
for s in shows:
    by_artist[s["artist"]["name"]].append(s)
for name, _ in artist_count.most_common(5):
    arr = sorted(by_artist[name], key=lambda s: s["_date"])
    take([arr[0], arr[-1]], 2, "A:repeat")

# B: festivals
take([s for s in shows if is_festival(s)], 6, "B:festival")
# C: empty setlists
take([s for s in shows if not s["_songs"]], 4, "C:no-setlist")
# D: one-off artists with a setlist, non-festival
take([s for s in shows if artist_count[s["artist"]["name"]] == 1
      and s["_songs"] and not is_festival(s)], 6, "D:one-off")
# E: filler
take(list(shows), 30 - len(picked), "E:random")

picked.sort(key=lambda s: s["_date"])
json.dump(picked, open(os.path.join(HERE, "sample.json"), "w"), indent=1)

print(f"\nsampled {len(picked)} shows:")
for s in picked:
    print(f"  {s['_date']}  [{s['_stratum']:<10}] {s['artist']['name']:<28} "
          f"@ {s['venue']['name'][:34]:<34} songs={len(s['_songs']):2d} "
          f"tour={(s.get('tour') or {}).get('name') or '-'}")
