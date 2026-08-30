# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Footnote and endnote styles (Chicago notes-bibliography, MHRA). pandoc turns
  `.docx` footnotes into `[^n]` markers and definitions, which are now
  harvested before the reference list is looked for. A full note becomes an
  entry unless the bibliography already lists the work; a shortened note
  (`Greshake, "Not What," 24.`) links to the full citation it repeats — by
  surname and title prefix, since a similarity score alone would call a short
  title a poor match — and `Ibid.` repeats the previous note. A shortened note
  that cannot be linked is kept with an explicit caveat rather than silently
  merged. A notes-only document with no bibliography heading works: the notes
  are the reference list.
- MLA style: `Works Cited` lists, where the year trails the container behind
  a comma (`Smith, John. "Title." Journal, vol. 5, 2020, pp. 10-20.`) and an
  undated web source is legitimate. Undated entries are admitted only under a
  Works Cited or Bibliography heading, and only when they carry a quoted
  title, so the year gate stays shut for prose everywhere else. In-text
  author-page parentheticals — `(Smith 42)`, `(Smith and Jones 12)`,
  `(Greshake et al. 12)`, `(Smith 42; Lee 3)` — match by surname; a surname
  held by two entries is left unresolved rather than guessed. An access date
  is no longer mistaken for the publication year. `(Smith 2020)` stays an
  author-date citation, not MLA with page 2020.
- Numeric and bracketed citation styles: IEEE, Vancouver/AMA, ACM and numbered
  lists. Numbered entries (`[1] …`, `1. …`) are parsed with their number, in
  IEEE shape (initials-first authors, quoted title) and Vancouver shape
  (initials glued to the surname, unquoted title, `2020;15(2):123-45` year).
  In-text `[1]`, `[2, 5]`, `[5-7]`, `[1]–[3]`, pandoc superscripts (`^8^`, as
  converted from a `.docx`) and Unicode superscripts (`¹²`) all resolve to
  their entry by position; a marker beyond the list is reported unresolved.
  A numbered list of author-date entries still parses as author-date with the
  number attached. `--style numeric` forces the label when detection guesses
  wrong.
- For numeric styles the claim-support worklist collapses to one row per
  unique source-and-sentence pair, so a review article's sixty markers over
  twenty sources stay finishable.
- Chicago author-date reference lists: a year standing on its own between
  periods (`Smith, John. 2020. "Title." Journal.`) is now parsed as an entry,
  alongside the parenthesised-year author-date grammar. Full given names
  (`Smith, John`) are recognised as person authors, not organisations.
- APA/Harvard page locators: `(Smith, 2020, p. 5)` and `Smith (2020, pp. 4-6)`
  are now counted as citations and the locator is carried on the citation
  record. Trailing words that are not a locator still disqualify the match.
- `--style {auto,author-date,numeric,mla,notes}` on both subcommands, defaulting
  to auto-detection. The report and the JSON output name the style the run used
  and whether it was detected or forced.
- Fenced and inline code is now stripped before the in-text scan, so an array
  index like `arr[1]` or a signature like `foo(Date, 2020)` in code can no longer
  be counted as a citation. Markdown link definitions (`[1]: url`), inline
  links (`[1](url)`), reference uses (`[text][1]`) and exponents (`x^2^`) are
  likewise excluded from the numeric markers.

### Fixed

- Quoted titles now match when the punctuation sits inside the closing quote
  (`"Title." Journal`, the Chicago and IEEE convention) as well as outside it
  (`'Title', Journal`, the Harvard convention). Previously the Chicago form
  fell through to the unquoted-title fallback and kept its quotes in the title.
- Sentence context no longer swallows the sentence after a trailing citation
  marker (`… appears here.^8^`), and no longer leaks marker fragments into the
  next citation's context.

### Changed

- The version number has a single source of truth: `__version__` in
  `scripts/touchneedle.py`. `scripts/sync-plugin-skill.sh` now stamps it into
  the `SKILL.md` frontmatter and the plugin manifest instead of checking three
  hand-maintained numbers agree, so a release bump is one line plus the sync
  script.

## [0.1.0] — 2026-08-30

First public release. The checker was written and used to verify the
bibliography of a real MSc dissertation before being extracted here. Requires
Python 3.11 or newer — 3.9 reached end of life in October 2025 and current
mypy will not target it, so type checking was not possible while it was still
the floor.

### Added

- `check` — routes each reference entry to whichever authority can confirm it
  (arXiv, Crossref, OpenAlex, the IETF datatracker, or the live web) and reports
  what does not line up. Exits 2 when something needs attention, so it gates CI.
- `claims` — emits a worklist pairing each in-text citation with the sentence it
  supports and a locator for the source, for the reading pass that no database
  lookup can do.
- Prose reference-list parsing (Harvard/author-date) from Markdown and `.docx`,
  rather than requiring a `.bib` file. Standards, specifications and vendor
  documentation are checked alongside journal articles.
- Two-way cross-referencing: entries never cited, and citations with no entry.
- Ambiguous `2025a`/`2025b` suffix detection.
- On-disk HTTP cache with a 7-day TTL, so re-runs are nearly free.
- `--offline` mode for smoke-testing parsing with no network access.
- A test suite of 91 stdlib `unittest` cases that never touches the network.
- Three install paths off one file: `pip install touchneedle` for the console
  script, `git clone` into a skills directory, or `/plugin install`.
- ruff and mypy as CI gates, configured in `pyproject.toml` and installed from a
  `[dependency-groups]` dev group. A group cannot be pulled in by
  `pip install touchneedle[...]`, so the package still declares zero runtime
  dependencies. mypy runs with `strict = true` and is clean; the CI matrix runs
  3.11, 3.13 and 3.14.
- Dependabot for GitHub Actions.
- The version number is maintained in three places — `__version__` in
  `scripts/touchneedle.py`, `version:` in the `SKILL.md` frontmatter and
  `version` in the plugin manifest — with `pyproject.toml` reading it
  dynamically out of the module, so it cannot drift.

### Fixed

Both found while writing the test suite for this release:

- The one-entry-per-line fallback splitter no longer glues preamble — table
  rows, figure captions, stray headings — onto the front of the first real
  entry. Text before the first author-year line is now discarded as preamble.
- `citation_key` now splits `Smith & Jones` on the ampersand. It previously
  normalised the name first, which stripped the `&` and left `smith jones` as a
  single token, so an ampersand citation never keyed to its entry. Matching
  still succeeded through the surname fallback, but suffix-ambiguity detection
  silently skipped these citations.

### Known limits

- Author-date reference lists only. Numeric styles (Vancouver, IEEE) are not
  parsed.
- Page numbers, edition and publisher details are not checked.
- The list of in-text citations with no matching entry has expected false
  positives, because a regex cannot tell `(Smith, 2024)` from `(ICLR 2023)`.

[Unreleased]: https://github.com/nicoleman0/touchneedle/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/nicoleman0/touchneedle/releases/tag/v0.1.0
