# Project Brief — Tourlist (working title)

**Status:** Draft v0.1
**Last updated:** 2026-06-11
**Owner:** [you]

## Problem

I have 200–300 concert attendances recorded on setlist.fm and a personal music
library of albums I own (MP3s in iTunes, sourced from CDs, Bandcamp, etc. —
deliberately not streaming). There is no way to turn that gig history into a
playlist that reflects what each band was actually touring when I saw them.
Doing it by hand means cross-referencing setlists, tour/album associations,
and my own library for hundreds of shows.

## Vision

A self-hosted web app that takes a setlist.fm username, walks me through my
concert history, works out which album each band was touring for, lets me
record which albums I own, applies a set of song-selection rules, and outputs
a chronological tracklist — one song per concert — that I can use to quickly
build the playlist manually in iTunes.

The playlist is a *document*, not an integration. The app never touches
iTunes, Spotify, or any music service. It produces a text list:
`artist / album / track number / song title`, ordered by attendance date.

## Core concepts

- **Attendance** — a concert I (or anyone) went to, pulled from setlist.fm.
  Swappable input: any setlist.fm username can be used (defaults to mine).
- **Ownership library** — the persistent, accumulating record of which albums
  I own. Global and singular: it is always *my* library, regardless of whose
  attendance is being processed. Written once, reused forever.
- **Toured album** — the album a band was promoting at the time of a given
  show. Inferred from setlist/tour data; not always knowable.
- **Selection rules** — the logic that picks one song per concert from the
  setlist (or elsewhere), handling edge cases: unknown setlist, tour not
  associated with an album, album not owned, etc. Rules to be fully
  specified in the PRD.

## V1 scope

1. Input a setlist.fm username (default: mine) and fetch full attendance
   history. Responses cached locally; the app must respect setlist.fm rate
   limits and not re-fetch on every load.
2. A review queue UI listing each concert with:
   - show date / venue
   - artist
   - the inferred toured album, with a control to mark it owned
   - expandable discography (via MusicBrainz) to mark other albums owned
   - the suggested song from the setlist (or fallback per rules)
3. Persistent state: ownership flags and per-concert review status survive
   across sessions. Reviewing ~250 concerts will take multiple sittings.
4. Generate playlist: an explicit action in the UI that produces a clean,
   chronologically ordered (by attendance date) text list, one song per
   concert, with each entry containing in this order:
   - Artist
   - Album
   - Track number
   - Song title

   The list is the deliverable — copyable/saveable text used to hand-build
   the playlist in iTunes.

## Explicitly out of scope (v1)

- Writing playlists into iTunes or any music service.
- iTunes `Library.xml` import to seed ownership (planned v2: bulk-write into
  the same ownership store; v1 is manual entry only).
- Multi-user accounts / auth. Single-user tool; "anyone can use it" means
  anyone can self-host it, not log into my instance.
- Public hosting, polish, mobile support. Runs locally or on temporary
  hosting for personal use.

## Future ideas (backlog, not commitments)

- iTunes library import (ownership seeding + fuzzy matching via MusicBrainz
  canonical names).
- "To buy" list: toured albums I don't own, surfaced as a shopping list.
- Generating playlists from other people's attendance against my library.

## Constraints

- External dependencies: setlist.fm API (requires API key) and MusicBrainz
  API (rate-limited, requires polite usage / user agent).
- Personal project: optimise for simplicity and fun, not scale.
- All docs, tickets, wires, and code live in a single repo.

## Success criteria (v1 is done when…)

I can plug in my setlist.fm username, work through my full attendance
history across multiple sessions, record album ownership as I go, and export
a chronological artist/album/track/title list covering every reviewed
concert — with every edge case either resolved by a rule or clearly flagged.

## Open questions (for the PRD)

1. The selection rules themselves: precedence order when setlist is unknown,
   tour ≠ album, album unowned, song not on the toured album, multiple
   shows on the same tour (repeat songs allowed?).
2. How is the toured album actually inferred? setlist.fm tour name →
   MusicBrainz release matching needs a defined strategy and a manual
   override.
3. Multiple attendances of the same artist: does ownership review get
   skipped (already answered: yes, persistent), and should song suggestions
   avoid repeats across those shows?
4. Tech stack — deferred to the Technology Approach doc.
