# Claim support

`touchneedle claims DOC` produces a worklist for checking whether the sources
cited in a document actually support the claims made in the text.

Unlike `check`, this command does not decide whether a source supports a claim.
It identifies the claim and its citation so that the source can be read and
judged.

## Usage

From an installed copy:

```bash
touchneedle claims thesis.docx --out claims.md
```

From a clone, without installing:

```bash
python3 scripts/touchneedle.py claims thesis.docx --out claims.md
```

The output is a Markdown worklist containing each in-text citation, the
sentence containing the claim, and a locator for the cited source.

Each row can then be judged as `SUPPORTED`, `PARTIAL`, `UNSUPPORTED`, or
`INACCESSIBLE`.

`claims` does not make that judgement automatically. It prepares the evidence
so that the source can be read and assessed.