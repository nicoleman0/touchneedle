#!/usr/bin/env python3
"""Verify that the citations in a document are real, correctly described, and
consistently used.

Reads a prose reference list (Harvard/author-date) out of a Markdown or .docx
document, routes each entry to whichever authority can actually confirm it --
arXiv, Crossref, OpenAlex, the IETF datatracker, or the live web -- and reports
what does not line up. Also cross-checks in-text citations against the list in
both directions.

Standard library only. Python 3.9+.

  touchneedle.py check  DOC [--out report.md] [--json data.json]
  touchneedle.py claims DOC [--out claims.md]

Exit status is 2 when the run found problems worth a human look, 0 when clean.
"""

from __future__ import annotations

import argparse
import dataclasses
import difflib
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any, Iterable, Optional

__version__ = "0.1.0"
# Placeholder owner: swapped for the real one at publish time. One token,
# repo-wide, so the swap is a single sed -- see RELEASING.md.
REPO_URL = "https://github.com/OWNER/touchneedle"
UA = f"touchneedle/{__version__} (+{REPO_URL}; academic reference verification)"
CACHE_TTL = 7 * 24 * 3600

# Verification outcomes, worst first -- the report sorts by this order.
SEVERITY = {
    "MISMATCH": 0,
    "NOT_FOUND": 1,
    "LINK_DEAD": 2,
    "STALE": 3,
    "PARTIAL": 4,
    "LINK_MOVED": 5,
    "UNVERIFIABLE": 6,
    "VERIFIED": 7,
}
PROBLEM_STATUSES = {"MISMATCH", "NOT_FOUND", "LINK_DEAD", "STALE"}


# --------------------------------------------------------------------------
# text loading and cleanup
# --------------------------------------------------------------------------

def load_text(path: str) -> str:
    """Return document text as Markdown, converting .docx through pandoc."""
    if path.lower().endswith((".docx", ".odt", ".rtf")):
        if not shutil.which("pandoc"):
            sys.exit(f"error: {path} needs pandoc to convert, and pandoc is not on PATH")
        out = subprocess.run(
            ["pandoc", path, "-t", "markdown", "--wrap=none"],
            capture_output=True, text=True,
        )
        if out.returncode != 0:
            sys.exit(f"error: pandoc failed on {path}:\n{out.stderr}")
        return out.stdout
    with open(path, encoding="utf-8") as fh:
        return fh.read()


LATEX_NOISE = re.compile(r"\\(?:allowbreak|linebreak|newline|,|;|!)\{?\}?")
MARKBOTH = re.compile(r"\\markboth\{[^}]*\}\{[^}]*\}")


def clean(s: str) -> str:
    """Strip the LaTeX/pandoc debris that survives a docx -> markdown pass."""
    s = LATEX_NOISE.sub("", s)
    s = MARKBOTH.sub("", s)
    s = re.sub(r"\\([\'\"`^~$&%#_{}])", r"\1", s)   # pandoc escapes
    s = s.replace("\u00a0", " ").replace("\u2011", "-")
    s = re.sub(r"[ \t]*\n[ \t]*", " ", s)
    return re.sub(r"\s{2,}", " ", s).strip()


TITLES = r"references|bibliography|works cited|reference list"
HEADING = re.compile(r"^(#{1,4})\s*(?:\d+[.)]?\s*)?(?:%s)\b.*$" % TITLES, re.I | re.M)
# A .docx whose Word style never mapped to a heading level leaves the word
# sitting on a line of its own, sometimes bold or underlined.
BARE_HEADING = re.compile(r"^[ \t]*[*_]{0,2}(?:%s)[*_:]{0,2}[ \t]*$" % TITLES, re.I | re.M)


def split_document(text: str) -> tuple[str, str]:
    """Split into (body, reference block).

    Later candidates win -- the word appears in running prose long before the
    list itself -- but a candidate only wins if entries can actually be parsed
    below it, so a stray mention does not swallow the real list.
    """
    candidates = list(HEADING.finditer(text)) or list(BARE_HEADING.finditer(text))
    if not candidates:
        sys.exit("error: no 'References' / 'Bibliography' heading found in the document")

    for match in reversed(candidates):
        level = len(match.group(1)) if match.re is HEADING else 1
        rest = text[match.end():]
        nxt = re.search(r"^#{1,%d}\s+\S" % level, rest, re.M)
        block = rest[: nxt.start()] if nxt else rest
        if len(split_entries(block)) >= 3:
            return text[: match.start()], block
    sys.exit("error: found a References heading but could not parse any entries under it")


SKIP_ENTRY = re.compile(r"^(\\markboth|\[\^|:::|<!--|!\[|\||\s*$)")


def split_entries(block: str) -> list[str]:
    """Blank-line-separated entries, with a fallback for one-per-line lists."""
    chunks = [c.strip() for c in re.split(r"\n[ \t]*\n", block)]
    entries = [clean(c) for c in chunks if c and not SKIP_ENTRY.match(c)]
    entries = [e for e in entries if len(e) > 25 and re.search(r"\((?:19|20)\d\d[a-z]?\)", e)]
    if len(entries) <= 1 and block.count("\n") > 3:
        # Single-spaced list: start a new entry at each line that opens with a
        # capitalised author or organisation and carries a year.
        entries, current = [], None
        for line in block.splitlines():
            if re.match(r"^[A-Z\u00c0-\u00dd][^\n]*\((?:19|20)\d\d[a-z]?\)", line.strip()):
                if current is not None:
                    entries.append(clean(current))
                current = line
            elif current is not None:
                # Anything before the first author-year line is preamble --
                # a table row, a caption, a stray heading -- not an entry.
                current += " " + line
        if current is not None:
            entries.append(clean(current))
        entries = [e for e in entries
                   if len(e) > 25 and not SKIP_ENTRY.match(e)]
    return entries


# --------------------------------------------------------------------------
# reference parsing
# --------------------------------------------------------------------------

@dataclasses.dataclass
class Reference:
    raw: str
    key: str = ""
    name: str = ""            # first-author surname, or organisation name
    is_org: bool = False
    year: str = ""
    suffix: str = ""          # the 'a' / 'b' in 2025a
    title: str = ""
    container: str = ""
    url: str = ""
    doi: str = ""
    arxiv: str = ""
    rfc: str = ""
    draft: str = ""
    draft_rev: str = ""
    accessed: str = ""
    kind: str = "unknown"
    status: str = "UNVERIFIABLE"
    notes: list[str] = dataclasses.field(default_factory=list)
    evidence: list[str] = dataclasses.field(default_factory=list)
    cited_by: list[str] = dataclasses.field(default_factory=list)


YEAR = re.compile(r"\((19|20)(\d\d)([a-z]?)\)")
# A quoted title may contain an apostrophe ("what you've signed up for"), so the
# closing quote is only the one followed by punctuation or end of entry.
QUOTED = re.compile(
    r"(?:^|[\s(])[\u2018'\"\u201c](.{8,300}?)[\u2019'\"\u201d](?=\s*[,.;]|\s*$)")
URL_RE = re.compile(r"<?(https?://[^\s>)\]]+)>?")
DOI_RE = re.compile(r"\b(10\.\d{4,9}/[^\s,;>\)\]]+)")
ARXIV_RE = re.compile(r"arXiv[:\s]\s*(\d{4}\.\d{4,5})(v\d+)?", re.I)
RFC_RE = re.compile(r"\bRFC\s*(\d{3,5})\b", re.I)
DRAFT_RE = re.compile(r"\b(draft-[a-z0-9][a-z0-9\-]*[a-z0-9])\b", re.I)
ACCESSED_RE = re.compile(r"\(Accessed:?\s*([^)]+)\)", re.I)
PERSON_RE = re.compile(r"^[A-Z\u00c0-\u00dd][\w\u00c0-\u017e'\u2019\-]+,\s*[A-Z]\.")

ACADEMIC = re.compile(
    r"\b(proceedings|conference|symposium|workshop|journal|transactions|advances in|"
    r"findings of|arxiv|preprint|acm|ieee|usenix|neurips|iclr|icml)\b", re.I)


def parse_entry(raw: str) -> Reference:
    ref = Reference(raw=raw)

    ym = YEAR.search(raw)
    if ym:
        ref.year = ym.group(1) + ym.group(2)
        ref.suffix = ym.group(3)
        authors = raw[: ym.start()].strip().rstrip(",")
        tail = raw[ym.end():].strip()
    else:
        authors, tail = "", raw

    ref.is_org = not PERSON_RE.match(authors)
    if ref.is_org:
        ref.name = authors.strip(" .,")
    else:
        ref.name = authors.split(",")[0].strip()

    ref.key = f"{normalise(ref.name)}|{ref.year}{ref.suffix}"

    qm = QUOTED.search(tail)
    if qm:
        ref.title = qm.group(1).strip()
        ref.container = tail[qm.end():].lstrip(" ,.").strip()
    else:
        # Unquoted title: everything up to the first sentence break that is not
        # part of an initial or a URL.
        head = re.split(r"\.\s+(?=[A-Z])|\.\s*Available at", tail, maxsplit=1)
        ref.title = head[0].strip(" .,")
        ref.container = (head[1] if len(head) > 1 else "").strip()

    if m := URL_RE.search(raw):
        ref.url = m.group(1).rstrip(".,;")
    if m := DOI_RE.search(raw):
        ref.doi = m.group(1).rstrip(".")
    if m := ARXIV_RE.search(raw):
        ref.arxiv = m.group(1)
    if m := RFC_RE.search(raw):
        ref.rfc = m.group(1)
    if m := DRAFT_RE.search(raw):
        # Take the whole token greedily, then split a trailing -NN revision off
        # it -- 'draft-ietf-oauth-v2-1-15' is v2-1 at revision 15.
        full = m.group(1)
        rm = re.match(r"^(.*?)-(\d{2})$", full)
        ref.draft, ref.draft_rev = (rm.group(1), rm.group(2)) if rm else (full, "")
    if m := ACCESSED_RE.search(raw):
        ref.accessed = m.group(1).strip()
        ref.title = re.sub(r"\s*\(Accessed:?[^)]*\)", "", ref.title).strip()
    ref.title = re.sub(r"\s*Available at:?.*$", "", ref.title, flags=re.I)
    # An unquoted title often absorbs the series identifier that follows it;
    # trim it so title matching compares like with like.
    ref.title = re.sub(
        r",?\s*(RFC\s*\d+|BCP\s*\d+|Internet-Draft\s+draft-\S+|IETF)\b", "",
        ref.title, flags=re.I).strip(" .,")

    if ref.arxiv:
        ref.kind = "arxiv"
    elif ref.doi:
        ref.kind = "doi"
    elif ref.rfc:
        ref.kind = "rfc"
    elif ref.draft:
        ref.kind = "ietf-draft"
    elif qm and ACADEMIC.search(ref.container):
        ref.kind = "paper"
    elif ref.url:
        ref.kind = "web"
    return ref


# --------------------------------------------------------------------------
# in-text citations
# --------------------------------------------------------------------------

PAREN = re.compile(r"\(([^()]{3,120}?(?:19|20)\d\d[a-z]?[^()]{0,40}?)\)")
NARRATIVE = re.compile(
    r"\b([A-Z\u00c0-\u00dd][\w\u00c0-\u017e'\u2019\-]*"
    r"(?:\s+(?:and|&)\s+[A-Z\u00c0-\u00dd][\w\u00c0-\u017e'\u2019\-]*"
    r"|\s+et\s+al\.?"
    r"|\s+[A-Z\u00c0-\u00dd][\w\u00c0-\u017e'\u2019\-]*){0,3})"
    r"\s+\(((?:19|20)\d\d)([a-z]?)\)")
NOT_A_CITATION = re.compile(
    r"^(accessed|figure|table|chapter|section|appendix|see|eq|equation|n\.?d\.?)\b", re.I)


@dataclasses.dataclass
class Citation:
    name: str
    year: str
    suffix: str
    form: str                 # 'parenthetical' or 'narrative'
    context: str
    key: str = ""


def find_citations(body: str) -> list[Citation]:
    out: list[Citation] = []
    for m in PAREN.finditer(body):
        inner = m.group(1)
        if re.search(r"accessed", inner, re.I):
            continue
        for part in re.split(r";", inner):
            part = part.strip()
            cm = re.match(
                r"^(.{2,80}?)[,\s]+((?:19|20)\d\d)([a-z]?)\s*$", part.replace("et al.", "et al"))
            if not cm:
                continue
            name = cm.group(1).strip(" ,")
            if NOT_A_CITATION.match(name) or not re.match(r"^[A-Z\u00c0-\u00dd]", name):
                continue
            out.append(Citation(name, cm.group(2), cm.group(3), "parenthetical",
                                context(body, m.start())))
    for m in NARRATIVE.finditer(body):
        name = m.group(1).strip()
        if NOT_A_CITATION.match(name):
            continue
        out.append(Citation(name, m.group(2), m.group(3), "narrative",
                            context(body, m.start())))
    return out


SENT_END = re.compile(r"(?<![A-Z])(?<!\bet al)(?<!\bvol)(?<!\bpp)[.!?](?:\s|$)")


def context(body: str, pos: int, width: int = 420) -> str:
    """Approximate sentence around a position -- good enough for a worklist."""
    start = max(0, pos - width)
    end = min(len(body), pos + width)
    left = body[start:pos]
    right = body[pos:end]
    headings = list(re.finditer(r"(?m)^#{1,6}[^\n]*$", left))
    if headings:                  # don't drag the section title into the quote
        left = left[headings[-1].end():]
    bounds = list(SENT_END.finditer(left))
    if bounds:
        left = left[bounds[-1].end():]
    fwd = SENT_END.search(right)
    if fwd:
        right = right[: fwd.end()]
    return clean(left + right)


def normalise(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"\bet\s+al\.?", "", s, flags=re.I)
    s = re.sub(r"[^a-z0-9 ]", " ", s.lower())
    return re.sub(r"\s+", " ", s).strip()


def citation_key(name: str, year: str, suffix: str) -> str:
    # Split the ampersand off before normalise(), which strips punctuation and
    # would otherwise leave 'Smith & Jones' as the single token 'smith jones'.
    n = normalise(name.split("&")[0])
    n = re.split(r"\band\b", n)[0].strip()
    return f"{n}|{year}{suffix}"


def match_citations(refs: list[Reference], cites: list[Citation]) -> list[Citation]:
    """Attach each in-text citation to a reference where one can be found."""
    by_key = {r.key: r for r in refs}
    by_surname: dict[str, list[Reference]] = {}
    for r in refs:
        first = normalise(r.name).split(" ")[0] if not r.is_org else normalise(r.name)
        by_surname.setdefault(first, []).append(r)

    for c in cites:
        key = citation_key(c.name, c.year, c.suffix)
        if key in by_key:
            c.key = key
            by_key[key].cited_by.append(c.form)
            continue
        # organisation names cite in full; person names cite by surname only
        stem = key.split("|")[0]
        head = stem.split(" ")[0]
        for candidate_stem in (stem, head):
            for r in by_surname.get(candidate_stem, []):
                if r.year == c.year and (not c.suffix or c.suffix == r.suffix):
                    c.key = r.key
                    r.cited_by.append(c.form)
                    break
            if c.key:
                break
    return cites


# --------------------------------------------------------------------------
# HTTP with an on-disk cache
# --------------------------------------------------------------------------

class Fetcher:
    def __init__(self, cache_dir: str, timeout: int = 25, offline: bool = False,
                 mailto: Optional[str] = None, delay: float = 0.4):
        self.cache_dir = cache_dir
        self.timeout = timeout
        self.offline = offline
        self.mailto = mailto
        self.delay = delay
        self.last = 0.0
        os.makedirs(cache_dir, exist_ok=True)

    def get(self, url: str, accept: Optional[str] = None, max_bytes: int = 400_000) -> dict:
        path = os.path.join(self.cache_dir, hashlib.sha256(
            (url + (accept or "")).encode()).hexdigest() + ".json")
        if os.path.exists(path) and time.time() - os.path.getmtime(path) < CACHE_TTL:
            with open(path, encoding="utf-8") as fh:
                return json.load(fh)
        if self.offline:
            return {"ok": False, "status": None, "error": "offline", "body": "", "final_url": url}

        gap = self.delay - (time.time() - self.last)
        if gap > 0:
            time.sleep(gap)
        self.last = time.time()

        ua = UA if not self.mailto else f"{UA} mailto:{self.mailto}"
        req = urllib.request.Request(url, headers={
            "User-Agent": ua,
            "Accept": accept or "text/html,application/json;q=0.9,*/*;q=0.8",
        })
        rec: dict[str, Any]
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read(max_bytes)
                charset = resp.headers.get_content_charset() or "utf-8"
                rec = {"ok": True, "status": resp.status,
                       "body": raw.decode(charset, "replace"),
                       "final_url": resp.geturl(), "error": None}
        except urllib.error.HTTPError as e:
            rec = {"ok": False, "status": e.code, "body": "", "final_url": url,
                   "error": f"HTTP {e.code}"}
        except Exception as e:                          # timeouts, DNS, TLS, redirect loops
            rec = {"ok": False, "status": None, "body": "", "final_url": url,
                   "error": f"{type(e).__name__}: {e}"}
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(rec, fh)
        return rec

    def json(self, url: str) -> Optional[Any]:
        rec = self.get(url, accept="application/json")
        if not rec["ok"]:
            return None
        try:
            return json.loads(rec["body"])
        except json.JSONDecodeError:
            return None


# --------------------------------------------------------------------------
# similarity
# --------------------------------------------------------------------------

def title_score(a: str, b: str) -> float:
    na, nb = normalise(a), normalise(b)
    if not na or not nb:
        return 0.0
    seq = difflib.SequenceMatcher(None, na, nb).ratio()
    ta, tb = set(na.split()), set(nb.split())
    jac = len(ta & tb) / len(ta | tb) if ta | tb else 0.0
    contain = 1.0 if (na in nb or nb in na) and min(len(na), len(nb)) > 20 else 0.0
    return max(seq, jac, contain)


def author_present(surname: str, authors: Iterable[str]) -> bool:
    s = normalise(surname).split(" ")[-1]
    return any(s and s in normalise(a).split() for a in authors)


# --------------------------------------------------------------------------
# per-source verification
# --------------------------------------------------------------------------

def check_metadata(ref: Reference, found_title: str, found_authors: list[str],
                   found_year: Optional[str], source: str) -> None:
    """Compare a retrieved record against the reference and set status/notes."""
    score = title_score(ref.title, found_title)
    ref.evidence.append(f"{source}: \u201c{found_title[:140]}\u201d"
                        + (f" ({found_year})" if found_year else ""))
    problems = []
    if score < 0.60:
        problems.append(f"title differs from {source} record (similarity {score:.2f})")
    elif score < 0.85:
        ref.notes.append(f"title only partly matches {source} (similarity {score:.2f})")
    if found_authors and not ref.is_org and not author_present(ref.name, found_authors):
        problems.append(f"first author '{ref.name}' not among {source} authors "
                        f"({', '.join(found_authors[:4])})")
    if found_year and ref.year and abs(int(found_year) - int(ref.year)) > 1:
        problems.append(f"year {ref.year} vs {found_year} in {source}")

    if problems:
        ref.status = "MISMATCH"
        ref.notes.extend(problems)
    elif score >= 0.85:
        ref.status = "VERIFIED"
    else:
        ref.status = "PARTIAL"


def verify_arxiv(ref: Reference, f: Fetcher) -> bool:
    url = f"http://export.arxiv.org/api/query?id_list={ref.arxiv}&max_results=1"
    rec = f.get(url, accept="application/atom+xml")
    if not rec["ok"]:
        ref.notes.append(f"arXiv API unreachable ({rec['error']})")
        return False
    try:
        root = ET.fromstring(rec["body"])
    except ET.ParseError:
        return False
    ns = {"a": "http://www.w3.org/2005/Atom"}
    entry = root.find("a:entry", ns)
    if entry is None or entry.findtext("a:title", "", ns).strip() in ("", "Error"):
        ref.status = "NOT_FOUND"
        ref.notes.append(f"arXiv has no paper with id {ref.arxiv}")
        return True
    title = " ".join(entry.findtext("a:title", "", ns).split())
    authors = [a.findtext("a:name", "", ns) for a in entry.findall("a:author", ns)]
    published = entry.findtext("a:published", "", ns)[:4] or None
    check_metadata(ref, title, authors, published, f"arXiv:{ref.arxiv}")
    return True


def crossref_record(item: dict) -> tuple[str, list[str], Optional[str]]:
    title = (item.get("title") or [""])[0]
    authors = [" ".join(filter(None, [a.get("given"), a.get("family")]))
               for a in item.get("author", [])]
    parts = (item.get("issued") or {}).get("date-parts") or [[None]]
    year = str(parts[0][0]) if parts and parts[0] and parts[0][0] else None
    return title, authors, year


def verify_doi(ref: Reference, f: Fetcher) -> bool:
    data = f.json(f"https://api.crossref.org/works/{urllib.parse.quote(ref.doi)}")
    if not data or "message" not in data:
        ref.status = "NOT_FOUND"
        ref.notes.append(f"Crossref has no record for DOI {ref.doi}")
        return True
    title, authors, year = crossref_record(data["message"])
    check_metadata(ref, title, authors, year, f"Crossref {ref.doi}")
    return True


def verify_by_title(ref: Reference, f: Fetcher) -> bool:
    """No identifier: search Crossref then OpenAlex by bibliographic title."""
    if not ref.title:
        return False
    q = urllib.parse.quote(ref.title[:250])
    best: tuple[float, str, list[str], Optional[str], str] = (0.0, "", [], None, "")

    data = f.json(f"https://api.crossref.org/works?query.bibliographic={q}&rows=5"
                  + (f"&mailto={urllib.parse.quote(f.mailto)}" if f.mailto else ""))
    for item in ((data or {}).get("message", {}) or {}).get("items", []):
        title, authors, year = crossref_record(item)
        s = title_score(ref.title, title)
        if s > best[0]:
            best = (s, title, authors, year, f"Crossref ({item.get('DOI', 'no DOI')})")

    if best[0] < 0.85:
        data = f.json(f"https://api.openalex.org/works?per-page=5&filter=title.search:{q}"
                      + (f"&mailto={urllib.parse.quote(f.mailto)}" if f.mailto else ""))
        for item in (data or {}).get("results", []):
            title = item.get("display_name") or ""
            authors = [a.get("author", {}).get("display_name", "")
                       for a in item.get("authorships", [])]
            year = str(item.get("publication_year")) if item.get("publication_year") else None
            s = title_score(ref.title, title)
            if s > best[0]:
                best = (s, title, authors, year, "OpenAlex")

    if best[0] < 0.55:
        ref.status = "NOT_FOUND"
        ref.notes.append("no close title match in Crossref or OpenAlex"
                         + (f" (best {best[0]:.2f}: \u201c{best[1][:90]}\u201d)" if best[1] else ""))
        return True
    check_metadata(ref, best[1], best[2], best[3], best[4])
    return True


def verify_rfc(ref: Reference, f: Fetcher) -> bool:
    data = f.json(f"https://datatracker.ietf.org/api/v1/doc/document/rfc{ref.rfc}/?format=json")
    if data and data.get("title"):
        check_metadata(ref, data["title"], [], None, f"IETF datatracker RFC {ref.rfc}")
        if data.get("std_level"):
            ref.evidence.append(f"status: {data['std_level']}")
        return True
    rec = f.get(f"https://www.rfc-editor.org/rfc/rfc{ref.rfc}.txt", accept="text/plain")
    if not rec["ok"]:
        ref.status = "NOT_FOUND"
        ref.notes.append(f"RFC {ref.rfc} not retrievable from datatracker or rfc-editor")
        return True
    head = rec["body"][:4000]
    if ref.title and title_score(ref.title, head) < 0.10 and normalise(ref.title)[:40] not in normalise(head):
        ref.status = "PARTIAL"
        ref.notes.append(f"RFC {ref.rfc} exists but its text does not obviously contain the cited title")
    else:
        ref.status = "VERIFIED"
    ref.evidence.append(f"rfc-editor: rfc{ref.rfc}.txt retrieved")
    return True


def verify_draft(ref: Reference, f: Fetcher) -> bool:
    data = f.json(
        f"https://datatracker.ietf.org/api/v1/doc/document/{ref.draft}/?format=json")
    if not data or not data.get("title"):
        ref.status = "NOT_FOUND"
        ref.notes.append(f"IETF datatracker has no draft named {ref.draft}")
        return True
    check_metadata(ref, data["title"], [], None, f"IETF datatracker {ref.draft}")
    current = str(data.get("rev") or "")
    if current:
        ref.evidence.append(f"current revision: -{current}")
        if ref.draft_rev and ref.draft_rev != current:
            ref.status = "STALE"
            ref.notes.append(
                f"cited as -{ref.draft_rev} but the current revision is -{current}; "
                "an Internet-Draft is a moving target, so confirm the cited text survived")
    if str(data.get("state") or "").lower() in {"expired", "dead", "replaced"}:
        ref.notes.append(f"datatracker state: {data['state']}")
    return True


TITLE_TAG = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)
OG_TITLE = re.compile(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\'](.*?)["\']', re.I)
SOFT_404 = re.compile(r"\b(404|not found|page (?:not|no longer) (?:found|available)|"
                      r"deleted|does not exist)\b", re.I)


def verify_web(ref: Reference, f: Fetcher) -> bool:
    if not ref.url:
        return False
    rec = f.get(ref.url)
    if not rec["ok"]:
        # Our own offline switch is not evidence about the link.
        ref.status = "UNVERIFIABLE" if rec["error"] == "offline" else "LINK_DEAD"
        ref.notes.append(f"{ref.url} -> {rec['error']}")
        return True

    page_title = ""
    if m := OG_TITLE.search(rec["body"]):
        page_title = m.group(1)
    elif m := TITLE_TAG.search(rec["body"]):
        page_title = re.sub(r"<[^>]+>", " ", m.group(1))
    page_title = clean(page_title)[:200]
    ref.evidence.append(f"page title: \u201c{page_title}\u201d" if page_title
                        else f"HTTP {rec['status']}, no <title>")

    final = rec["final_url"]
    if final.rstrip("/") != ref.url.rstrip("/"):
        ref.notes.append(f"redirects to {final}")

    if page_title and SOFT_404.search(page_title):
        ref.status = "LINK_DEAD"
        ref.notes.append(f"page resolves but looks like an error page: \u201c{page_title}\u201d")
        return True

    if not page_title:
        ref.status = "PARTIAL"
        ref.notes.append("URL resolves but no title could be read (PDF or JS-rendered page); "
                         "confirm by eye")
        return True

    score = max(title_score(ref.title, page_title),
                title_score(ref.title, page_title + " " + ref.container))
    if score >= 0.55:
        ref.status = "VERIFIED"
    elif normalise(ref.name) and normalise(ref.name).split(" ")[0] in normalise(page_title):
        ref.status = "PARTIAL"
        ref.notes.append(f"page title \u201c{page_title}\u201d does not match the cited title, "
                         "though the publisher matches")
    else:
        ref.status = "MISMATCH"
        ref.notes.append(f"cited title vs page title mismatch (similarity {score:.2f}): "
                         f"\u201c{page_title}\u201d")
    if final.rstrip("/") != ref.url.rstrip("/") and ref.status == "VERIFIED":
        ref.status = "LINK_MOVED"
    return True


def verify(ref: Reference, f: Fetcher) -> None:
    if f.offline:
        # Absence of a lookup is not a finding about the citation.
        ref.status = "UNVERIFIABLE"
        ref.notes.append("offline mode: no source was contacted")
        return
    done = False
    if ref.arxiv:
        done = verify_arxiv(ref, f)
    if not done and ref.doi:
        done = verify_doi(ref, f)
    if not done and ref.rfc:
        done = verify_rfc(ref, f)
    if not done and ref.draft:
        done = verify_draft(ref, f)
    if not done and ref.kind == "paper":
        done = verify_by_title(ref, f)
    if not done and ref.url:
        done = verify_web(ref, f)
    elif done and ref.url and ref.status in {"VERIFIED", "PARTIAL"} and ref.kind != "web":
        # Identifier checked out; still make sure the link the reader follows works.
        probe = f.get(ref.url)
        if not probe["ok"]:
            ref.notes.append(f"companion link {ref.url} -> {probe['error']}")
            ref.status = "LINK_DEAD" if ref.status == "VERIFIED" else ref.status
    if not done and not ref.url:
        ref.status = "UNVERIFIABLE"
        ref.notes.append("no DOI, arXiv id, RFC number or URL to check against")


# --------------------------------------------------------------------------
# reporting
# --------------------------------------------------------------------------

def build_report(refs: list[Reference], cites: list[Citation], doc: str,
                 offline: bool) -> str:
    counts: dict[str, int] = {}
    for r in refs:
        counts[r.status] = counts.get(r.status, 0) + 1

    uncited = [r for r in refs if not r.cited_by]
    unresolved = [c for c in cites if not c.key]
    ambiguous = ambiguous_suffixes(refs, cites)

    L = [f"# Citation check \u2014 {os.path.basename(doc)}", "",
         f"Run {time.strftime('%Y-%m-%d %H:%M')}"
         + ("  \u2014 **offline mode, nothing was verified against a live source**" if offline else ""),
         "", f"{len(refs)} reference entries, {len(cites)} in-text citation instances.", "",
         "## Summary", "", "| Status | Count | Meaning |", "|---|---:|---|"]
    meaning = {
        "VERIFIED": "matched an authoritative record",
        "PARTIAL": "found, but the match is loose \u2014 eyeball it",
        "MISMATCH": "**found something that disagrees with what you wrote**",
        "NOT_FOUND": "**searched and could not find it at all**",
        "LINK_DEAD": "**URL does not resolve**",
        "LINK_MOVED": "URL redirects elsewhere",
        "STALE": "**cited revision superseded**",
        "UNVERIFIABLE": "nothing checkable in the entry",
    }
    for status in sorted(counts, key=lambda s: SEVERITY[s]):
        L.append(f"| {status} | {counts[status]} | {meaning[status]} |")

    problems = [r for r in refs if r.status in PROBLEM_STATUSES]
    L += ["", f"**{len(problems)} entries need attention.**" if problems
          else "**No entry failed verification.**", ""]

    L += ["## Entries needing attention", ""]
    if not problems:
        L.append("_None._")
    for r in sorted(problems, key=lambda r: SEVERITY[r.status]):
        L += [f"### {r.status} \u2014 {r.name} ({r.year}{r.suffix})", "",
              f"> {r.raw}", ""]
        for n in r.notes:
            L.append(f"- {n}")
        for e in r.evidence:
            L.append(f"- _{e}_")
        L.append("")

    soft = [r for r in refs if r.status in {"PARTIAL", "LINK_MOVED", "UNVERIFIABLE"}]
    L += ["## Worth a glance", ""]
    if not soft:
        L.append("_None._")
    for r in sorted(soft, key=lambda r: SEVERITY[r.status]):
        note = r.notes[0] if r.notes else (r.evidence[0] if r.evidence else "")
        L.append(f"- **{r.status}** \u2014 {r.name} ({r.year}{r.suffix}): {note}")
    L.append("")

    L += ["## Verified", ""]
    ok = [r for r in refs if r.status == "VERIFIED"]
    for r in ok:
        L.append(f"- {r.name} ({r.year}{r.suffix}) \u2014 {r.title[:80]}"
                 + (f" \u2014 _{r.evidence[0][:100]}_" if r.evidence else ""))
    if not ok:
        L.append("_None._")

    L += ["", "## Cross-reference consistency", "",
          "### Reference-list entries never cited in the text", ""]
    L += [f"- {r.name} ({r.year}{r.suffix}) \u2014 {r.title[:90]}" for r in uncited] or ["_None._"]

    L += ["", "### In-text citations with no matching reference entry", "",
          "_Expect false positives here: parenthetical years such as `(ICLR 2023)` "
          "look like citations to a regex._", ""]
    seen = set()
    rows = []
    for c in unresolved:
        k = (c.name, c.year, c.suffix)
        if k in seen:
            continue
        seen.add(k)
        rows.append(f"- `{c.name} ({c.year}{c.suffix})` \u2014 \u2026{c.context[:150]}\u2026")
    L += rows or ["_None._"]

    L += ["", "### Ambiguous year suffixes", ""]
    L += ambiguous or ["_None._"]

    L += ["", "## What this run did not check", "",
          "- Whether each source **supports the claim it is attached to**. That needs "
          "reading, not fetching \u2014 run `touchneedle.py claims` and work the list.",
          "- Page numbers, edition, and publisher details.",
          "- Anything behind a paywall or a JS-rendered page, which comes back PARTIAL.", ""]
    return "\n".join(L)


def ambiguous_suffixes(refs: list[Reference], cites: list[Citation]) -> list[str]:
    """Same author+year split across a/b in the list must be cited with a suffix."""
    groups: dict[str, list[Reference]] = {}
    for r in refs:
        groups.setdefault(f"{normalise(r.name)}|{r.year}", []).append(r)
    out = []
    for stem, group in groups.items():
        if len(group) < 2:
            continue
        name, year = group[0].name, group[0].year
        bare = [c for c in cites
                if citation_key(c.name, c.year, "") == stem and not c.suffix]
        if bare:
            out.append(f"- `{name} ({year})` is cited without a suffix "
                       f"{len(bare)}\u00d7, but the list has "
                       f"{', '.join(year + r.suffix for r in group)}")
        if any(not r.suffix for r in group):
            out.append(f"- reference list has {len(group)} entries for {name} ({year}) "
                       "but not all carry an a/b suffix")
    return out


def build_claims(refs: list[Reference], cites: list[Citation], doc: str) -> str:
    by_key = {r.key: r for r in refs}
    L = [f"# Claim-support worklist \u2014 {os.path.basename(doc)}", "",
         "One row per in-text citation. For each, read the source and decide whether it "
         "supports the sentence: **SUPPORTED / PARTIAL / UNSUPPORTED / INACCESSIBLE**. "
         "Do not guess \u2014 if the source cannot be read, say INACCESSIBLE.", ""]
    ordered = sorted(cites, key=lambda c: (c.key or "zzz", c.year))
    n = 0
    for c in ordered:
        r = by_key.get(c.key)
        n += 1
        L += [f"## {n}. {c.name} ({c.year}{c.suffix}) \u2014 {c.form}", ""]
        if r:
            src = r.url or (f"arXiv:{r.arxiv}" if r.arxiv else "") or (
                f"doi:{r.doi}" if r.doi else "") or (f"RFC {r.rfc}" if r.rfc else "")
            L += [f"- **Source**: {r.title or r.raw[:100]}",
                  f"- **Locate at**: {src or '_no locator in the reference entry_'}"]
        else:
            L.append("- **Source**: _no matching reference-list entry_")
        L += ["- **Claim in the text**:", f"  > \u2026{c.context}\u2026", "",
              "- **Verdict**: ", ""]
    return "\n".join(L)


# --------------------------------------------------------------------------
# entry point
# --------------------------------------------------------------------------

def collect(doc: str) -> tuple[list[Reference], list[Citation]]:
    text = load_text(doc)
    body, block = split_document(text)
    refs = [parse_entry(e) for e in split_entries(block)]
    if not refs:
        sys.exit("error: found a References heading but could not parse any entries under it")
    cites = match_citations(refs, find_citations(body))
    return refs, cites


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    for name in ("check", "claims"):
        p = sub.add_parser(name)
        p.add_argument("doc", help="Markdown or .docx document")
        p.add_argument("--out", help="write the report here instead of stdout")
    chk = sub.choices["check"]
    chk.add_argument("--json", dest="json_out", help="also write machine-readable results")
    chk.add_argument("--offline", action="store_true",
                     help="parse and cross-check only; make no network calls")
    chk.add_argument("--mailto", default=os.environ.get("CITATION_CHECK_MAILTO"),
                     help="contact address sent to Crossref/OpenAlex for their polite "
                          "rate-limit pool (optional; also read from CITATION_CHECK_MAILTO)")
    chk.add_argument("--cache", default=".touchneedle-cache", help="HTTP cache directory")
    chk.add_argument("--timeout", type=int, default=25)

    args = ap.parse_args()
    refs, cites = collect(args.doc)

    if args.cmd == "claims":
        out = build_claims(refs, cites, args.doc)
    else:
        f = Fetcher(args.cache, timeout=args.timeout, offline=args.offline,
                    mailto=args.mailto)
        for i, r in enumerate(refs, 1):
            print(f"[{i}/{len(refs)}] {r.name} ({r.year}{r.suffix}) \u2026",
                  file=sys.stderr, flush=True)
            verify(r, f)
            print(f"    {r.status}", file=sys.stderr, flush=True)
        out = build_report(refs, cites, args.doc, args.offline)
        if args.json_out:
            with open(args.json_out, "w", encoding="utf-8") as fh:
                json.dump({"references": [dataclasses.asdict(r) for r in refs],
                           "citations": [dataclasses.asdict(c) for c in cites]},
                          fh, indent=2, ensure_ascii=False)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(out + "\n")
        print(f"wrote {args.out}", file=sys.stderr)
    else:
        print(out)

    if args.cmd == "check":
        return 2 if any(r.status in PROBLEM_STATUSES for r in refs) else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
