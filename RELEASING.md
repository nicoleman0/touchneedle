# Releasing

How a version of touchneedle gets from the repository to PyPI. Read it top to
bottom the first time; after that the checklist is the whole of it.

## Checklist

`main` is protected — "changes must be made through a pull request" — so the
version bump and the changelog move land as a branch and a PR like any other
work, and the tag is cut from `main` after that merges. A direct push is
rejected with `GH013`, after the commit already exists locally; move it to a
branch rather than trying to force it through.

Which installer the commands below use depends on how the checkout's
virtualenv was made. A `uv venv` has no `pip` in it, so `python -m pip` and
`python -m build` both fail with `No module named pip`; the `uv` forms work
either way and are given first.

1. `python3 -m unittest discover -s tests -t tests` — all green.
2. `uv pip install --group dev` (or `pip install --group dev`), then
   `ruff check . && mypy scripts/touchneedle.py` — both clean. Dev-only tools;
   the package itself still has no runtime dependencies.
3. `bash scripts/sync-plugin-skill.sh` — regenerates the plugin's bundled copy
   of the skill and stamps the current `__version__` into the `SKILL.md`
   frontmatter and the plugin manifest.
4. Bump `__version__` in `scripts/touchneedle.py` — the single source of
   truth. `pyproject.toml` reads it straight out of the module
   (`dynamic = ["version"]`), and step 3's script stamps it into the `SKILL.md`
   frontmatter and the plugin manifest, so nothing else is edited by hand. Run
   step 3 again after bumping to propagate it.
5. Move the `Unreleased` entries in `CHANGELOG.md` under the new version, and
   update the link definitions at the bottom.
6. Tag from `main`, after the pull request has merged:
   `git tag -a vX.Y.Z -m 'vX.Y.Z'`, then push the tag.

## Version numbering

The report format is part of the interface — people diff reports between runs
and grep them in CI. A change to statuses, to their meanings, or to the section
headings in the report is a breaking change and gets a major bump once this
reaches 1.0.

## Publishing to PyPI

Set up once, at [pypi.org/manage/account/publishing](https://pypi.org/manage/account/publishing/):
the publisher is project `touchneedle`, owner `nicoleman0`, repository
`touchneedle`, workflow `publish.yml`, environment `pypi`. It is already
configured and needs no attention unless the workflow file, the repository or
the owner is renamed. A project that does not yet exist on PyPI is registered as
a *pending* publisher instead, and the first successful upload creates it.

This is trusted publishing: PyPI accepts a short-lived OIDC token minted by the
workflow, so there is no API token to store in repository secrets or to leak.

Then publishing is: push the tag, cut a GitHub release from it, and
`.github/workflows/publish.yml` does the rest.

### Before you tag

```bash
uv build                                    # or `python -m build`
uvx twine check dist/*                      # or `python -m twine check dist/*`
uv run --no-project --with ./dist/touchneedle-*.whl \
  touchneedle check tests/fixtures/sample.md --offline --out /tmp/r.md
```

Confirm the installed console script works, not just the checkout — the entry
point is the part that silently breaks. `uv run --with` builds a throwaway
environment for the check, which is why it is preferred over
`pip install --force-reinstall`: the latter leaves the release wheel installed
in the working virtualenv, where it shadows the checkout on the next run.

### After the release

The publish workflow finishing is not the same as the release being installable.
PyPI's simple index updates first; the JSON API and resolvers such as `uv` and
`pip` can lag it by a few minutes, so a `No solution found` for the version you
just published means the CDN has not caught up, not that the upload failed.
Confirm with the index, then install:

```bash
curl -s https://pypi.org/simple/touchneedle/ | grep touchneedle-X.Y.Z
uv run --no-project --with touchneedle==X.Y.Z touchneedle --help
```

**A version number on PyPI is permanent.** It cannot be re-uploaded or
overwritten, only yanked and superseded. Get the tag right before you cut the
release.
