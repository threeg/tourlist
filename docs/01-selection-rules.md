# Selection Rules — Tourlist

**Status:** Draft v0.2 (interview output; all open decisions ratified)
**Last updated:** 2026-06-11
**Owner:** [you]
**Depends on:** `00-project-brief.md`

The core contract: for every concert in the attendance history, the app
suggests **exactly one song**, or explicitly declares why it can't. The rules
below are evaluated in precedence order; the first matching rule wins.

---

## 1. Global definitions (used by every rule)

| Concept | Definition |
|---|---|
| **Ranking measure** | Last.fm global playcount, per track. Used everywhere a "best song" decision is needed. Singles inference is explicitly rejected (too fuzzy for v1). |
| **Attribution** | Every song is attributed to the **earliest owned studio album** containing it. Compilations and live albums **never** receive attribution and **never** confer eligibility, even if owned. Attribution determines the Album / Track # printed in the export. *(v2 backlog: owned compilations — e.g. greatest-hits — may count as an ownership source for a song; v1 is deliberately studio-albums-only.)* |
| **Ownership filter** | Hard. A song is eligible only if attributable to an owned studio album. No exceptions, no near-miss thresholds. |
| **Global exclusion ("burning")** | Once a song is selected for any concert, it is ineligible for **every other concert by that artist, forever** — across tours and across the whole history. A song burns only when **confirmed** (auto-applied row reviewed, or manual pick). Unreviewed auto-suggestions do not burn; a draft export may therefore transiently suggest the same song for two unreviewed shows, self-healing on review. |
| **Pool** | The set of eligible songs a rule selects from. Default = highest-ranked song in the pool. The manual override is always limited to the same pool (each rule defines its own). |
| **Festival sets** | No special machinery. One playlist row per set; each set is a concert. Festival sets simply hit the low-information rules (R2, R5) more often. Known cost, accepted: festival slots burn big hits under global exclusion. |

## 2. Toured-album inference (runs before selection)

Date-window heuristic against MusicBrainz release dates. The setlist.fm
tour-name field is **ignored** (demoted to, at most, a display hint).

| # | Step | Behaviour |
|---|---|---|
| I1 | **Trailing window** | Studio albums released within **24 months before** the show date are candidates. |
| I2 | **Trailing evidence wins** | If any trailing candidate has ≥1 song in the setlist, the candidate with the **most songs played** wins. Future-album tracks are **ignored entirely** at this step — an unreleased teaser is not evidence, even if seven trailing songs face one teaser, and even one trailing song beats five teasers (conservative error; manual override is the remedy). |
| I3 | **Leading (road-testing) inference** | Activates only when no trailing candidate put a single song on the setlist. A **future album with ≥1 song played** that night wins, with **unbounded lookahead** — evidence-gated, not time-gated (bands demo years early). Only possible because the app is retrospective. |
| I4 | **No setlist** | Leading inference can never fire (no evidence possible). Resolve against the trailing window alone; if multiple trailing candidates, the **most recently released** wins. |
| I5 | **Nothing matches** | No trailing candidate, no played future song → **not an album tour**. Selection proceeds under R2. |
| — | Known jank | Matching live performances to later album tracks depends on setlist.fm titles matching MusicBrainz titles; demos get renamed ("New Song"). Failed matches silently fall back to the trailing album. Accepted for v1; the manual override is the safety net. |

## 3. Selection rules — decision table (precedence order)

| # | Condition | Pool & default suggestion | Fallback if pool empty | Confirmation | Override pool |
|---|---|---|---|---|---|
| **R1** | Setlist known; toured album inferred **and owned**; ≥1 of its songs played | Songs from the toured album played that night, minus burned. Default = most popular. | → R2 | **Auto-apply** (override available, never required) | Same pool |
| **R2** | Setlist known; and either (a) no album tour (I5), (b) toured album **unowned**, or (c) toured album owned but **zero of its songs played** | Full setlist, filtered to **owned** (per attribution), minus burned. Default = most popular. | → R4 (if burns caused emptiness) else → R5 | **Auto-apply** | Same pool |
| **R3** | Setlist **unknown or empty**; toured album inferred (I4) **and owned** | Synthesised pool = full tracklist of the toured album, minus burned. Default = most popular. The playlist knowingly contains a song with no evidence it was played. | → R4 | **Confirmation required** | **Entire album tracklist** (your memory of the night outranks Last.fm) |
| **R4** | **Exhaustion**: pool empty *only because of burned songs* (artist's owned, played material all used by earlier shows) | Widened pool = artist's **full owned discography** (studio albums, per attribution), minus burned. Default = most popular. "No repeats" outranks "really played that night" — dealer's choice, but the dealer shows the deck. | → R5 (entire owned discography burned) | **Confirmation required** | Full owned discography minus burned |
| **R5** | **Unresolved**: nothing owned was played; or setlist unknown and toured album unknown/unowned; or R4 exhausted | No suggestion. Concert lands in the export's **Unresolved** section with a hint: the most popular played song (when a setlist exists) — doubling as the proto–"to buy" list (v2 backlog). | — (terminal) | n/a | n/a |

Notes on collapsed cases (deliberately *not* rows):

- **"Toured album not owned"** is not a rule — the ownership filter makes its songs ineligible and the show falls through to R2 naturally.
- **"Multiple shows, same tour"** is not a rule — global exclusion handles it, and is intentionally stronger than per-tour (a song used on the *Ten* tour is unavailable at a greatest-hits show a decade later).
- **Festivals** are not a rule — see Global definitions.

## 4. Generation-time behaviour

"Generate playlist" is idempotent and re-runnable at any point, including
mid-review. Every concert is in exactly one state; the export is one document
with three sections:

| Concert state | Export section | Behaviour |
|---|---|---|
| Confirmed (reviewed auto-apply, or manual pick) | **Playlist** | Chronological row: Artist / Album (per attribution) / Track # / Title. |
| Suggested, not yet reviewed (R1/R2 auto-apply pending review) | **Playlist** | Emitted as-is — auto-apply means auto-apply; partial drafts are the point of multi-session review. May transiently duplicate within an artist (see burning rule). |
| Awaiting confirmation (R3/R4) | **Needs review** | Listed with the pending suggestion shown; never silently promoted into the playlist. |
| Unresolved (R5) | **Unresolved** | Listed with the most-popular-played hint where available. |

Ordering: by attendance date. Same-day rows (festivals) preserve setlist.fm's
own ordering — no pretence that it encodes set times.

## 5. Feeds into

- The PRD (this table is its core).
- The spike (de-scoped by I1–I5: it now only needs to validate MusicBrainz release-date cleanliness and Last.fm coverage, not tour-name parsing).
- Review UI requirements: per-rule override pools, confirmation states, burn accounting.
