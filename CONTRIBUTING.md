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

## Running the tests

```bash
python3 -m unittest discover -s tests -t tests
```

There is nothing to install first.

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
