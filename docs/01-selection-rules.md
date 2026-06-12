# Selection Rules — Tourlist

**Status:** Draft v0.3 (spike amendments ratified and folded in)
**Last updated:** 2026-06-11
**Owner:** [you]
**Depends on:** `00-project-brief.md`. **Informed by:** `spike/FINDINGS.md`.

The core contract: for every concert in the attendance history, the app
suggests **exactly one song**, or explicitly declares why it can't. The rules
below are evaluated in precedence order; the first matching rule wins.

---

## 1. Global definitions (used by every rule)

| Concept | Definition |
|---|---|
| **Studio album** | A MusicBrainz release group with primary type *Album*, no secondary types, **and ≥1 release with official status**. The official-release filter is mandatory: release groups carry no bootleg flag, and without it bootlegs enter the trailing window and steal attribution (e.g. *Rough Mixes 4-26-91* predates *Ten* and contains its songs). |
| **Ranking measure** | Last.fm global playcount, per track (`autocorrect=1`). Used everywhere a "best song" decision is needed. Spike-validated: 233/233 sampled tracks found, all non-zero, ranking meaningful in the long tail. Singles inference is explicitly rejected. |
| **Attribution** | Every song is attributed to the **earliest owned studio album** (per the definition above) containing it. Compilations, live albums, and bootlegs **never** receive attribution and **never** confer eligibility, even if owned. Attribution determines the Album / Track # printed in the export. *(v2 backlog: owned compilations — e.g. greatest-hits — may count as an ownership source for a song; v1 is deliberately studio-albums-only.)* |
| **Ownership filter** | Hard. A song is eligible only if attributable to an owned studio album. No exceptions, no near-miss thresholds. Known consequence (spike): ~5–10% of played songs are non-album singles attributable to nothing and silently drop out of pools, per design. |
| **Global exclusion ("burning")** | Once a song is selected for any concert, it is ineligible for **every other concert by that artist, forever** — across tours and across the whole history. A song burns only when **confirmed** (auto-applied row reviewed, or manual pick). Unreviewed auto-suggestions do not burn; a draft export may therefore transiently suggest the same song for two unreviewed shows, self-healing on review. |
| **Pool** | The set of eligible songs a rule selects from. Default = highest-ranked song in the pool. The manual override is always limited to the same pool (each rule defines its own). |
| **Festival sets** | No special machinery. One playlist row per set; each set is a concert. Festival sets simply hit the low-information rules (R2, R5) more often. Known cost, accepted: festival slots burn big hits under global exclusion. |

## 2. Toured-album inference (runs before selection)

Date-window heuristic against MusicBrainz release dates. The setlist.fm
tour-name field is **never used for inference** — too sparse (51% present) —
but is shown in the review UI as a display hint / sanity flag (spike: it
agreed with inference 8/10 when it named an album; disagreement is a signal
to check the override).

Every inference outcome carries a **confidence class** — **evidenced** (I2,
I3) or **assumed** (I4) — which the selection rules consume.

| # | Step | Behaviour |
|---|---|---|
| I1 | **Trailing window** | Studio albums (per Global definitions, official-filtered) released within **30 months before** the show date are candidates. *(Widened from 24 after the spike found 2/30 shows missing the cliff by ≤3 months.)* |
| I2 | **Trailing evidence wins** | If any trailing candidate has ≥1 song in the setlist, the candidate with the **most songs played** wins; **ties go to the most recently released** (spike: Chelsea Wolfe 4–4 tie). Future-album tracks are **ignored entirely** at this step — an unreleased teaser is not evidence, even one trailing song beats five teasers (conservative error; manual override is the remedy). Confidence: **evidenced**. |
| I3 | **Leading (road-testing) inference** | Activates only when no trailing candidate put a single song on the setlist. A **future album with ≥1 song played** that night wins, with **unbounded lookahead** — evidence-gated, not time-gated (bands demo years early). Only possible because the app is retrospective. Confidence: **evidenced**, but see R1: I3-inferred albums never auto-apply (spike: unbounded lookahead confidently picked an album 3 years out when the true toured album was an excluded soundtrack). |
| I4 | **No usable setlist evidence** | Fires when the setlist is absent, **or** present but with zero trailing-candidate songs and zero future-album songs. Resolve against the trailing window alone: **most recently released candidate wins**. With no setlist, this album drives selection (R3). With a setlist present, it is **display context only** — selection proceeds on the setlist under R2. Confidence: **assumed**. |
| I5 | **Nothing matches** | Trailing window empty and no played future song → **not an album tour**. Selection proceeds under R2 (setlist present) or R5 (no setlist). |
| — | Known jank | Matching live performances to album tracks uses the pipeline: exact → normalised (quotes/accents/punctuation) → containment (handles Sigur Rós `[Vaka]` vs "Untitled #3 – Samskeyti") → fuzzy ≥0.85. Spike: 92% raw-exact, 0 true fuzzy cases, threshold has comfortable margin. Demos renamed on setlists ("New Song") still slip through; failed matches fall back to the trailing album. Manual override is the safety net. |

## 3. Selection rules — decision table (precedence order)

| # | Condition | Pool & default suggestion | Fallback if pool empty | Confirmation | Override pool |
|---|---|---|---|---|---|
| **R1** | Setlist known; toured album inferred **and owned**; ≥1 of its songs played | Songs from the toured album played that night, minus burned. Default = most popular. | → R2 | **Auto-apply if I2-inferred. Confirmation required if I3-inferred** (road-testing lookahead is weaker evidence; spike found its failure mode in the wild). | Same pool |
| **R2** | Setlist known; and either (a) no album tour (I5), (b) toured album **unowned**, or (c) toured album owned/assumed (I4-with-setlist) but **zero of its songs played** | Full setlist, filtered to **owned** (per attribution), minus burned. Default = most popular. | → R4 (if burns caused emptiness) else → R5 | **Auto-apply** | Same pool |
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
| Suggested, not yet reviewed (auto-apply pending review) | **Playlist** | Emitted as-is — auto-apply means auto-apply; partial drafts are the point of multi-session review. May transiently duplicate within an artist (see burning rule). |
| Awaiting confirmation (R3, R4, and I3-inferred R1) | **Needs review** | Listed with the pending suggestion shown; never silently promoted into the playlist. |
| Unresolved (R5) | **Unresolved** | Listed with the most-popular-played hint where available. |

Ordering: by attendance date (**parse setlist.fm's `dd-MM-yyyy` `eventDate` —
lexicographic sort silently mangles chronology**). Same-day rows (festivals)
preserve setlist.fm's own ordering — no pretence that it encodes set times.

## 5. Known limitations (accepted for v1; manual override is the remedy)

1. **Soundtracks**: excluding secondary-type Soundtrack is usually right but
   misses the rare soundtrack-as-toured-album (*Into the Wild*). Worse, the
   exclusion can hand I3 a confident wrong answer — now mitigated by I3's
   confirmation gate, fixed by the override.
2. **Non-album singles** (~5–10% of played songs) attribute to nothing and
   silently drop from R2 pools.
3. **MusicBrainz type/date jank**: crowd-sourced types occasionally mislabel
   compilations/live releases as studio albums (Chelsea Wolfe's *Unknown
   Rooms*, Dave Matthews & Tim Reynolds); release-group dates are occasionally
   sloppy (*Backspacer* dated 2009-01-01). Year-only precision (19% of sampled
   release groups, almost all legacy catalogue) is treated as mid-year.
4. **Renamed demos** defeat title matching and fall back to the trailing album.
5. **R4 is unexercised**: the spike could not simulate burning (no ownership
   data). A full-history burn simulation against real ownership — Pearl Jam ×9
   is the stress case — is deferred until the app has an ownership store.

## 6. Feeds into

- The PRD (this table is its core).
- ~~The spike~~ **Spike complete** (`spike/FINDINGS.md`): all three data bets
  validated; its nine findings are folded into this version. Projected rule
  firing (all-owned, no burning): R1 ≈ 50%, R2 ≈ 16%, R3 ≈ 26%, R5 ≥ 6%.
  Real ownership moves shows R1→R2 and R2→R5.
- Review UI requirements: per-rule override pools, confirmation states, burn
  accounting, tour-name display hint, and a workload centre of gravity around
  R3 (~a quarter of all shows need confirmation with synthesised pools).
