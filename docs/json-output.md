# JSON output

`touchneedle check document.md --json data.json` writes a UTF-8 JSON object alongside
the Markdown report. `claims` does not offer `--json`.
The object contains parsed entries, citation matches, and verification results;
it does not contain the Markdown report or the process exit code.

This describes the current output, not a separately versioned JSON schema.
Record `touchneedle --version` with saved results, allow additional fields in
consumers, and do not parse the wording of `notes` or `evidence` as an API.

## Top-level fields

| Field | Type | Meaning |
| --- | --- | --- |
| `style` | string | Effective document citation style: `author-date`, `numeric`, `mla`, or `notes`. With `--style auto`, this is the detected style, not `auto`. |
| `references` | array of objects | Reference-list entries and, for notes documents, references collected from notes. Each object has the fields below. |
| `citations` | array of objects | Detected in-text citations, including those with no matching reference entry. Each object has the fields below. |

## Reference fields

String fields use `""` when no value was parsed, unless a different default is
shown. Lists use `[]` when empty; absent values are not encoded as `null`.
Parsed bibliographic fields describe what the document says, not corrected
metadata fetched from an authority.

| Field | Type | Meaning and empty/default behavior |
| --- | --- | --- |
| `raw` | string | Original reference-entry text supplied to the parser. |
| `key` | string | Internal reference-matching key, generally normalized name plus year/suffix, with a fallback for unparsed entries. Use it to associate citations within this result, not as a globally unique or persistent identifier. |
| `number` | integer | Numbered-list marker; `0` when there is none. |
| `style` | string | Entry's successful parse strategy: `author-date`, `ieee`, `mla`, `vancouver`, or `chicago-ad`; `""` if none fit. This can differ from the top-level document style. |
| `name` | string | First author's surname or the organization's name; empty if unparsed. |
| `is_org` | boolean | Whether `name` is treated as an organization rather than a person. Also `true` for an unparsed entry; it does not establish that an organization was identified. |
| `year` | string | Parsed publication year, such as `"2024"`; empty if unavailable. |
| `suffix` | string | Disambiguating letter, such as `"a"` in `2024a`; empty if absent. |
| `title` | string | Parsed title, or fallback entry text if no citation grammar fit. It is not necessarily an authority's title. |
| `container` | string | Remaining text after the title, which may include a journal, publisher, URL, or other details; empty if absent. |
| `url` | string | URL extracted from the entry; empty if absent. Redirect destinations are recorded in `notes`, not substituted here. |
| `doi` | string | DOI extracted from the entry; empty if absent. |
| `arxiv` | string | arXiv identifier extracted directly or from an arXiv DOI; empty if absent. |
| `rfc` | string | RFC number as a string; empty if absent. |
| `draft` | string | Internet-Draft name, without its trailing revision; empty if absent. |
| `draft_rev` | string | Cited draft revision, such as `"15"`, without the leading hyphen; empty if absent. |
| `accessed` | string | Access-date text extracted from the entry; empty if absent. |
| `kind` | string | Verification routing category: `arxiv`, `doi`, `rfc`, `ietf-draft`, `paper`, `web`, or `unknown`. It is not a verification result. |
| `status` | string | Verification outcome from the status table below; initially `UNVERIFIABLE`. |
| `unchecked` | boolean | An authority lookup failed, with details in `notes`. Another route may still produce a verdict, so inspect `status` as well. Defaults to `false`; offline mode also leaves it `false`. It is not a general test for whether verification succeeded. |
| `notes` | array of strings | Explanations, caveats, mismatches, and redirects; empty when none were recorded. Human-readable, not structured findings. |
| `evidence` | array of strings | Retrieved metadata/page-title summaries supporting the outcome; empty when none were recorded. Human-readable, not a full copy of the retrieved records. |
| `cited_by` | array of strings | Forms of citations matched to this entry, such as `narrative` or `numeric`. Repeated forms can occur. `[]` means no detected citation matched the entry, not that the reference itself is invalid. |

## Citation fields

| Field | Type | Meaning and empty/default behavior |
| --- | --- | --- |
| `name` | string | Parsed author/organization text; empty for numeric or note markers. |
| `year` | string | Parsed year; empty for forms without one, such as numeric and MLA citations. |
| `suffix` | string | Year-disambiguation letter; empty if absent. |
| `form` | string | Detection form: `parenthetical`, `narrative`, `numeric`, `note`, or `mla`. |
| `context` | string | Surrounding document text to help locate and review the citation. |
| `key` | string | Matching `Reference.key`, or `""` when no entry was matched. An empty key is a cross-reference warning, not proof that the citation is fabricated: detection has false positives and ambiguous matches. |
| `number` | integer | Numeric citation or footnote marker; `0` for forms without one. |
| `page` | string | Parsed page/page-range locator, including MLA locators; empty if absent. Page numbers are not verified against the source. |

## Interpreting statuses

**`PARTIAL` and `UNVERIFIABLE` describe limits of the check, not evidence that
a citation is wrong.** Keep them separate from findings in dashboards and CI
summaries. `VERIFIED` is also limited to the checks performed; it does not
verify page numbers, editions, every bibliographic field, or the document's claims.

| Status | What the result supports | Suggested handling |
| --- | --- | --- |
| `MISMATCH` | Retrieved metadata or a page title disagrees with the cited entry. | Review `notes` and `evidence` and correct the mismatch. |
| `NOT_FOUND` | A consulted authority returned no matching record or identifier. It is not a verdict about all possible sources. | Check the identifier and entry against the named authority. |
| `LINK_DEAD` | A cited link appears dead, including a definitive error response or an error page. The work may still exist elsewhere. | Repair the link; do not infer that the work is fabricated. |
| `STALE` | The cited Internet-Draft revision differs from the current revision. | Check whether the intended revision is correct and whether the cited text survived. |
| `PARTIAL` | Some information was reached, but it was insufficient for a confident check. PDFs, JavaScript pages, and security interstitials commonly cause this. | Label as incomplete verification and review manually; do not count it as a wrong citation. |
| `LINK_MOVED` | A web page otherwise checked out, but redirected to a different URL. | Review the redirect and consider updating the URL. |
| `UNVERIFIABLE` | No verification verdict was reached, for example because the run was offline, a source was unreachable, or no supported identifier was available. | Label as unverified and inspect `notes`; do not count it as a wrong citation. |
| `VERIFIED` | The metadata or page-title checks performed by the selected route passed. | Retain the evidence and caveats; this is not a guarantee of complete bibliographic or factual correctness. |

`MISMATCH`, `NOT_FOUND`, `LINK_DEAD`, and `STALE` are the verification findings
grouped in `PROBLEM_STATUSES`.
Cross-reference warnings, such as an empty citation `key` or an uncited reference,
are separate from these verification statuses. Do not use exit status `0` to
mean every entry was checked: an entirely offline run can return `0`.

## Worked example

From a clone, generate results from the bundled fixture without contacting any
authority (an installed CLI can use `touchneedle` instead of the script path):

```sh
python3 scripts/touchneedle.py check tests/fixtures/sample.md --offline --out report.md --json data.json
```

Then use `jq` to list findings, incomplete checks, and unresolved citation matches
separately:

```sh
jq -r '.references[] | select(.status | IN("MISMATCH", "NOT_FOUND", "LINK_DEAD", "STALE")) | [.status, .key] | @tsv' data.json
jq -r '.references[] | select(.status | IN("PARTIAL", "UNVERIFIABLE")) | [.status, .key] | @tsv' data.json
jq -r '.citations[] | select(.key == "") | [.form, .context] | @tsv' data.json
```

For this offline fixture the first command prints no findings, and the second
prints eight `UNVERIFIABLE` entries, including:

```text
UNVERIFIABLE	anthropic|2024
```

That is eight entries **not checked**, not eight bad citations.
The third command reports detected citations without a matched entry for manual
review, independently of whether any reference was verified.
For a normal online run, omit `--offline`; the same queries still keep findings
and coverage gaps distinct. Inspect each selected reference's `notes` and
`evidence` before drawing a conclusion.
