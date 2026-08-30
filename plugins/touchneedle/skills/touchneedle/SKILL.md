---
name: touchneedle
version: 0.2.1
description: Verify that every citation and reference in a document is real, accurately described, and consistently used. Checks reference entries against arXiv, Crossref, OpenAlex, the IETF datatracker and the live web; cross-checks in-text citations against the reference list in both directions; and drives a claim-support pass that reads each source to confirm it actually backs the sentence citing it. Handles author-date (Harvard, APA, Chicago), numeric (IEEE, Vancouver), MLA, and footnote (Chicago notes, MHRA) citation styles in Markdown or .docx. Use when asked to check citations, verify references or a bibliography, find hallucinated or fabricated citations, check for dead links in a reference list, or confirm sources say what a draft claims they say.
---

# touchneedle

Verifies a prose reference list in Markdown or `.docx`, in any of the four
style families a real document uses: author-date (Harvard, APA, Chicago
author-date), numeric (IEEE, Vancouver/AMA), MLA, and footnote styles (Chicago
notes, MHRA). The style is auto-detected; `--style` forces it when detection
guesses wrong. Two passes, deliberately separated:

- **Pass 1 — existence and metadata.** Deterministic, scripted, no judgement.
  Does the source exist, and does the entry describe it correctly?
- **Pass 2 — claim support.** Requires reading. Does the source actually support
  the sentence that cites it?

Pass 1 catches fabricated and garbled references. Pass 2 catches the more common
and more damaging failure in a real draft: a genuine source attached to a claim
it does not make.

## Pass 1 — run the script

```bash
python3 scripts/touchneedle.py check <document> --out citation-report.md --json citation-data.json
```

`<document>` may be `.md` or `.docx` (`.docx` is converted with pandoc, which
must be on PATH). Options:

- `--offline` — parse and cross-check only, no network. Use to smoke-test parsing.
- `--style {auto,author-date,numeric,mla,notes}` — the citation style, default
  `auto` (detected from the reference list and the in-text markers). Force one
  when detection guesses wrong; parsing itself is per-entry, so a forced style
  mostly changes the in-text finders and the report wording.
- `--mailto you@example.com` — sent to Crossref and OpenAlex for their polite
  rate-limit pool. Optional and off by default. **Never pass the user's address
  without asking them first** — it goes to third-party services.
- `--cache DIR` — HTTP cache, default `.touchneedle-cache`, 7-day TTL. Re-runs are
  nearly free, so iterate freely.

Exit status is 2 when something needs attention, 0 when clean.

Routing is by what the entry carries, because no single database covers a mixed
bibliography: arXiv id → arXiv API; DOI → Crossref; RFC number → IETF datatracker,
falling back to rfc-editor; `draft-*` → datatracker, **including whether the cited
revision is still current**; quoted title in an academic venue → Crossref then
OpenAlex title search; anything else with a URL → fetch it and compare the page
title. Entries with an identifier *and* a URL get both, so a live paper with a
dead link is still reported.

### Reading the report

Statuses, worst first:

| Status | What it means | What to do |
|---|---|---|
| `MISMATCH` | Found a record that **disagrees** with the entry | Highest priority. Real title with the wrong authors is the classic fabricated-citation signature |
| `NOT_FOUND` | Searched the right places, found nothing | Likely fabricated, or the title is badly wrong |
| `LINK_DEAD` | URL does not resolve, or resolves to an error page | Replace the URL or add an archive link |
| `STALE` | Cited draft revision superseded | Confirm the cited text survived into the current revision |
| `PARTIAL` | Found, loose match | Eyeball it. PDFs and JS-rendered pages land here routinely |
| `LINK_MOVED` | Redirects elsewhere | Usually fine; update the URL |
| `UNVERIFIABLE` | Nothing checkable in the entry | Add a DOI or URL |
| `VERIFIED` | Matched an authoritative record | — |

Do not report a `PARTIAL` or `UNVERIFIABLE` as if it were a problem found. It is
a gap in what the script could reach, not evidence against the citation. Say
which it is.

The cross-reference section lists entries never cited and in-text citations
with no entry. **The second list has expected false positives** — the shape
differs by style (a parenthesised year like `(ICLR 2023)` in author-date, a
bracketed figure reference like `[12]` in numeric, a name-page pair in prose
in MLA), and the report names the shape to expect. Filter it before showing it
to the user. In a notes document, the list means a marker with no definition
or a note that could not be linked — both are real problems, not noise.

## Pass 2 — claim support

```bash
python3 scripts/touchneedle.py claims <document> --out claims-worklist.md
```

Produces one entry per in-text citation — for numeric styles, one per unique
source-and-sentence pair, so a heavily cited review stays finishable — with
the surrounding sentence and a locator for the source. Then, for each row:

1. Fetch the source (WebFetch for a URL; the arXiv abs page for an arXiv id).
2. Read enough to judge the specific claim — not the abstract alone if the claim
   is specific.
3. Record a verdict in the worklist:
   - `SUPPORTED` — source states or clearly implies the claim
   - `PARTIAL` — supports a weaker version; note the gap precisely
   - `UNSUPPORTED` — source does not support it, or says something different
   - `INACCESSIBLE` — could not read it (paywall, dead link, no full text)

**Never guess.** If the source cannot be read, the verdict is `INACCESSIBLE`, not
an inference from the title. A fabricated verdict here is worse than no pass at
all, because it launders an unchecked citation as checked.

Work in batches of about ten and save progress as you go — a full pass over a
long bibliography will not fit in one context.

## Reporting back

Lead with the count that matters: how many entries need attention, out of how
many. Then the `MISMATCH` and `NOT_FOUND` entries individually with the evidence,
since those are the ones that damage a submission. Group the rest.

Where the document is built from a `.docx` master, say so: fixes must go into the
Word file by hand, because any extracted Markdown is a build intermediate that
the next build overwrites.

Be straight about coverage. State how many entries were verified against an
authoritative record, how many only against a live web page (weaker evidence —
it shows a page exists at that URL with a matching title, not that the work is
what the entry claims), and how many could not be checked at all.
