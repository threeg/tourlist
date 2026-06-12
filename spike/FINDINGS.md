# Spike Findings — validating the three data bets

**Date:** 2026-06-11
**Inputs:** setlist.fm user `flupenflarf` (full history), MusicBrainz, Last.fm.
**Method:** 30-show stratified sample (repeat artists, festival sets, no-setlist
shows, one-off club gigs, random filler) run through the I1–I5 inference and
R1–R5 selection logic from `docs/01-selection-rules.md`. All API responses
cached in `spike/cache/` (~700 files); re-runs are free. Scripts: `01_attendance.py`
→ `02_sample.py` → `03_bets.py` → `04_summarize.py`. Disposable.

**Simulation caveats:** ownership is unknown, so rules ran under an
**all-albums-owned** assumption with **no burning**. R1/R3 numbers are
therefore upper bounds and R5 is a floor; R4 can't fire at all without burning.

## Attendance basics

| Metric | Value |
|---|---|
| Total shows | 238 |
| Date range | 1993-12-30 → 2026-04-04 |
| Distinct artists | 157 |
| Non-empty setlist | 181 (76%) |
| Tour name present | 123 (51%) |
| Artist has MBID in setlist.fm payload | 238 (100%) |
| Most-seen | Pearl Jam ×9, Modest Mouse ×7, Mogwai ×6, Japandroids ×5, Eddie Vedder ×5 |

100% MBID coverage is a quiet win: no artist-name disambiguation layer needed —
setlist.fm hands us the MusicBrainz key directly.

## Verdict summary

| Bet | Verdict |
|---|---|
| 1. MusicBrainz release dates | **Workable — clean only after an official-release filter** (mandatory, see below) |
| 2. Last.fm coverage | **Clean** — 233/233 pool tracks found, all non-zero, ranking meaningful in the long tail |
| 3. Title matching | **Clean with light normalisation** — 92% raw-exact; no true fuzzy matching needed in sample |

---

## Bet 1 — MusicBrainz release dates: WORKABLE (with one mandatory fix)

**Date precision** (across the 30 sampled artists' studio-album release groups,
after filtering — see below): 76% day-precise, 4% month, 19% year-only, 0% missing.
The year-only mass is almost entirely legacy catalogue — 50 of Tony Bennett's 71
albums, all pre-2000s. Albums in the touring era the 24-month window actually
tests are effectively always day-precise. Treating year-only as mid-year is fine;
only one sampled inference relied on a year-only date (Loney Dear, *Loney, Noir*
[2005]) and it still resolved correctly.

**⚠ Mandatory fix: filter to release groups with ≥1 official release.**
MusicBrainz release *groups* carry no official/bootleg status (only releases do),
so a naive "primary-type Album, no secondary types" query returns bootlegs as
studio albums. Pearl Jam's "discography" included *Rough Mixes 4-26-91*, *The
Secrect Gig*, *Freak*, *Covers 1995*… Without the filter this is not cosmetic:

- bootlegs enter the 24-month trailing window as candidates, and
- *Rough Mixes 4-26-91* (1991-04-26) **predates *Ten*** (1991-08-27) and contains
  its songs — under "earliest studio album wins", attribution would print bootleg
  titles in the export.

The filter removed 47 of 356 sampled release groups (13%) and eliminated every
date-less one. **Amend the rules doc's definition of "studio album" to include
official-release status.**

**Inference results (I1–I5) on the sample:** I2 ×13, I3 ×2, I4 ×8, I5 ×7.
Ground-truthing against the setlist.fm tour-name field where it names an album
(10 shows): inference agreed 8/10. The misses are instructive:

- **Eddie Vedder 2008, tour field "Into the Wild"** — the toured album is a
  *soundtrack*, which the studio-albums-only rule excludes; with zero trailing
  evidence, I3's unbounded lookahead confidently grabbed *Ukulele Songs* (2011,
  three years out). Manual override is the designed remedy, but see the R1
  auto-apply concern under "Amendments".
- **Mumford & Sons 2011-10-22, tour field "Sigh No More"** — *Sigh No More*
  (2009-10-02) missed the 24-month window by **3 weeks**, so I3 inferred *Babel*
  (2012) off one road-tested song. Defensible (they did debut Babel material that
  night) but it produced a degenerate one-song R1 pool.

A second near-miss: Modest Mouse 2023 fell to I5 because *The Golden Casket*
missed the window by ~2.5 months (26.5 months old at show time). Two of 30
shows landing within ±3 months of the window edge suggests the 24-month
constant deserves a sensitivity check before freezing.

Data warts seen: *Backspacer*'s release-group first-release-date is `2009-01-01`
(actual: 2009-09-20) — harmless here, but RG-level dates can be sloppy.
Chelsea Wolfe's *Unknown Rooms* (a compilation by any sane reading) is typed a
plain studio Album in MB. Dave Matthews & Tim Reynolds' lone "studio album" is
actually a live release mis-typed. MB types are crowd-sourced; the manual
override carries this.

## Bet 2 — Last.fm coverage: CLEAN

233/233 pool tracks queried were found (with `autocorrect=1`), every one with a
non-zero global playcount — including Icelandic titles (Sigur Rós), a tiny
Portland instrumental act (Talkdemonic: 11,931 plays), and deep album cuts.
Ranking is meaningful, not degenerate, even in the long tail:

- Loney Dear (R3 pool): 28,259 → 407, clean strict ordering.
- Ginger Root (R3 pool): 549k → 53k.
- Blaqk Audio (R2 pool): 537k → 13k.

The only "degenerate" pools were degenerate by *size* (a 1-song pool ranks
trivially), not by missing data. No fallback ranking source needed for v1.

## Bet 3 — Title matching: CLEAN with light normalisation

Of 79 setlist-song ↔ inferred-album-track matches: **92% raw exact**, 8% exact
after normalisation (curly quotes, accents, punctuation), **0 needed real fuzzy
matching** at a 0.85 similarity threshold. The worst non-matches in the sample
(e.g. setlist "Art Czars" vs album "Heart Sweats", 0.57) are *true* negatives —
genuinely different songs — which means a fuzzy threshold around 0.85 has a
comfortable safety margin against false positives.

One structural case needs more than string distance: MB titles Sigur Rós'
*( )* tracks as `[Vaka]`, `[Samskeyti]`… while setlist.fm uses
"Untitled #3 – Samskeyti". Naive parenthetical-stripping normalisation turns
the MB titles into empty strings; a **containment rule** (one normalised title
contained in the other) resolves them all. Recommended matcher pipeline:
exact → normalised-exact → containment → fuzzy ≥0.85.

## Rule-firing distribution (all-owned, no burning)

| Rule | Sample count | Share | Notes |
|---|---|---|---|
| R1 | 15 | 50% | Happy path; upper bound (ownership shrinks this) |
| R2 | 5 | 16% | Incl. all "not an album tour" shows (Beck, Sigur Rós, War on Drugs…) |
| R3 | 8 | 26% | Every no-setlist show with a trailing album; **confirmation-required**, so this is review-UI workload |
| R4 | 0 | 0% | Cannot fire without burning; needs a full-history simulation (Pearl Jam ×9 is the stress case) |
| R5 | 2 | 6% | **Floor.** Both were no-setlist + no-window-album |

The sample's no-setlist share (27%) tracks the population (24%), so R3+R5 ≈
one-third of all shows needing either confirmation or triage is a fair
projection — review-UI effort should go there. Real ownership will move shows
R1→R2 (toured album unowned but other played songs owned) and R2→R5 (nothing
owned); R5 in practice will sit well above 6% and doubles as the "to buy" list,
as the rules doc anticipates.

## Surprises / proposed amendments before the PRD freezes

1. **Amend the studio-album definition** (Global definitions + I1): release
   groups must have ≥1 *official* release. Without it, bootlegs corrupt both the
   window and attribution. (Found via Pearl Jam; severity: breaks exports.)
2. **I2 has no tie-break.** Chelsea Wolfe 2014 tied 4–4 between *Unknown Rooms*
   (2012) and *Pain Is Beauty* (2013); the correct album was the more recent.
   Propose: most-recent-wins on ties (consistent with I4's spirit).
3. **Consider gating I3-derived R1 behind confirmation.** I3's unbounded
   lookahead produced a confident wrong answer (Eddie Vedder → *Ukulele Songs*,
   3 years out, when the real toured album was an excluded soundtrack) and a
   degenerate 1-song pool (Mumford & Sons). R1 currently *auto-applies*; an
   I3-inferred album is much weaker evidence than an I2 one.
4. **24-month window sensitivity:** 2 of 30 shows missed the window by ≤3
   months (Mumford & Sons by 3 weeks, Modest Mouse by ~2.5 months). Worth
   either widening to ~30 months or keeping 24 and accepting the manual
   override — but decide deliberately.
5. **Rules-doc wording gap:** R2(c) ("toured album owned but zero of its songs
   played") implies an inference path that I1–I5 never define — with a setlist
   present, no trailing evidence, and no future songs, no step assigns an album
   (I4 is no-setlist-only). It never fired in the sample, but the PRD should
   either add the I4-style fallback or strike R2(c).
6. **Soundtracks:** excluding secondary-type Soundtrack is usually right, but
   it excludes *Into the Wild* — a soundtrack that *was* the toured album. v1
   answer is the manual override; note it as a known class of misses.
7. **Non-album singles in R2 pools** are real but small: ~5–10% of played songs
   are unattributable to any studio album (e.g. "King Rat", "Comin' Through",
   Sigur Rós one-off singles) and silently drop out, per design.
8. Implementation note: setlist.fm `eventDate` is `dd-MM-yyyy` — sorting it
   lexicographically silently mangles chronology. Parse it.
9. The demoted setlist.fm tour-name field agreed with inference 8/10 times when
   it named an album — too sparse (51% present) to drive inference, as decided,
   but valuable as the display hint / sanity flag in the review UI.
