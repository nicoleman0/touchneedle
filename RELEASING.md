# Releasing

## Swapping the placeholder URL

The public repository URL is not yet fixed, so it appears as the single token
`OWNER/touchneedle` everywhere it is needed. At publish time, replace it in
one pass:

```bash
grep -rl 'OWNER/touchneedle' . --exclude-dir=.git \
  | xargs sed -i 's|OWNER/touchneedle|<your-org>/touchneedle|g'
grep -rn 'OWNER' . --exclude-dir=.git    # must come back empty
```

It appears in `scripts/touchneedle.py` (`REPO_URL`, which is sent as part of
the HTTP User-Agent, so it should point somewhere a rate-limited API operator
can actually reach you), `pyproject.toml` (the project URLs PyPI renders on the
sidebar), `README.md`, `CHANGELOG.md` and the plugin manifests.

## Checklist

1. `python3 -m unittest discover -s tests -t tests` — all green.
2. `bash scripts/sync-plugin-skill.sh` — regenerates the plugin's bundled copy
   of the skill and fails if the version numbers have drifted apart.
3. Bump the version in all four places: `__version__` in
   `scripts/touchneedle.py`, `version:` in the `SKILL.md` frontmatter,
   `version` in `plugins/touchneedle/.claude-plugin/plugin.json`, and
   `version` in `pyproject.toml`. The sync script in step 2 fails if any of
   them disagree, so run it again after bumping.
4. Move the `Unreleased` entries in `CHANGELOG.md` under the new version, and
   update the link definitions at the bottom.
5. Tag: `git tag -a v0.1.0 -m 'v0.1.0'` and push the tag.

## Version numbering

The report format is part of the interface — people diff reports between runs
and grep them in CI. A change to statuses, to their meanings, or to the section
headings in the report is a breaking change and gets a major bump once this
reaches 1.0.

## Publishing to PyPI

Set up once, at [pypi.org/manage/account/publishing](https://pypi.org/manage/account/publishing/):
add a **pending publisher** for project `touchneedle`, owner `<your-org>`,
repository `touchneedle`, workflow `publish.yml`, environment `pypi`. Pending is
the right choice for a project that does not exist on PyPI yet — the first
successful upload creates it. Do the same on
[test.pypi.org](https://test.pypi.org/manage/account/publishing/) if you want a
rehearsal first.

This is trusted publishing: PyPI accepts a short-lived OIDC token minted by the
workflow, so there is no API token to store in repository secrets or to leak.

Then publishing is: push the tag, cut a GitHub release from it, and
`.github/workflows/publish.yml` does the rest.

### Before you tag

```bash
python -m build
python -m twine check dist/*
pip install --force-reinstall dist/touchneedle-*.whl
touchneedle check tests/fixtures/sample.md --offline --out /tmp/r.md
```

Confirm the installed console script works, not just the checkout — the entry
point is the part that silently breaks.

**A version number on PyPI is permanent.** It cannot be re-uploaded or
overwritten, only yanked and superseded. Get the tag right before you cut the
release.
