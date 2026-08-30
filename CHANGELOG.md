# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] — 2026-08-30

First public release. The checker was written and used to verify the
bibliography of a real MSc dissertation before being extracted here.

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

[Unreleased]: https://github.com/OWNER/touchneedle/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/OWNER/touchneedle/releases/tag/v0.1.0
