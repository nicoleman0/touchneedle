# JSON output

`touchneedle check DOC --json FILE` writes the verification results as JSON.
The file is intended for CI jobs, dashboards, and other tools that need to
consume the results without parsing the Markdown report.

The top level has three keys:

| Key | Type | Meaning |
|---|---|---|
| `style` | string | The citation style used for this run: `author-date`, `numeric`, `mla`, or `notes`. |
| `references` | array | One object for each reference-list entry. Each object is the JSON form of a `Reference`. |
| `citations` | array | One object for each in-text citation instance. Each object is the JSON form of a `Citation`. |

The `references` and `citations` arrays can be empty when the document contains
no entries of that kind.

## `Reference`

Each item in `references` is the serialized `Reference` dataclass.

| Field | Type | Meaning | When empty |
|---|---|---|---|
| `raw` | string | The original reference-list entry, after the parser's basic cleanup. | Never for a parsed entry. |
| `key` | string | Internal key used to match in-text citations to the reference. | Not normally empty; fallback keys are generated for entries that cannot be parsed normally. |
| `number` | integer | Number from a numbered reference marker such as `[3]`, `3.`, or `3)`. | `0` when the reference list is not numbered. |
| `style` | string | Citation grammar that successfully parsed the entry. | Empty when no citation grammar matched the entry. |
| `name` | string | First-author surname, or the organisation name for an organisational reference. | Empty when no author or organisation could be identified. |
| `is_org` | boolean | Whether `name` represents an organisation rather than a person. | Never; always `true` or `false`. |
| `year` | string | Publication year. | Empty when no publication year was parsed. |
| `suffix` | string | Year suffix such as `a` or `b`. | Empty when the year has no suffix. |
| `title` | string | Title parsed from the reference entry. | Empty when no title could be extracted. |
| `container` | string | The publication or containing source after the title. | Empty when no container was parsed. |
| `url` | string | HTTP or HTTPS URL found in the entry. | Empty when the reference has no URL. |
| `doi` | string | DOI found in the entry. | Empty when no DOI is present. |
| `arxiv` | string | arXiv identifier found in the entry. | Empty when the reference is not identified by an arXiv ID. |
| `rfc` | string | RFC number found in the entry. | Empty when the reference is not an RFC. |
| `draft` | string | IETF Internet-Draft name found in the entry. | Empty when the reference is not an Internet-Draft. |
| `draft_rev` | string | Revision number separated from an Internet-Draft name. | Empty when there is no revision number. |
| `accessed` | string | Access date parsed from an `Accessed:` date in the reference. | Empty when no access date is present. |
| `kind` | string | Broad locator/source kind inferred by the parser. | `unknown` when no supported kind can be inferred. |
| `status` | string | Verification result for the reference. See [Statuses](#statuses). | `UNVERIFIABLE` is the initial/default status. |
| `unchecked` | boolean | Whether an authority could not be reached, so the reference could not actually be checked. | Never; always `true` or `false`. |
| `notes` | array of strings | Parser or verification notes explaining caveats or problems. | `[]` when there are no notes. |
| `evidence` | array of strings | Evidence returned by the verification process. | `[]` when no evidence was recorded. |
| `cited_by` | array of strings | Keys of in-text citations that matched this reference. | `[]` when the reference is not cited in the document. |

A reference can legitimately have many empty locator fields. For example, a
web reference may have a `url` but no `doi`, `arxiv`, `rfc`, or `draft`.

An empty field means that the parser did not find that piece of metadata. It
does not by itself mean that the reference is wrong.

## `Citation`

Each item in `citations` is the serialized `Citation` dataclass.

| Field | Type | Meaning | When empty |
|---|---|---|---|
| `name` | string | Author or organisation name extracted from an in-text citation. | Empty when the citation form does not carry a name. |
| `year` | string | Publication year carried by the citation. | Empty when the citation form does not carry a year. |
| `suffix` | string | Year suffix such as `a` or `b`. | Empty when no suffix is present. |
| `form` | string | Form in which the citation was found, such as `parenthetical`, `narrative`, `numeric`, `mla`, or `note`. | Never for a parsed citation. |
| `context` | string | Surrounding text containing the citation. | Normally non-empty for a found citation. |
| `key` | string | Reference key matched to the citation. | Empty when no reference-list entry could be matched. |
| `number` | integer | Numeric citation marker or footnote number. | `0` when the citation has no numeric marker. |
| `page` | string | Page locator used by MLA-style citations. | Empty when the citation has no MLA page locator. |

A citation with an empty `key` is an unresolved in-text citation: the parser
found a citation-shaped marker but could not match it to a reference-list
entry.

## Statuses

`status` is the verification outcome for a reference.

| Status | Meaning |
|---|---|
| `MISMATCH` | An authoritative source was found, but it disagrees with information in the reference. |
| `NOT_FOUND` | The checker searched the available authorities and could not find the referenced work. This does not prove that the source does not exist. |
| `LINK_DEAD` | The supplied URL does not currently resolve. |
| `STALE` | The cited revision has been superseded by a newer revision. |
| `PARTIAL` | Some evidence was found, but verification was incomplete. |
| `LINK_MOVED` | The supplied URL redirects somewhere else. |
| `UNVERIFIABLE` | There was not enough checkable information, or verification could not be completed. |
| `VERIFIED` | The available reference metadata matched an authoritative record. |

### `PARTIAL` and `UNVERIFIABLE` are not failures

`PARTIAL` and `UNVERIFIABLE` mean **not checked completely**, not **wrong**.

They should not be treated as proof that a reference is incorrect.

The problem statuses are:

```text
MISMATCH
NOT_FOUND
LINK_DEAD
STALE