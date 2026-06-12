"""Step 1: pull full attendance history, dump to attendance.json, print basics."""
import json
import os
from collections import Counter

import spikelib

HERE = os.path.dirname(os.path.abspath(__file__))

shows = spikelib.fetch_attended("flupenflarf")
with open(os.path.join(HERE, "attendance.json"), "w") as f:
    json.dump(shows, f, indent=1)

dates = sorted(s["eventDate"] for s in shows)  # dd-MM-yyyy
artists = Counter(s["artist"]["name"] for s in shows)
with_songs = [s for s in shows if spikelib.setlist_songs(s)]
with_tour = [s for s in shows if (s.get("tour") or {}).get("name")]
with_mbid = [s for s in shows if s["artist"].get("mbid")]

print(f"total shows:            {len(shows)}")
print(f"date range:             {dates[0]} .. {dates[-1]}")
print(f"distinct artists:       {len(artists)}")
print(f"non-empty setlist:      {len(with_songs)} ({100*len(with_songs)//max(len(shows),1)}%)")
print(f"tour name present:      {len(with_tour)} ({100*len(with_tour)//max(len(shows),1)}%)")
print(f"artist has MBID:        {len(with_mbid)}")
print("\ntop 15 most-seen artists:")
for name, n in artists.most_common(15):
    print(f"  {n:3d}  {name}")
