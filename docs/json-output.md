# JSON output format

`touchneedle check` writes JSON when you pass `--json FILE`:

```sh
touchneedle check paper.md --json results.json
```

The top-level object has three keys:

| Key | Type | Contents |
|---|---|---|
| `style` | string | Citation style selected for the document. |
| `references` | array | Parsed reference-list entries, each with a verification result. |
| `citations` | array | In-text citation instances found in the document. |

## Reference entries

Each object in `references` contains these fields:

| Field | Meaning |
|---|---|
| `raw` | Original reference-list text. |
| `key` | Parsed citation key, when available. |
| `number` | Numbered-list position; `0` when the entry is unnumbered. |
| `style` | Parsing strategy used for the entry. |
| `name`, `is_org` | First author or organization name, and whether it is an organization. |
| `year`, `suffix` | Parsed year and optional letter suffix such as `a` or `b`. |
| `title`, `container` | Parsed work title and containing publication or venue. |
| `url`, `doi`, `arxiv`, `rfc`, `draft`, `draft_rev`, `accessed` | Parsed link, identifiers, draft revision, or access date. Empty strings mean no value was parsed. |
| `kind` | Parsed source kind; defaults to `unknown` when it could not be classified. |
| `status` | Verification outcome listed below. |
| `unchecked` | Whether the result could not be checked because an authority was unavailable. |
| `notes` | Explanations and follow-up details. |
| `evidence` | Sources or records used during verification. |
| `cited_by` | Forms of citations that matched this reference, such as `parenthetical` or `numeric`. |

## Citation entries

Each object in `citations` describes one in-text citation:

| Field | Meaning |
|---|---|
| `name`, `year`, `suffix` | Parsed author or organization, year, and optional year suffix. |
| `form` | Citation form, such as `parenthetical`, `narrative`, `numeric`, or `note`. |
| `context` | Text surrounding the citation. |
| `key` | Parsed key that can link it to a reference entry. |
| `number` | Numeric marker or footnote number; `0` when absent. |
| `page` | Parsed page locator, when present. |

## Verification statuses

| Status | Meaning |
|---|---|
| `VERIFIED` | The checked metadata or page title matched. |
| `MISMATCH` | Retrieved metadata or page title disagrees with the reference. |
| `NOT_FOUND` | The consulted index or authority had no matching record. |
| `LINK_DEAD` | The URL failed with evidence that it is unavailable, or resolves to an error page. |
| `STALE` | The cited Internet-Draft revision has been superseded. |
| `PARTIAL` | A source was found, but the available information was not enough for a confident match. |
| `LINK_MOVED` | The URL redirected, while the destination matched the reference. |
| `UNVERIFIABLE` | No supported identifier or URL was available, or the check could not be completed. |

`PARTIAL` and `UNVERIFIABLE` describe gaps in verification, not proof that a
reference is wrong. The `unchecked` field identifies checks that could not run
because an authority was unreachable. `check` exits with status 2 for
`MISMATCH`, `NOT_FOUND`, `LINK_DEAD`, or `STALE`; the other statuses alone do
not cause that exit status.

For example, `jq` can list the statuses that make `check` exit with 2:

```sh
jq -r '.references[] | select(.status == "MISMATCH" or .status == "NOT_FOUND" or .status == "LINK_DEAD" or .status == "STALE") | [.status, .raw] | @tsv' results.json
```
