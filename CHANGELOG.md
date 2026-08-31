# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.0] — 2026-08-31

Windows. A reference list carrying a name outside the console's code page
brought the run down, and a `.docx` came back mangled, which between them cover
most of what the tool is pointed at on that platform. Both are fixed here, and
both are now covered by tests that fail without the fix.

### Added

- `--version` prints the version and exits. `__version__` in the module is
  already the single source of truth, so the flag reads it rather than
  restating it.

### Fixed

- A report is no longer written in whatever encoding the locale happens to
  offer. `stdout` and `stderr` are set to UTF-8 at startup, so a name the
  console's code page cannot represent no longer ends the run with a
  `UnicodeEncodeError`. cp1252 covers `Müller` and `Sørensen`, which is why
  this went unnoticed for so long; a Greek or Polish name did not survive it.
- A `.docx`, `.odt` or `.rtf` converted through pandoc is read as UTF-8 rather
  than in the locale's encoding. pandoc writes UTF-8 whatever the locale says,
  so on a Windows checkout the conversion came back mangled or raised outright
  — on the input format the tool is most often pointed at.

## [0.2.2] — 2026-08-31

Every entry below is the same defect: the checker reporting a coverage gap of
its own as a finding about someone's citation. Each was found by running the
tool over real bibliographies rather than over the fixtures, and each was
confirmed against the upstream API before being called a bug.

### Changed

- `--mailto` is documented as what it is: OpenAlex rate-limits anonymous search
  when it is busy, and OpenAlex is the fallback covering the venues Crossref
  does not index, so without a contact address those entries come back
  unchecked rather than verified. It stays off by default and is still never
  inferred.

### Fixed

- A run in which authorities could not be reached no longer reads as a pass.
  The report counts the entries nothing was decided about, says so directly
  under the summary, and points at `--mailto` when no address was supplied.
  `UNVERIFIABLE` no longer claims there was "nothing checkable in the entry"
  when the truth is that the check could not be run.
- A record found by title search is no longer treated as the cited work. A
  search returns neighbours, and `title_score` gives a containing title full
  marks, so "Is Attention All You Need?" scored 1.00 against the paper it is
  asking about and "Attention is all you need" was reported as disagreeing with
  a 2025 book chapter. A candidate now has to carry the cited surname as well
  before it earns a metadata comparison, candidates are ranked by that
  corroboration ahead of title score so a wrong exact-scoring hit cannot win on
  arrival order, and the second index is consulted whenever the first has not
  produced the work. `MISMATCH` is left to the routes that fetch a work by its
  identifier, where the record is the cited work by construction; a search that
  finds nothing convincing reports not found and names the closest candidate.
  A date that disagrees on a searched record is advisory, since an index holds
  reprints, later editions and duplicate entries.
- An authority that could not be reached no longer produces a finding. A rate
  limit, a timeout or a 5xx while asking Crossref, OpenAlex, the IETF
  datatracker or the live web is a failure of our side of the conversation and
  says nothing about the citation, but it was being reported as `NOT_FOUND`,
  `MISMATCH` or `LINK_DEAD` — and taking the exit status to 2 with it. Only a
  server that answers 404 or 410, or a hostname that does not resolve, is now
  treated as evidence. A route that cannot reach its authority returns no
  verdict, names what went unanswered, and lets the next route try; where one
  source answered and the other did not, a disagreement is recorded as
  unconfirmed rather than wrong. Observed against OpenAlex, which rate-limits
  anonymous search under load: two real papers were reported as disagreeing
  with the record because the second opinion never arrived.
- The report no longer claims a source was searched when it was not: the
  "no close title match" note now names only the authorities that answered.
- An arXiv DOI (`10.48550/arXiv.2406.04093`) now routes to the arXiv API rather
  than to Crossref. arXiv registers its DOIs with DataCite, so Crossref has no
  record of them and every preprint cited in the form doi.org recommends came
  back `NOT_FOUND` — a coverage gap reporting itself as a finding, against real
  and correctly described papers, and an exit status of 2 with it. Found by
  running the checker over a machine-drafted bibliography, where the form is
  ubiquitous: five of eight entries were accused, and all five were real.

## [0.2.1] — 2026-08-30

Packaging and documentation only; the checker itself is byte-for-byte 0.2.0.
Cut so the corrected README and the widened keyword set reach the PyPI page,
which renders whatever the last upload carried.

### Changed

- README leads with what the tool is for and names the fabricated-citation case
  in the first forty words, that being the snippet search engines and the PyPI
  page display. Corrects a typo in the opening line.
- Added a `What it produces` section with a real excerpt, and
  `docs/example-report.md` with the full report, generated live against the test
  fixture rather than written by hand.
- Badges for the PyPI version, the supported Python versions, CI and the licence.
- Keywords extended across `pyproject.toml`, `.claude-plugin/marketplace.json`
  and the plugin manifest; classifier list widened; a `Documentation` URL added
  to the project URLs PyPI renders.

## [0.2.0] — 2026-08-30

Citation styles beyond Harvard/author-date: numeric (IEEE, Vancouver/AMA),
MLA, Chicago author-date, and footnote styles (Chicago notes, MHRA), with
auto-detection and a `--style` override. The verification layer was already
style-agnostic, so the work is all in parsing and matching; four new fixtures
pin each family's contract.

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
- A citation marker following an abbreviation (`Smith et al.[3]`, `Fig. 4.[1]`)
  no longer blanks or truncates the claim sentence in the worklist: the
  trailing-marker test now carries the same abbreviation guards the sentence
  splitter does.
- Two reference entries that no grammar could parse no longer collapse onto one
  key, which had the report naming the wrong source for a numbered citation.
- Footnote definitions are scanned for citations in every style, not only in
  notes documents. Harvesting them out of the text was dropping the citations
  inside them everywhere else.
- An access date written bare at the end of an entry (`Accessed 3 Mar. 2021.`),
  not only the parenthesised Harvard form, is lifted out before any grammar
  looks for a year.
- A footnote is linked to a bibliography entry by surname token rather than
  substring, so `Lee` no longer matches `Leeson`, and an apostrophised surname
  (`O'Brien`) survives the note parser intact.
- A year inside a quoted title is no longer taken as the publication year, and
  a suffixed year (`2020a.`) is no longer lost, which had collapsed the a/b
  entries onto one key.
- Bracketed numbers are only citations in a numeric document; elsewhere `[3]`
  is a figure or a table, and `--style` now suppresses them as documented.
- Vancouver/AMA entries with the NLM month-qualified date (`2020 Jan;15(2)`)
  parse as Vancouver instead of falling through and losing their title.
- An entry no grammar claimed is no longer verified as a paper, which reported
  a parse gap as NOT_FOUND and failed the run.
- Two adjacent numeric markers (`[1][2]`) both count; only the second was found.
- A footnote number is no longer written into a reference's list position,
  where it could shadow a numbered bibliography entry and mislabel the report.

### Changed

- The version number has a single source of truth: `__version__` in
  `scripts/touchneedle.py`. `scripts/sync-plugin-skill.sh` now stamps it into
  the `SKILL.md` frontmatter and the plugin manifest instead of checking three
  hand-maintained numbers agree, so a release bump is one line plus the sync
  script.

### Known limits

- MLA narrative citations that end in a bare page number (`Smith argues the
  point (42)`) are not matched — a bare parenthesised number cannot be told
  from any other parenthesised digit.
- An entry no grammar claims is kept with its raw text and an explicit
  "could not parse" note rather than dropped or guessed at.
- A two-word organisation inside a footnote (`World Bank, "Report,"`) can be
  read as a natural-order person, which weakens the author check for that
  entry; the title check still applies.

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

[Unreleased]: https://github.com/nicoleman0/touchneedle/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/nicoleman0/touchneedle/releases/tag/v0.3.0
[0.2.2]: https://github.com/nicoleman0/touchneedle/releases/tag/v0.2.2
[0.2.1]: https://github.com/nicoleman0/touchneedle/releases/tag/v0.2.1
[0.2.0]: https://github.com/nicoleman0/touchneedle/releases/tag/v0.2.0
[0.1.0]: https://github.com/nicoleman0/touchneedle/releases/tag/v0.1.0
