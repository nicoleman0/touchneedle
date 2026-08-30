# Releasing

## Where the project lives

GitHub (`ncoleman/touchneedle`) is canonical, because CI, PyPI trusted
publishing and the plugin marketplace all resolve against it. Codeberg is a
**pull mirror**, configured once in Codeberg's own UI (Settings -> Repository ->
Mirror Settings, "Pull from a remote repository"). Nothing in this repository
configures it, there is no second CI workflow to keep in step, and a push to
GitHub turns up on Codeberg without a release step.

Going the other way was considered and rejected: PyPI's trusted publishing only
mints OIDC tokens for GitHub Actions, so a Codeberg-canonical layout would mean
storing a long-lived PyPI API token in CI secrets.

The repository URL appears in `scripts/touchneedle.py` (`REPO_URL`, which goes
out in the HTTP User-Agent, so it has to point somewhere a rate-limited API
operator can actually reach you), `pyproject.toml` (the project URLs PyPI
renders on the sidebar), `README.md`, `CHANGELOG.md` and the plugin manifests.
If it ever moves, rewrite all of them in one pass:

```bash
grep -rl 'ncoleman/touchneedle' . --exclude-dir=.git \
  | xargs perl -pi -e 's|ncoleman/touchneedle|<new-owner>/touchneedle|g'
```

`perl -pi -e` rather than `sed -i`: the in-place flag takes a mandatory suffix
argument on BSD sed and an optional attached one on GNU sed, so any single sed
invocation is wrong on one platform or the other.

## Checklist

1. `python3 -m unittest discover -s tests -t tests` — all green.
2. `pip install --group dev && ruff check . && mypy scripts/touchneedle.py` —
   both clean. Dev-only tools; the package itself still has no runtime
   dependencies.
3. `bash scripts/sync-plugin-skill.sh` — regenerates the plugin's bundled copy
   of the skill and fails if the version numbers have drifted apart.
4. Bump the version in **three** places: `__version__` in
   `scripts/touchneedle.py`, `version:` in the `SKILL.md` frontmatter, and
   `version` in `plugins/touchneedle/.claude-plugin/plugin.json`.
   `pyproject.toml` is **not** one of them — it declares `dynamic = ["version"]`
   and reads `__version__` straight out of the module, so it cannot drift. Run
   step 3 again after bumping; it fails if the three disagree.
5. Move the `Unreleased` entries in `CHANGELOG.md` under the new version, and
   update the link definitions at the bottom.
6. Tag: `git tag -a v0.1.0 -m 'v0.1.0'` and push the tag.

## Version numbering

The report format is part of the interface — people diff reports between runs
and grep them in CI. A change to statuses, to their meanings, or to the section
headings in the report is a breaking change and gets a major bump once this
reaches 1.0.

## Publishing to PyPI

Set up once, at [pypi.org/manage/account/publishing](https://pypi.org/manage/account/publishing/):
add a **pending publisher** for project `touchneedle`, owner `ncoleman`,
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
