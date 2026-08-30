# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
