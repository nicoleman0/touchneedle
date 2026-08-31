# touchneedle (Claude Code plugin)

Verifies that the citations in a document are real, accurately described, and
consistently used — including the fabricated-citation signature an AI-drafted
bibliography produces: a real title carrying the wrong authors, or a plausible
reference to a paper that does not exist.

Reads a prose reference list out of Markdown or `.docx` in four style families
(author-date, numeric, MLA, footnote), checks each entry against whichever
authority can confirm it — arXiv, Crossref, OpenAlex, the IETF datatracker or
the live web — and cross-checks the in-text citations against the list in both
directions.

## Install

```
/plugin marketplace add nicoleman0/touchneedle
/plugin install touchneedle
```

## Use

Ask in plain words:

> check the citations in thesis.docx

The skill runs two passes, deliberately separated. The first is scripted: it
fetches records and compares fields, so it returns the same answer every run.
The second is the part a script cannot do — it reads each cited source and rules
on whether the source supports the sentence citing it.

`.docx` input needs `pandoc` on PATH. Nothing else is required beyond Python
3.11+, and the plugin installs no dependencies.

## Without Claude Code

The same file runs as a command-line tool, and that is the primary way to use
it:

```bash
pip install touchneedle
touchneedle check thesis.docx --out report.md
```

## More

Source, an example report, and the full option reference:
<https://github.com/nicoleman0/touchneedle>. MIT licensed.
