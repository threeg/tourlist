"""Step 4: aggregate bets_results.json into the tables FINDINGS.md needs."""
import json
import os
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
recs = json.load(open(os.path.join(HERE, "bets_results.json")))
print(f"{len(recs)} shows analysed\n")

# ---- Bet 1: release-date precision + inference outcomes ----
prec = Counter()
total_albums = 0
for r in recs:
    for k, v in r["date_precision"].items():
        prec[k] += v
        total_albums += v
print("== Bet 1: MusicBrainz release-date precision (across all sampled artists' studio albums) ==")
for k in ("day", "month", "year", "none"):
    print(f"  {k:>6}: {prec[k]:3d} ({100*prec[k]//max(total_albums,1)}%)")
print(f"  total : {total_albums}")

steps = Counter(r["inference"]["step"] for r in recs)
print(f"\ninference steps: {dict(steps)}")
print("\nper-show inference:")
for r in recs:
    inf = r["inference"]
    print(f"  {r['date']} {r['artist'][:24]:<24} {inf['step']:<4} "
          f"-> {inf['album'] or 'NONE':<38} [{inf['album_date'] or '-'}] "
          f"(tour field: {r['tour'] or '-'})")

# ---- Bet 2: Last.fm coverage ----
print("\n== Bet 2: Last.fm coverage ==")
tq = tf = tnz = 0
degen = []
for r in recs:
    lf = r["lastfm"]
    tq += lf["queried"]; tf += lf["found"]
    tnz += lf["nonzero"]
    if lf["queried"] and lf["degenerate"]:
        degen.append(r)
print(f"  tracks queried: {tq}, found: {tf} ({100*tf//max(tq,1)}%), "
      f"nonzero playcount: {tnz} ({100*tnz//max(tq,1)}%)")
print(f"  degenerate pools (<=1 nonzero): {len(degen)}")
for r in degen:
    print(f"    {r['date']} {r['artist']} rule={r['rule']} "
          f"pool={r['lastfm']['pool_size']} found={r['lastfm']['found']}")
# spread check: is the ranking meaningful (clear ordering)?
print("  sample top tracks:")
for r in recs[:0]:
    pass

# ---- Bet 3: title matching ----
print("\n== Bet 3: title matching (setlist.fm vs MB tracks of inferred album) ==")
te = tn = tc = tfz = 0
fuzzy_cases, near = [], []
for r in recs:
    tm = r.get("title_match")
    if not tm:
        continue
    te += tm["exact"]; tn += tm["norm"]
    tc += tm.get("contains", 0); tfz += tm["fuzzy"]
    for c in tm["fuzzy_cases"]:
        fuzzy_cases.append((r["artist"], c))
    for c in tm["near_misses"]:
        near.append((r["artist"], c))
tot = te + tn + tc + tfz
print(f"  matched titles: {tot} -> exact-raw {te} ({100*te//max(tot,1)}%), "
      f"exact-after-normalise {tn}, containment {tc}, fuzzy-only {tfz}")
print("  fuzzy-only cases:")
for a, c in fuzzy_cases:
    print(f"    [{a}] setlist '{c['song']}' ~ album '{c['matched']}' ({c['ratio']})")
print("  near misses (no-match but ratio >= 0.55 — possible missed matches):")
for a, c in near:
    print(f"    [{a}] setlist '{c['song']}' ?~ album '{c['matched']}' ({c['ratio']})")

# ---- rule distribution ----
print("\n== Rule firing (ALL-OWNED assumption, no burning) ==")
rules = Counter(r["rule"] for r in recs)
for k in ("R1", "R2", "R3", "R4", "R5"):
    n = rules.get(k, 0)
    print(f"  {k}: {n:2d} ({100*n//len(recs)}%)")
gap = [r for r in recs if r["inference"]["step"] == "I4*"]
print(f"\nI4* rules-doc gap cases (setlist present, zero evidence): {len(gap)}")
for r in gap:
    print(f"  {r['date']} {r['artist']} -> {r['inference']['album']}")

print("\nR2 shows and their unattributable setlist songs (not on any studio album):")
for r in recs:
    if r["rule"] == "R2":
        ua = r.get("r2_unattributable", [])
        print(f"  {r['date']} {r['artist'][:24]:<24} pool={r['lastfm']['pool_size']:2d} "
              f"unattributable={len(ua)} {ua[:4]}")
print("\nR5 shows:")
for r in recs:
    if r["rule"] == "R5":
        print(f"  {r['date']} {r['artist'][:24]:<24} stratum={r['stratum']} "
              f"songs={r['n_songs']} albums={r['n_studio_albums']} "
              f"inference={r['inference']['step']}")
