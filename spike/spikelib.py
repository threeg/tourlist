"""Throwaway spike helpers: cached, rate-limited HTTP GETs against
setlist.fm, MusicBrainz and Last.fm. Cache lives in spike/cache/ keyed by
a hash of the full URL+headers, so re-runs cost zero API calls.
"""
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(HERE, "cache")
os.makedirs(CACHE_DIR, exist_ok=True)

USER_AGENT = "tourlist-spike/0.1 (gregg.seymour@appnovation.com)"


def _require_key(env_var):
    key = os.environ.get(env_var)
    if not key:
        sys.exit(f"missing {env_var} — export it before running "
                 f"(only needed for uncached requests)")
    return key

# seconds between requests, per host
_MIN_INTERVAL = {
    "api.setlist.fm": 1.2,       # free tier is strict (2/s nominal; stay well under)
    "musicbrainz.org": 1.1,      # MB requires <=1 req/s
    "ws.audioscrobbler.com": 0.3,
}
_last_call = {}


def _cache_path(url):
    h = hashlib.sha256(url.encode()).hexdigest()[:24]
    return os.path.join(CACHE_DIR, h + ".json")


def get_json(url, headers=None, max_retries=5):
    """GET url, return parsed JSON. Disk-cached forever. 404 cached as None."""
    path = _cache_path(url)
    if os.path.exists(path):
        with open(path) as f:
            blob = json.load(f)
        return blob["body"]

    host = urllib.parse.urlparse(url).hostname
    hdrs = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if headers:
        hdrs.update(headers)

    for attempt in range(max_retries):
        wait = _MIN_INTERVAL.get(host, 1.0) - (time.time() - _last_call.get(host, 0))
        if wait > 0:
            time.sleep(wait)
        _last_call[host] = time.time()
        req = urllib.request.Request(url, headers=hdrs)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            with open(path, "w") as f:
                json.dump({"url": url, "body": body}, f)
            return body
        except urllib.error.HTTPError as e:
            if e.code == 404:
                with open(path, "w") as f:
                    json.dump({"url": url, "body": None}, f)
                return None
            if e.code in (429, 502, 503) and attempt < max_retries - 1:
                backoff = 3 * (2 ** attempt)
                print(f"  [{host} {e.code}] backing off {backoff}s", file=sys.stderr)
                time.sleep(backoff)
                continue
            raise
        except (urllib.error.URLError, TimeoutError):
            if attempt < max_retries - 1:
                time.sleep(3 * (2 ** attempt))
                continue
            raise


# ---------- setlist.fm ----------

def setlistfm(path, **params):
    qs = ("?" + urllib.parse.urlencode(params)) if params else ""
    url = f"https://api.setlist.fm/rest/1.0{path}{qs}"
    return get_json(url, headers={"x-api-key": _require_key("SETLISTFM_API_KEY")})


def fetch_attended(username):
    """All attended setlists for a user, newest first (API order)."""
    shows = []
    page = 1
    while True:
        data = setlistfm(f"/user/{username}/attended", p=page)
        if not data or not data.get("setlist"):
            break
        shows.extend(data["setlist"])
        total = data.get("total", 0)
        per_page = data.get("itemsPerPage", 20)
        print(f"  page {page}: {len(shows)}/{total}", file=sys.stderr)
        if page * per_page >= total:
            break
        page += 1
    return shows


def setlist_songs(show):
    """Flat list of song names from a setlist.fm setlist blob (skips tapes)."""
    songs = []
    for st in show.get("sets", {}).get("set", []):
        for song in st.get("song", []):
            name = (song.get("name") or "").strip()
            if name and not song.get("tape"):
                songs.append(name)
    return songs


# ---------- MusicBrainz ----------

def mb(path, **params):
    params["fmt"] = "json"
    url = f"https://musicbrainz.org/ws/2{path}?{urllib.parse.urlencode(params)}"
    return get_json(url)


def studio_albums(artist_mbid, official_only=True):
    """Studio-album release groups (primary type Album, no secondary types),
    with first-release-date. Returns list of dicts sorted by date.

    official_only: drop release groups with zero official releases — RGs have
    no status field themselves, so bootlegs ("Rough Mixes 4-26-91") otherwise
    masquerade as studio albums and pollute the window + attribution."""
    out = []
    offset = 0
    while True:
        data = mb("/release-group", artist=artist_mbid, type="album",
                  limit=100, offset=offset)
        if not data:
            break
        for rg in data.get("release-groups", []):
            if rg.get("primary-type") != "Album":
                continue
            if rg.get("secondary-types"):
                continue  # live, compilation, soundtrack, remix...
            out.append({
                "rgid": rg["id"],
                "title": rg["title"],
                "date": rg.get("first-release-date", "") or "",
            })
        offset += 100
        if offset >= data.get("release-group-count", 0):
            break
    if official_only:
        out = [a for a in out if _has_official_release(a["rgid"])]
    out.sort(key=lambda a: a["date"] or "9999")
    return out


def _has_official_release(rgid):
    data = mb("/release", **{"release-group": rgid, "inc": "recordings",
                             "status": "official", "limit": 100})
    return bool((data or {}).get("releases"))


def album_tracks(rgid):
    """Track titles for a release group: earliest official release's tracklist.
    Returns (release_title, [(position, title), ...]) or (None, [])."""
    data = mb("/release", **{"release-group": rgid, "inc": "recordings",
                             "status": "official", "limit": 100})
    releases = (data or {}).get("releases", [])
    if not releases:
        data = mb("/release", **{"release-group": rgid, "inc": "recordings",
                                 "limit": 100})
        releases = (data or {}).get("releases", [])
    if not releases:
        return None, []
    releases.sort(key=lambda r: (r.get("date") or "9999",
                                 r.get("media") and len(r["media"]) or 9))
    rel = releases[0]
    tracks = []
    pos = 0
    for medium in rel.get("media", []):
        for tr in medium.get("tracks", []):
            pos += 1
            tracks.append((pos, tr.get("title", "")))
    return rel.get("title"), tracks


# ---------- Last.fm ----------

def lastfm_track(artist, track):
    """Returns dict with playcount/listeners ints, or None if not found."""
    params = urllib.parse.urlencode({
        "method": "track.getInfo", "api_key": _require_key("LASTFM_API_KEY"),
        "artist": artist, "track": track, "format": "json",
        "autocorrect": 1,
    })
    data = get_json(f"https://ws.audioscrobbler.com/2.0/?{params}")
    if not data or "track" not in data:
        return None
    t = data["track"]
    try:
        return {"playcount": int(t.get("playcount", 0)),
                "listeners": int(t.get("listeners", 0)),
                "matched_name": t.get("name")}
    except (TypeError, ValueError):
        return None


# ---------- title matching ----------

def norm_title(s):
    """Aggressive normalisation for title comparison."""
    import re
    import unicodedata
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower()
    s = s.replace("’", "'").replace("‘", "'")
    # drop (parentheticals) like "(live)"/"(acoustic)" — but if that empties
    # the title (MB names Sigur Rós' ( ) tracks "[Vaka]"), keep the content
    # and let the punctuation pass below handle the brackets
    stripped = re.sub(r"\s*\(.*?\)\s*", " ", s)
    if stripped.strip(" []!?.,'\"-"):
        s = stripped
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return s.strip()


def title_containment(a, b):
    """True if one normalised title contains the other (>=4 chars contained):
    catches 'Untitled #3 – Samskeyti' vs '[Samskeyti]'."""
    na, nb = norm_title(a), norm_title(b)
    if len(na) < 4 or len(nb) < 4:
        return False
    return na in nb or nb in na


def fuzzy_ratio(a, b):
    import difflib
    return difflib.SequenceMatcher(None, norm_title(a), norm_title(b)).ratio()
