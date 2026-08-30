# touchneedle

Citiation tool that verifies the citations in a document are real,
accurately described, and consistently used.

Useful for both students and examiners who wish to corroborate citations.

It works standalone, or as a coding agent skill.

Most commercial citation checkers want a `.bib` file and check it against academic
databases. That covers journal articles but misses standards,
specifications, vendor documentation, and blog posts. In a lot of real
bibliographies, this is half the list.

So this tool parses a **prose reference list** (Harvard/author-date)
straight out of Markdown or `.docx`, and routes each entry to whichever
authority can actually confirm it.

## What it checks

**Existence and metadata** — scripted and deterministic:

| Entry carries | Checked against |
|---|---|
| arXiv id | arXiv API |
| DOI | Crossref |
| RFC number | IETF datatracker, falling back to rfc-editor |
| `draft-*` name | IETF datatracker, **including whether the cited revision is still current** |
| Quoted title in an academic venue | Crossref, then OpenAlex, by title |
| A URL and nothing else | Fetched live; page title compared with the cited title |

Entries with both an identifier and a URL get both, so a real paper behind a dead
link is still reported. Detects the fabricated-citation signature — a real title
carrying the wrong authors — as `MISMATCH`.

**Internal consistency** — every in-text citation resolves to a list entry, every
list entry is cited somewhere, and `2025a`/`2025b` suffixes are used unambiguously.

**Claim support** — the pass that needs reading rather than fetching. `claims`
emits a worklist pairing each in-text citation with the sentence making the claim
and a locator for the source; the model then reads each source and rules
SUPPORTED / PARTIAL / UNSUPPORTED / INACCESSIBLE. This catches the failure the
database checks cannot: a genuine source attached to a claim it does not make.

## Install

As a command-line tool:

```bash
pip install touchneedle
```

As a Claude Code skill:

```bash
git clone https://github.com/ncoleman/touchneedle ~/.claude/skills/touchneedle
```

Or as a Claude Code plugin:

```
/plugin marketplace add ncoleman/touchneedle
/plugin install touchneedle
```

There are no dependencies beyond Python 3.11+. `pandoc` is needed only for `.docx` input.

Then, in Claude Code: *"check the citations in thesis.docx"*.

## Use directly

```bash
touchneedle check thesis.docx --out report.md --json data.json
touchneedle claims thesis.docx --out claims.md
```

From a clone, without installing, that is `python3 scripts/touchneedle.py …` —
the same file either way.

Options: `--offline` (parse and cross-check only, no network), `--cache DIR`
(HTTP cache, 7-day TTL, so re-runs are nearly free), `--timeout N`, and
`--mailto you@example.com` for Crossref and OpenAlex's polite rate-limit pool.
`--mailto` is off by default and never inferred — it sends an address to third
parties.

`check` exits 2 when something needs attention, 0 when clean, so it drops into CI.

## Statuses

`MISMATCH` and `NOT_FOUND` are the ones that damage a submission. `LINK_DEAD` and
`STALE` need a fix but not a retraction. `PARTIAL`, `LINK_MOVED` and
`UNVERIFIABLE` are for a glance — notably, PDFs and JS-rendered pages land in
`PARTIAL` routinely, because no `<title>` can be read from them. A `PARTIAL` is a
limit of the check, not evidence against the citation.

## Limits

Author-date reference lists only — numeric styles (Vancouver, IEEE) are not
parsed. Page numbers, edition and publisher details are not checked.

Sources behind paywalls cannot be verified beyond their metadata record.

The list of in-text citations with no matching entry has expected false positives,
because a regex cannot distinguish `(Smith, 2024)` from `(ICLR 2023)`.

## Development

```bash
python3 -m unittest discover -s tests -t tests
```

See [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request.

The short version: standard library only, tests stay offline, and never let a coverage gap
report itself as a finding.

## Licence

MIT — see [LICENSE](LICENSE).
