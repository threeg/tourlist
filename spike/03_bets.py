"""Step 3: for each sampled show, test the three bets + simulate rule firing.

Outputs bets_results.json (one record per show) and prints a running log.

Ownership is unknown in the spike, so rule simulation runs under the
ALL-OWNED assumption (every studio album owned) with NO burning. That gives
the structural rule distribution; R5 hits under all-owned are a lower bound.
"""
import json
import os
import sys
from datetime import date, timedelta

import spikelib
from spikelib import norm_title, fuzzy_ratio, title_containment

HERE = os.path.dirname(os.path.abspath(__file__))
FUZZY_THRESHOLD = 0.85

sample = json.load(open(os.path.join(HERE, "sample.json")))

# ---------- date handling ----------

def parse_mb_date(s):
    """Returns (approx_date, precision) where precision in day/month/year/none."""
    if not s:
        return None, "none"
    parts = s.split("-")
    try:
        if len(parts) == 3:
            return date(int(parts[0]), int(parts[1]), int(parts[2])), "day"
        if len(parts) == 2:
            return date(int(parts[0]), int(parts[1]), 15), "month"
        return date(int(parts[0]), 7, 1), "year"
    except ValueError:
        return None, "none"

# ---------- per-artist discography with tracklists (cached in-process) ----------

_disco_cache = {}

def discography(mbid, name):
    if mbid in _disco_cache:
        return _disco_cache[mbid]
    albums = spikelib.studio_albums(mbid)
    print(f"  [{name}] {len(albums)} studio albums; fetching tracklists...",
          file=sys.stderr)
    for a in albums:
        a["approx_date"], a["precision"] = parse_mb_date(a["date"])
        _, tracks = spikelib.album_tracks(a["rgid"])
        a["tracks"] = tracks  # [(pos, title)]
        a["norm_tracks"] = {norm_title(t): (p, t) for p, t in tracks}
    _disco_cache[mbid] = albums
    return albums

# ---------- matching ----------

def match_song_to_album(song, album):
    """Returns (kind, track_title, ratio): kind in exact/norm/contains/fuzzy/none."""
    for p, t in album["tracks"]:
        if t == song:
            return "exact", t, 1.0
        if norm_title(t) == norm_title(song):
            return "norm", t, 1.0
    for p, t in album["tracks"]:
        if title_containment(song, t):
            return "contains", t, 1.0
    best, best_r = None, 0.0
    for p, t in album["tracks"]:
        r = fuzzy_ratio(song, t)
        if r > best_r:
            best, best_r = t, r
    if best_r >= FUZZY_THRESHOLD:
        return "fuzzy", best, best_r
    return "none", best, best_r

def songs_on_album(songs, album):
    """List of (song, kind, matched_title, ratio) with kind != none."""
    out = []
    for s in songs:
        kind, t, r = match_song_to_album(s, album)
        if kind != "none":
            out.append((s, kind, t, r))
    return out

# ---------- inference I1-I5 ----------

def infer_toured_album(show_date, songs, albums):
    """Returns (album_or_None, step, notes). Resolves the rules-doc gap where a
    setlist exists but has zero candidate evidence by falling back to the
    most recent trailing candidate (I4-style); flagged in notes."""
    window_start = show_date - timedelta(days=730)
    trailing = [a for a in albums if a["approx_date"]
                and window_start <= a["approx_date"] <= show_date]
    future = [a for a in albums if a["approx_date"]
              and a["approx_date"] > show_date]

    if songs:
        evid = [(len(songs_on_album(songs, a)), a) for a in trailing]
        evid = [(n, a) for n, a in evid if n > 0]
        if evid:
            # rules-doc gap: I2 defines no tie-break. Use most-recent-wins
            # (consistent with I4's spirit); record when a tie occurred.
            evid.sort(key=lambda x: x[1]["date"], reverse=True)
            evid.sort(key=lambda x: -x[0])
            tie = len(evid) > 1 and evid[0][0] == evid[1][0]
            note = f"{evid[0][0]} trailing songs played"
            if tie:
                note += (f" — TIE with {evid[1][1]['title']!r}, "
                         "most-recent won (rules doc silent)")
            return evid[0][1], "I2", note
        fut = [(len(songs_on_album(songs, a)), a) for a in future]
        fut = [(n, a) for n, a in fut if n > 0]
        if fut:
            fut.sort(key=lambda x: (-x[0], x[1]["date"]))
            return fut[0][1], "I3", f"{fut[0][0]} future songs played (road-test)"
        if trailing:
            trailing.sort(key=lambda a: a["date"])
            return trailing[-1], "I4*", ("GAP: setlist present, zero evidence; "
                                         "fell back to most recent trailing")
        return None, "I5", "no trailing candidate, no played future song"
    else:
        if trailing:
            trailing.sort(key=lambda a: a["date"])
            return trailing[-1], "I4", "no setlist; most recent trailing wins"
        return None, "I5", "no setlist, no trailing candidate"

# ---------- attribution (all-owned): earliest studio album containing song ----------

def attribute(song, albums):
    for a in albums:  # albums sorted by date ascending
        kind, t, r = match_song_to_album(song, a)
        if kind != "none":
            return a, t
    return None, None

# ---------- main loop ----------

results = []
for i, show in enumerate(sample):
    artist = show["artist"]["name"]
    mbid = show["artist"]["mbid"]
    show_date = date.fromisoformat(show["_date"])
    songs_all = []
    covers = []
    for st in show.get("sets", {}).get("set", []):
        for song in st.get("song", []):
            nm = (song.get("name") or "").strip()
            if not nm or song.get("tape"):
                continue
            if song.get("cover"):
                covers.append(nm)
            else:
                songs_all.append(nm)

    print(f"\n[{i+1}/{len(sample)}] {show['_date']} {artist} "
          f"({len(songs_all)} own songs, {len(covers)} covers)", file=sys.stderr)
    albums = discography(mbid, artist)

    rec = {
        "date": show["_date"], "artist": artist, "stratum": show["_stratum"],
        "venue": show["venue"]["name"], "tour": (show.get("tour") or {}).get("name"),
        "n_songs": len(songs_all), "n_covers": len(covers),
        "n_studio_albums": len(albums),
        "date_precision": {p: sum(1 for a in albums if a["precision"] == p)
                           for p in ("day", "month", "year", "none")},
    }

    # --- Bet 1: inference ---
    album, step, notes = infer_toured_album(show_date, songs_all, albums)
    rec["inference"] = {"step": step, "notes": notes,
                        "album": album["title"] if album else None,
                        "album_date": album["date"] if album else None,
                        "album_precision": album["precision"] if album else None}
    print(f"  inference: {step} -> {album['title'] if album else 'NONE'} ({notes})",
          file=sys.stderr)

    # --- Bet 3: title matching against inferred album ---
    if album and songs_all:
        matches = []
        for s in songs_all:
            kind, t, r = match_song_to_album(s, album)
            matches.append({"song": s, "kind": kind, "matched": t,
                            "ratio": round(r, 3)})
        on_album = [m for m in matches if m["kind"] != "none"]
        rec["title_match"] = {
            "on_album": len(on_album),
            "exact": sum(1 for m in on_album if m["kind"] == "exact"),
            "norm": sum(1 for m in on_album if m["kind"] == "norm"),
            "contains": sum(1 for m in on_album if m["kind"] == "contains"),
            "fuzzy": sum(1 for m in on_album if m["kind"] == "fuzzy"),
            "fuzzy_cases": [m for m in on_album if m["kind"] in ("fuzzy", "contains")],
            "near_misses": [m for m in matches
                            if m["kind"] == "none" and m["ratio"] >= 0.55],
        }

    # --- rule simulation (all-owned, no burning) + pool construction ---
    if songs_all:
        if album:
            played_on_album = songs_on_album(songs_all, album)
            if played_on_album:
                rule, pool = "R1", [s for s, *_ in played_on_album]
            else:
                rule = "R2"
                pool = [s for s in songs_all if attribute(s, albums)[0]]
                if not pool:
                    rule = "R5"
        else:
            rule = "R2"
            pool = [s for s in songs_all if attribute(s, albums)[0]]
            if not pool:
                rule = "R5"
    else:
        if album:
            rule, pool = "R3", [t for _, t in album["tracks"]]
        else:
            rule, pool = "R5", []
    if rule == "R5":
        pool = []
    rec["rule"] = rule
    if rule == "R2" and songs_all:
        rec["r2_unattributable"] = [s for s in songs_all
                                    if not attribute(s, albums)[0]]
    print(f"  rule: {rule} (pool size {len(pool)})", file=sys.stderr)

    # --- Bet 2: Last.fm playcounts for the pool (cap 25 tracks) ---
    lf = []
    for s in pool[:25]:
        info = spikelib.lastfm_track(artist, s)
        lf.append({"song": s,
                   "found": info is not None,
                   "playcount": info["playcount"] if info else None,
                   "listeners": info["listeners"] if info else None})
    found = [x for x in lf if x["found"]]
    nonzero = [x for x in found if x["playcount"]]
    rec["lastfm"] = {
        "pool_size": len(pool), "queried": len(lf),
        "found": len(found), "nonzero": len(nonzero),
        "degenerate": len(lf) > 0 and len(nonzero) <= 1,
        "top": sorted(found, key=lambda x: -(x["playcount"] or 0))[:3],
        "tracks": lf,
    }
    if lf:
        print(f"  lastfm: {len(found)}/{len(lf)} found, {len(nonzero)} nonzero; "
              f"top={rec['lastfm']['top'][0]['song'] if found else '-'}",
              file=sys.stderr)

    results.append(rec)
    json.dump(results, open(os.path.join(HERE, "bets_results.json"), "w"), indent=1)

print(f"\ndone: {len(results)} shows -> bets_results.json", file=sys.stderr)
