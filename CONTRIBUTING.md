# Contributing

Thanks for looking. This is a small, deliberately boring codebase: one Python
file, no dependencies, and a test suite that runs in a fifth of a second.

## Ground rules

**Standard library only.** The install path is `git clone` into a skills
directory. Every dependency added is a reason for someone not to use it. If a
change seems to need a package, it almost certainly needs a smaller change
instead.

**Tests never touch the network.** The suite must pass on a machine with no
route out. Construct `Fetcher(dir, offline=True)`, or plant records in the cache
directly — `tests/test_verify.py` shows both. A test that makes a real request
is a flaky test and will be rejected.

**A `PARTIAL` is not a finding.** The distinction the whole tool rests on is
between *this citation is wrong* and *I could not check this citation*. Anything
that blurs the two — a status that overstates confidence, a report line that
reads as an accusation when it is a coverage gap — is a bug, however useful it
looks.

## Sending a change

Work from a branch, not from your fork's `main`. A pull request opened from
`main` cannot be updated without moving your fork's default branch, and it
tangles the next change you send with this one.

Pull request titles follow [Conventional Commits](https://www.conventionalcommits.org/):

```
fix: pin UTF-8 for stdout and pandoc output on legacy code pages
feat: add --version flag to CLI
docs: document the sync gate
test: cover the ambiguous-suffix splitter
```

The title carries further than it looks. Pull requests are squash-merged, so it
becomes the subject line of the commit that lands on `main`, and the branch's
own commit messages are folded into that commit's body. Those should be legible,
but the title is the one that has to be right. History from before this was
written down does not follow it — the rule starts here rather than being
applied backwards.

`fix:` and `feat:` are the two that carry weight, because they decide whether
the next release is a patch or a minor version. `docs:`, `test:`, `refactor:`,
`chore:` and `ci:` cover changes no changelog entry needs to mention.

Six gates run on a pull request, and all six must be green:

| Gate | What it runs | Described in |
| --- | --- | --- |
| `test` | the suite, on Linux, macOS and Windows | [Running the tests](#running-the-tests) |
| `lint` | `ruff check .` and `mypy scripts/touchneedle.py` | [Code style](#code-style) |
| `sync` | regenerates the plugin's bundled copies, fails if they are stale, and runs the copy | [The plugin's bundled copy](#the-plugins-bundled-copy) |
| `build` | builds the wheel, and checks the installed `touchneedle` command reports the same version as the source | |
| `pandoc` | the suite again with pandoc installed, so the conversion tests stop skipping | |
| `pr-title` | the title against the pattern above | this section |

`pandoc` exists because the conversion tests guard themselves with
`skipUnless(shutil.which("pandoc"))`, so that nobody is made to install pandoc
to run the suite. Without a job that has it, those tests skip everywhere and
report green, which reads as coverage and is not.

## Running the tests

```bash
python3 -m unittest discover -s tests -t tests
```

There is nothing to install first.

## Code style

```bash
uv pip install --group dev  # ruff and mypy, dev-only; `pip install --group dev`
ruff check .                # works too, in a virtualenv that has pip in it
mypy scripts/touchneedle.py
```

Both are gates in CI and both must be clean. They are a dependency *group*, not
an optional extra, so `pip install touchneedle` can never pull them in -- the
zero-dependency promise above is unaffected.

`ruff format` is deliberately not used. `build_report()` and `build_claims()`
assemble Markdown out of hand-aligned list literals, and the formatter reflows
them into a diff nobody can review. Wrap long lines by hand.

Two things in the parser look like style problems and are not. The regexes that
build `HEADING`, `BARE_HEADING` and the heading-level search use string
concatenation rather than an f-string, because their patterns contain `{1,4}`
quantifiers that an f-string would require doubling -- get one wrong and the
pattern breaks silently, with the tests still passing on the fixture. Leave them
as concatenation.

## The plugin's bundled copy

`scripts/touchneedle.py` and `SKILL.md` are the sources. `plugins/touchneedle/`
carries generated copies of both, because `SKILL.md` invokes the checker by a
path relative to itself and the script therefore has to travel with it. After
editing either source, run:

```bash
bash scripts/sync-plugin-skill.sh
```

and commit whatever it changes. CI regenerates the copies and fails if anything
differs, which is the usual reason an otherwise green pull request goes red.

## Adding a source of authority

Verification routes on what the entry carries — see `verify()`. A new authority
is a `verify_*(ref, fetcher) -> bool` function that returns `True` when it
reached a verdict and `False` when the lookup itself failed, so the next route
gets a turn. Set status through `check_metadata()` rather than by hand, so
title, author and year comparison stay consistent across sources.

Please add fixture-backed tests for the new routing, and be a good citizen of
whatever API you are calling: it goes through `Fetcher`, which caches for seven
days and rate-limits to one request every 0.4 s.

## Changing the parser

`tests/fixtures/sample.md` is the contract. It contains, on purpose, a decoy
`References management` heading, a cross-reference that looks like a citation
(`(Table 3, 2024)`), an `(Accessed: …)` date, an entry nobody cites, and a
citation with no entry. If you change parsing behaviour, change the fixture and
say why in the pull request — a diff to the expected counts in
`tests/test_citations.py` should always be a deliberate decision.

## Reporting a bad result

The most useful bug report is the reference entry itself, verbatim, plus what
the tool said and what the right answer is. Reference lists are gloriously
inconsistent and most parser bugs are one real-world entry that nobody imagined.
