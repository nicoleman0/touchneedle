"""Reference-list parsing: finding the list, splitting it, reading an entry."""

import os
import unittest

from context import FIXTURES, cc


class TestClean(unittest.TestCase):
    def test_strips_latex_debris_left_by_pandoc(self):
        self.assertEqual(cc.clean(r"Smith\, J. \allowbreak(2024)"), "Smith J. (2024)")

    def test_drops_markboth_running_heads(self):
        self.assertEqual(cc.clean(r"\markboth{Chapter}{Refs} Real text"), "Real text")

    def test_unescapes_pandoc_escapes_and_collapses_whitespace(self):
        self.assertEqual(cc.clean("O\\'Brien,   A.\n  (2020)"), "O'Brien, A. (2020)")

    def test_normalises_nbsp_and_non_breaking_hyphen(self):
        self.assertEqual(cc.clean("RFC 8259‑bis"), "RFC 8259-bis")


class TestStripCode(unittest.TestCase):
    def test_fenced_and_inline_code_are_removed(self):
        # Code is the one place where (Smith, 2020) and arr[1] are guaranteed
        # not to be citations, so it never reaches the finders.
        body = ("Text `foo(Date, 2020)` inline\n\n"
                "```python\nx = arr[1]\n```\n\n"
                "End (Jones, 2021).")
        stripped = cc.strip_code(body)
        self.assertNotIn("foo(", stripped)
        self.assertNotIn("arr", stripped)
        self.assertIn("(Jones, 2021)", stripped)

    def test_tilde_fences_are_removed_too(self):
        stripped = cc.strip_code("~~~\nx = [1]\n~~~\nFine (Jones, 2021).")
        self.assertNotIn("[1]", stripped)
        self.assertIn("(Jones, 2021)", stripped)

    def test_a_fence_with_extra_backticks_closes_on_the_same_opener(self):
        stripped = cc.strip_code("````\n```nested\n````\nFine (Jones, 2021).")
        self.assertNotIn("nested", stripped)
        self.assertIn("(Jones, 2021)", stripped)


class TestDetectStyle(unittest.TestCase):
    def test_the_author_date_fixture_is_detected_as_author_date(self):
        with open(os.path.join(FIXTURES, "sample.md"), encoding="utf-8") as fh:
            text = fh.read()
        body, block, heading, entries = cc.split_document(text)
        self.assertEqual(cc.detect_style(cc.strip_code(body), entries, heading), "author-date")

    def test_the_numeric_fixture_is_detected_as_numeric(self):
        with open(os.path.join(FIXTURES, "sample-numeric.md"), encoding="utf-8") as fh:
            text = fh.read()
        body, block, heading, entries = cc.split_document(text)
        self.assertEqual(cc.detect_style(cc.strip_code(body), entries, heading), "numeric")

    def test_a_numbered_list_cited_author_date_is_not_numeric(self):
        # The list is numbered markdown, but the body cites by name and year:
        # author-date with numbers attached, not a numeric style.
        text = (
            "As shown (Smith, 2020) and (Jones, 2021).\n\n"
            "## References\n\n"
            "1. Smith, J. (2020) 'A first paper', Journal of Things. doi:10.1/a\n\n"
            "2. Jones, K. (2021) 'A second paper', Journal of Things. doi:10.1/b\n\n"
            "3. Patel, R. (2022) 'A third paper', Journal of Things. doi:10.1/c\n"
        )
        body, block, heading, entries = cc.split_document(text)
        self.assertEqual(cc.detect_style(cc.strip_code(body), entries, heading), "author-date")

    def test_the_mla_fixture_is_detected_as_mla(self):
        with open(os.path.join(FIXTURES, "sample-mla.md"), encoding="utf-8") as fh:
            text = fh.read()
        body, block, heading, entries = cc.split_document(text)
        self.assertEqual(cc.detect_style(cc.strip_code(body), entries, heading), "mla")

    def test_the_notes_fixture_is_detected_as_notes(self):
        with open(os.path.join(FIXTURES, "sample-notes.md"), encoding="utf-8") as fh:
            rest, notes = cc.harvest_notes(fh.read())
        body, block, heading, entries = cc.split_document(rest)
        self.assertEqual(cc.detect_style(cc.strip_code(body), entries, heading, notes), "notes")

    def test_aside_footnotes_do_not_make_a_notes_document(self):
        # Definitions that read like clarifications, not citations, keep the
        # document in whatever style its list and body say.
        text = (
            "A term is defined here.[^1]\n\n"
            "## References\n\n"
            "Smith, J. (2020) 'A first paper', Journal of Things. doi:10.1/a\n\n"
            "Jones, K. (2021) 'A second paper', Journal of Things. doi:10.1/b\n\n"
            "Patel, R. (2022) 'A third paper', Journal of Things. doi:10.1/c\n\n"
            "[^1]: A clarification of the term, not a citation of anything.\n"
        )
        rest, notes = cc.harvest_notes(text)
        body, block, heading, entries = cc.split_document(rest)
        self.assertEqual(cc.detect_style(cc.strip_code(body), entries, heading, notes),
                         "author-date")

    def test_author_page_parentheticals_alone_do_not_make_mla(self):
        # Without a Works Cited heading, '(Smith 42)' is prose, not an MLA
        # citation, and the document stays author-date.
        text = (
            "As shown (Smith 42) in the earlier study.\n\n"
            "## References\n\n"
            "Smith, J. (2020) 'A first paper', Journal of Things. doi:10.1/a\n\n"
            "Jones, K. (2021) 'A second paper', Journal of Things. doi:10.1/b\n\n"
            "Patel, R. (2022) 'A third paper', Journal of Things. doi:10.1/c\n"
        )
        body, block, heading, entries = cc.split_document(text)
        self.assertEqual(cc.detect_style(cc.strip_code(body), entries, heading), "author-date")


class TestSplitDocument(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(FIXTURES, "sample.md"), encoding="utf-8") as fh:
            self.text = fh.read()

    def test_prefers_the_last_heading_that_actually_has_entries(self):
        # The fixture opens with a decoy '## References management' section. A
        # first-match-wins splitter would stop there and find no entries.
        body, block, heading, entries = cc.split_document(self.text)
        self.assertIn("References management", body)
        self.assertNotIn("References management", block)
        self.assertIn("Debenedetti", block)
        self.assertEqual(heading, "References")

    def test_body_excludes_the_reference_list(self):
        body, _, _, _ = cc.split_document(self.text)
        self.assertIn("Prompt injection was first characterised", body)
        self.assertNotIn("doi:10.1145", body)

    def test_bare_heading_fallback_for_unstyled_docx(self):
        # A .docx whose Word style never mapped to a heading level leaves the
        # word on a line of its own with no '#'.
        text = (
            "Body text citing Smith (2020) and others.\n\n"
            "**References**\n\n"
            "Smith, J. (2020) 'A first paper', Journal of Things. doi:10.1/a\n\n"
            "Jones, K. (2021) 'A second paper', Journal of Things. doi:10.1/b\n\n"
            "Patel, R. (2022) 'A third paper', Journal of Things. doi:10.1/c\n"
        )
        body, block, heading, entries = cc.split_document(text)
        self.assertIn("Body text", body)
        self.assertEqual(heading, "References")
        self.assertEqual(len(cc.split_entries(block)), 3)

    def test_exits_when_there_is_no_reference_list(self):
        with self.assertRaises(SystemExit):
            cc.split_document("# A document\n\nWith no reference list at all.\n")


class TestSplitEntries(unittest.TestCase):
    def test_blank_line_separated_entries(self):
        block = (
            "\nSmith, J. (2020) 'A paper about things', Journal of Things.\n\n"
            "Jones, K. (2021) 'Another paper about things', Journal of Things.\n"
        )
        self.assertEqual(len(cc.split_entries(block)), 2)

    def test_single_spaced_list_falls_back_to_one_entry_per_line(self):
        block = (
            "\nSmith, J. (2020) 'A paper about things', Journal of Things.\n"
            "Jones, K. (2021) 'Another paper about things', Journal of Things.\n"
            "Patel, R. (2022) 'A third paper about things', Journal of Things.\n"
            "Okafor, N. (2023) 'A fourth paper about things', Journal of Things.\n"
        )
        self.assertEqual(len(cc.split_entries(block)), 4)

    def test_bare_year_entries_are_admitted(self):
        block = (
            "\nSmith, John. 2020. \"A paper about things.\" Journal of Things.\n\n"
            "Jones, Karen. 2021. \"Another paper about things.\" Journal of Things.\n"
        )
        self.assertEqual(len(cc.split_entries(block)), 2)

    def test_single_spaced_bare_year_list_falls_back_to_one_entry_per_line(self):
        block = (
            "\nSmith, John. 2020. \"A paper about things.\" Journal of Things.\n"
            "Jones, Karen. 2021. \"Another paper about things.\" Journal of Things.\n"
            "Patel, Rupa. 2022. \"A third paper about things.\" Journal of Things.\n"
        )
        self.assertEqual(len(cc.split_entries(block)), 3)

    def test_prose_that_mentions_a_year_is_not_an_entry(self):
        # No period before the year: 'across 2019 and 2020' is a sentence,
        # not 'Smith, John. 2020.'
        block = "\nFieldwork was conducted across 2019 and 2020, and coded by hand.\n"
        self.assertEqual(cc.split_entries(block), [])

    def test_discards_table_rows_footnotes_and_images(self):
        block = (
            "\n| Column | Column |\n\n"
            "[^1]: A footnote that happens to mention 2020 in passing.\n\n"
            "![A figure caption from 2020 that is not a reference](fig.png)\n\n"
            "Smith, J. (2020) 'A real entry about things', Journal of Things.\n"
        )
        self.assertEqual(cc.split_entries(block), [
            "Smith, J. (2020) 'A real entry about things', Journal of Things."])

    def test_requires_a_year_so_stray_prose_is_not_an_entry(self):
        block = "\nThis paragraph is long enough to pass the length filter easily.\n"
        self.assertEqual(cc.split_entries(block), [])


class TestParseEntry(unittest.TestCase):
    def test_person_author_year_and_quoted_title(self):
        ref = cc.parse_entry(
            "Smith, J. and Jones, K. (2020) 'A paper about things', "
            "Journal of Things.")
        self.assertEqual(ref.name, "Smith")
        self.assertFalse(ref.is_org)
        self.assertEqual(ref.year, "2020")
        self.assertEqual(ref.title, "A paper about things")
        self.assertEqual(ref.key, "smith|2020")

    def test_particle_surname_is_kept_as_person(self):
        ref = cc.parse_entry(
            "van der Waals, J. D. (2020) 'A Study of Things', Journal of Things.")
        self.assertEqual(ref.name, "van der Waals")
        self.assertFalse(ref.is_org)
        self.assertEqual(ref.year, "2020")
        self.assertEqual(ref.title, "A Study of Things")
        self.assertEqual(ref.key, "van der waals|2020")

    def test_organisation_author_is_kept_whole(self):
        ref = cc.parse_entry(
            "Anthropic (2024) 'Model Context Protocol specification'. "
            "Available at: https://modelcontextprotocol.io/specification")
        self.assertTrue(ref.is_org)
        self.assertEqual(ref.name, "Anthropic")
        self.assertEqual(ref.key, "anthropic|2024")

    def test_year_suffix_is_captured(self):
        ref = cc.parse_entry("IETF (2025a) 'The OAuth 2.1 Authorization Framework'.")
        self.assertEqual((ref.year, ref.suffix), ("2025", "a"))
        self.assertEqual(ref.key, "ietf|2025a")

    def test_apostrophe_inside_a_quoted_title_does_not_end_it(self):
        # The closing quote is only the one followed by punctuation or the end.
        ref = cc.parse_entry(
            "Greshake, K. (2023) 'Not what you've signed up for: Compromising "
            "Real-World LLM-Integrated Applications', Proceedings of AISec.")
        self.assertTrue(ref.title.startswith("Not what you've signed up for"))
        self.assertTrue(ref.title.endswith("Applications"))

    def test_identifier_routing(self):
        cases = [
            ("Debenedetti, E. (2024) 'AgentDojo: A dynamic environment', "
             "arXiv:2406.13352.", "arxiv", "arxiv", "2406.13352"),
            ("Greshake, K. (2023) 'Not what you signed up for', AISec. "
             "doi:10.1145/3605764.3623985.", "doi", "doi", "10.1145/3605764.3623985"),
            ("Bradner, S. (1997) 'Key words for use in RFCs', RFC 2119.",
             "rfc", "rfc", "2119"),
        ]
        for raw, kind, attr, value in cases:
            with self.subTest(kind=kind):
                ref = cc.parse_entry(raw)
                self.assertEqual(ref.kind, kind)
                self.assertEqual(getattr(ref, attr), value)

    def test_draft_revision_is_split_off_the_draft_name(self):
        ref = cc.parse_entry(
            "IETF (2025) 'The OAuth 2.1 Authorization Framework', "
            "Internet-Draft draft-ietf-oauth-v2-1-13.")
        self.assertEqual(ref.kind, "ietf-draft")
        self.assertEqual(ref.draft, "draft-ietf-oauth-v2-1")
        self.assertEqual(ref.draft_rev, "13")

    def test_quoted_title_in_an_academic_venue_is_a_paper(self):
        ref = cc.parse_entry(
            "Smith, J. (2020) 'A paper about things', "
            "Proceedings of the 3rd Workshop on Things.")
        self.assertEqual(ref.kind, "paper")

    def test_url_only_entry_is_web(self):
        ref = cc.parse_entry(
            "Example Corp (2024) 'A blog post about things'. "
            "Available at: https://example.com/post")
        self.assertEqual(ref.kind, "web")
        self.assertEqual(ref.url, "https://example.com/post")

    def test_accessed_date_is_lifted_out_of_the_title(self):
        ref = cc.parse_entry(
            "Example Corp (2024) 'A blog post about things'. Available at: "
            "https://example.com/post (Accessed: 3 June 2026).")
        self.assertEqual(ref.accessed, "3 June 2026")
        self.assertNotIn("Accessed", ref.title)

    def test_a_bare_accessed_date_is_lifted_out_too(self):
        # MLA writes the access date without parentheses, at the end.
        ref = cc.parse_entry(
            "Smith, John. *The Book Title*. Publisher, 2020. Accessed 3 Mar. 2021.")
        self.assertEqual(ref.accessed, "3 Mar. 2021")
        self.assertNotEqual(ref.year, "2021")

    def test_an_arxiv_doi_routes_to_arxiv_not_crossref(self):
        # 10.48550 is registered with DataCite; Crossref has no record of it,
        # so routing it as an ordinary DOI reports a real paper NOT_FOUND.
        ref = cc.parse_entry(
            "Gao, L. et al. (2024) 'Scaling and evaluating sparse autoencoders', "
            "*arXiv*, 2406.04093. Available at: https://doi.org/10.48550/arXiv.2406.04093")
        self.assertEqual(ref.arxiv, "2406.04093")
        self.assertEqual(ref.kind, "arxiv")

    def test_an_ordinary_doi_is_untouched_by_the_arxiv_route(self):
        ref = cc.parse_entry(
            "Jones, K. (2020) 'A paper about things', Journal of Things. "
            "doi:10.1145/3605764.3623985")
        self.assertEqual(ref.arxiv, "")
        self.assertEqual(ref.kind, "doi")

    def test_trailing_url_punctuation_is_trimmed(self):
        ref = cc.parse_entry(
            "Example Corp (2024) 'A post'. Available at: https://example.com/post.")
        self.assertEqual(ref.url, "https://example.com/post")

    def test_series_identifier_is_trimmed_from_an_unquoted_title(self):
        ref = cc.parse_entry(
            "Bradner, S. (1997) Key words for use in RFCs, RFC 2119.")
        self.assertNotIn("RFC 2119", ref.title)


class TestUnparsedEntry(unittest.TestCase):
    """An entry no grammar claims still has to be distinguishable from the
    next one, and must not be sent off for verification as a paper."""

    def test_numbered_entries_get_distinct_keys(self):
        a = cc.parse_entry("[1] Technical Committee Report No. 14, Standards Body, London.")
        b = cc.parse_entry("[2] Technical Committee Report No. 15, Standards Body, London.")
        self.assertEqual(a.style, "")
        self.assertNotEqual(a.key, b.key)

    def test_unnumbered_entries_get_distinct_keys(self):
        a = cc.parse_entry("Technical Committee Report No. 14, Standards Body, London.")
        b = cc.parse_entry("Technical Committee Report No. 15, Standards Body, London.")
        self.assertNotEqual(a.key, b.key)

    def test_an_unparsed_entry_is_not_a_paper(self):
        # 'paper' sends the entry to a Crossref title search, which would
        # report NOT_FOUND for what is really a parse gap.
        ref = cc.parse_entry(
            "Technical Committee Report No. 14. Proceedings of the Standards Body, London.")
        self.assertNotEqual(ref.kind, "paper")


class TestParseChicagoEntry(unittest.TestCase):
    """Chicago author-date: the year stands on its own between periods."""

    def test_bare_year_between_periods(self):
        ref = cc.parse_entry(
            'Smith, John. 2020. "A paper about things." Journal of Things.')
        self.assertEqual(ref.style, "chicago-ad")
        self.assertEqual(ref.name, "Smith")
        self.assertFalse(ref.is_org)
        self.assertEqual(ref.year, "2020")
        self.assertEqual(ref.title, "A paper about things")
        self.assertEqual(ref.container, "Journal of Things.")
        self.assertEqual(ref.key, "smith|2020")

    def test_full_given_name_is_a_person_not_an_organisation(self):
        ref = cc.parse_entry('Smith, John. 2020. "A paper." Journal.')
        self.assertFalse(ref.is_org)
        self.assertEqual(ref.name, "Smith")

    def test_organisation_entry_with_bare_year(self):
        ref = cc.parse_entry(
            'Anthropic. 2024. "Model Context Protocol Specification." '
            "Available at: https://modelcontextprotocol.io/specification")
        self.assertTrue(ref.is_org)
        self.assertEqual(ref.name, "Anthropic")
        self.assertEqual(ref.key, "anthropic|2024")

    def test_year_suffix_after_a_bare_year(self):
        ref = cc.parse_entry('Smith, John. 2020a. "First." Journal.')
        self.assertEqual((ref.year, ref.suffix, ref.key), ("2020", "a", "smith|2020a"))

    def test_only_the_first_author_is_inverted_the_rest_stay_natural(self):
        ref = cc.parse_entry(
            'Debenedetti, Edoardo, Jiace Zhang, and Nicholas Carlini. '
            '2024. "AgentDojo." arXiv:2406.13352.')
        self.assertEqual(ref.name, "Debenedetti")
        self.assertFalse(ref.is_org)
        self.assertEqual(ref.arxiv, "2406.13352")

    def test_punctuation_inside_the_closing_quote_is_not_part_of_the_title(self):
        # Chicago and IEEE put the period and comma inside the quotes.
        ref = cc.parse_entry('Smith, John. 2020. "A paper about things." Journal.')
        self.assertEqual(ref.title, "A paper about things")
        self.assertNotIn('"', ref.title)

    def test_unquoted_title_after_a_bare_year(self):
        ref = cc.parse_entry("Kurzweil, R. 2005. The Singularity Is Near. Viking.")
        self.assertEqual(ref.title, "The Singularity Is Near")
        self.assertEqual(ref.container, "Viking.")

    def test_quoted_title_in_an_academic_venue_is_a_paper_with_a_bare_year(self):
        ref = cc.parse_entry('Smith, John. 2020. "A paper about things." '
                             "Journal of Things 5, no. 2: 10-20.")
        self.assertEqual(ref.kind, "paper")


class TestParseIeeeEntry(unittest.TestCase):
    """A numbered list in IEEE shape: initials-first authors, quoted title,
    bare year after the title."""

    def test_number_marker_title_authors_and_year(self):
        ref = cc.parse_entry(
            '[1] S. Bradner, "Key Words for Use in RFCs to Indicate Requirement '
            'Levels," RFC 2119, Mar. 1997.')
        self.assertEqual(ref.number, 1)
        self.assertEqual(ref.style, "ieee")
        self.assertEqual(ref.name, "Bradner")
        self.assertFalse(ref.is_org)
        self.assertEqual(ref.year, "1997")
        self.assertEqual(ref.title, "Key Words for Use in RFCs to Indicate "
                                    "Requirement Levels")
        self.assertEqual(ref.rfc, "2119")
        self.assertEqual(ref.kind, "rfc")

    def test_multi_author_entry_takes_the_first_surname(self):
        ref = cc.parse_entry(
            '[2] K. Greshake, S. Abdelnabi, and S. Mishra, "Not What You\'ve '
            'Signed Up For," in Proceedings of AISec, 2023.')
        self.assertEqual(ref.name, "Greshake")
        self.assertEqual(ref.year, "2023")

    def test_et_al_does_not_become_the_surname(self):
        ref = cc.parse_entry('[3] J. Smith et al., "A paper," Venue, 2020.')
        self.assertEqual(ref.name, "Smith")

    def test_hyphenated_initials_are_a_person(self):
        ref = cc.parse_entry('[4] A.-B. Smith, "A paper," Venue, 2020.')
        self.assertFalse(ref.is_org)
        self.assertEqual(ref.name, "Smith")

    def test_organisation_author_before_a_quoted_title(self):
        ref = cc.parse_entry(
            '[5] Internet Engineering Task Force, "The OAuth 2.1 Authorization '
            'Framework," Internet-Draft draft-ietf-oauth-v2-1-13, 2025.')
        self.assertTrue(ref.is_org)
        self.assertEqual(ref.name, "Internet Engineering Task Force")
        self.assertEqual(ref.draft, "draft-ietf-oauth-v2-1")
        self.assertEqual(ref.draft_rev, "13")
        self.assertEqual(ref.kind, "ietf-draft")

    def test_the_year_is_the_last_one_after_the_title(self):
        # A year inside the title must not become the publication year.
        ref = cc.parse_entry('[6] J. Smith, "A 2020 retrospective," Venue, 2021.')
        self.assertEqual(ref.year, "2021")

    def test_a_quoted_title_after_a_parenthesised_year_stays_author_date(self):
        # IEEE entries can carry '(2020)' inside a proceedings name; the
        # parenthesised year there must not be mistaken for the entry's own.
        ref = cc.parse_entry(
            '[7] J. Smith, "A paper," in Proceedings of the IEEE Conference '
            "(2020), pp. 1-5.")
        self.assertEqual(ref.name, "Smith")
        self.assertEqual(ref.year, "2020")

    def test_numbered_author_date_entries_keep_their_grammar(self):
        # A Harvard list written as a markdown numbered list is still
        # author-date; the number is recorded alongside.
        ref = cc.parse_entry("1. Smith, J. (2020) 'A paper about things', Journal.")
        self.assertEqual(ref.number, 1)
        self.assertEqual(ref.style, "author-date")
        self.assertEqual(ref.name, "Smith")
        self.assertEqual(ref.year, "2020")


class TestParseVancouverEntry(unittest.TestCase):
    """Vancouver/AMA: initials glued to the surname, unquoted title, year
    after the container's period."""

    def test_author_block_and_semicolon_year(self):
        ref = cc.parse_entry(
            "1. Smith JA, Jones KB. A title of work. Journal of Things. "
            "2020;15(2):123-45.")
        self.assertEqual(ref.number, 1)
        self.assertEqual(ref.style, "vancouver")
        self.assertEqual(ref.name, "Smith")
        self.assertFalse(ref.is_org)
        self.assertEqual(ref.year, "2020")
        self.assertEqual(ref.title, "A title of work")
        self.assertEqual(ref.container, "Journal of Things")

    def test_et_al_in_the_author_block(self):
        ref = cc.parse_entry("2. Smith JA, Jones KB, et al. Another title. Journal. 2021;1:1-2.")
        self.assertEqual(ref.name, "Smith")
        self.assertEqual(ref.year, "2021")
        self.assertEqual(ref.title, "Another title")

    def test_year_at_the_end_of_the_entry(self):
        ref = cc.parse_entry("3. Lee C. A third work. Journal of Stuff. 2019.")
        self.assertEqual((ref.name, ref.year, ref.title), ("Lee", "2019", "A third work"))

    def test_a_quoted_vancouver_title_is_not_an_organisation(self):
        ref = cc.parse_entry('4. Smith JA. "A quoted title." Journal of Things. 2020;1:1.')
        self.assertEqual(ref.style, "vancouver")
        self.assertFalse(ref.is_org)
        self.assertEqual(ref.name, "Smith")
        self.assertEqual(ref.title, "A quoted title")


class TestVancouverMonthDate(unittest.TestCase):
    def test_a_month_qualified_date_still_parses(self):
        # '2020 Jan;' is the NLM form for a monthly journal.
        ref = cc.parse_entry(
            "Smith JA, Jones KB. Title of the article here. J Clin Med. "
            "2020 Jan;15(2):123-45.")
        self.assertEqual(ref.style, "vancouver")
        self.assertEqual(ref.year, "2020")
        self.assertEqual(ref.title, "Title of the article here")


class TestNumberedEntryGates(unittest.TestCase):
    def test_numbered_entries_need_no_year(self):
        block = (
            "\n[1] S. Bradner, \"Key Words for Use in RFCs,\" RFC 2119, 1997.\n\n"
            "[2] K. Greshake, \"Not What You've Signed Up For,\" AISec, 2023.\n\n"
            "[3] J. Smith, \"A third paper about things,\" Venue, 2020.\n"
        )
        entries = cc.split_entries(block)
        self.assertEqual(len(entries), 3)

    def test_single_spaced_numbered_list_falls_back_one_per_line(self):
        block = (
            "\n[1] S. Bradner, \"Key Words for Use in RFCs,\" RFC 2119, 1997.\n"
            "[2] K. Greshake, \"Not What You've Signed Up For,\" AISec, 2023.\n"
            "[3] J. Smith, \"A third paper about things,\" Venue, 2020.\n"
        )
        self.assertEqual(len(cc.split_entries(block)), 3)

    def test_a_doi_leading_a_chunk_is_not_a_number_marker(self):
        # '10.1145/...' has no whitespace after the period, so it must not be
        # read as entry number 10.
        chunk = "10.1145/3605764.3623985. A stray line that is long enough to pass the length gate."
        self.assertIsNone(cc.NUM_MARKER.match(chunk))


class TestParseMlaEntry(unittest.TestCase):
    """MLA: 'Surname, Given. "Title." Container, year, pages.' -- the year
    trails the container, so the entry is claimed by the quoted-title
    strategy."""

    def test_year_after_the_title(self):
        ref = cc.parse_entry(
            'Smith, John. "A Paper About Things." Journal of Things, '
            "vol. 5, no. 2, 2020, pp. 10-20.")
        self.assertEqual(ref.style, "mla")
        self.assertEqual(ref.name, "Smith")
        self.assertFalse(ref.is_org)
        self.assertEqual(ref.year, "2020")
        self.assertEqual(ref.title, "A Paper About Things")
        self.assertEqual(ref.container,
                         "Journal of Things, vol. 5, no. 2, 2020, pp. 10-20.")
        self.assertEqual(ref.kind, "paper")

    def test_et_al_in_the_author_segment(self):
        ref = cc.parse_entry(
            'Greshake, Kai, et al. "Not What You\'ve Signed Up For." '
            "Proceedings of AISec, 2023, pp. 79-90. doi:10.1145/3605764.3623985.")
        self.assertEqual(ref.style, "mla")
        self.assertEqual(ref.name, "Greshake")
        self.assertEqual(ref.year, "2023")
        self.assertEqual(ref.doi, "10.1145/3605764.3623985")

    def test_an_undated_web_entry_is_allowed(self):
        ref = cc.parse_entry(
            'Anthropic. "Model Context Protocol Specification." '
            "https://modelcontextprotocol.io/specification. Accessed 3 June 2026.")
        self.assertEqual(ref.style, "mla")
        self.assertTrue(ref.is_org)
        self.assertEqual(ref.name, "Anthropic")
        self.assertEqual(ref.year, "")
        self.assertEqual(ref.kind, "web")

    def test_a_year_inside_the_title_is_not_the_publication_year(self):
        ref = cc.parse_entry(
            'Doe, Jane. "The 2020 Election Explained." Politics Weekly.')
        self.assertEqual(ref.year, "")

    def test_a_suffixed_year_keeps_its_suffix(self):
        a = cc.parse_entry("Smith, J. 'A Study of Things', Journal of Things, 2020a.")
        b = cc.parse_entry("Smith, J. 'Another Study', Journal of Things, 2020b.")
        self.assertEqual((a.year, a.suffix), ("2020", "a"))
        self.assertEqual(a.key, "smith|2020a")
        self.assertNotEqual(a.key, b.key)

    def test_an_access_date_is_not_the_publication_year(self):
        ref = cc.parse_entry(
            'Anthropic. "Model Context Protocol Specification." '
            "https://example.com/spec. Accessed 3 June 2026.")
        self.assertEqual(ref.year, "")


class TestYearlessEntryGate(unittest.TestCase):
    def test_an_undated_quoted_entry_passes_under_works_cited(self):
        block = ('Anthropic. "A specification of things." https://example.com. '
                 "Accessed 3 June 2026.")
        self.assertEqual(len(cc.split_entries("\n" + block + "\n", True)), 1)

    def test_the_same_entry_is_rejected_under_references(self):
        # A References list is expected to date everything; an undated chunk
        # there is prose or a broken entry, not a free pass.
        block = ('Anthropic. "A specification of things." https://example.com. '
                 "Accessed 3 June 2026.")
        self.assertEqual(cc.split_entries("\n" + block + "\n"), [])

    def test_undated_prose_is_still_rejected_under_works_cited(self):
        # No quoted title, so not an entry however lenient the heading.
        block = "\nThe following list gathers sources consulted during the work.\n"
        self.assertEqual(cc.split_entries(block, True), [])


class TestHarvestNotes(unittest.TestCase):
    def test_definitions_are_extracted_and_removed(self):
        text = ("Body with a marker.[^1] More body.\n\n"
                "[^1]: Kai Greshake, \"A paper,\" Venue, 2023.\n")
        rest, notes = cc.harvest_notes(text)
        self.assertEqual(notes, {1: 'Kai Greshake, "A paper," Venue, 2023.'})
        self.assertNotIn("[^1]:", rest)
        self.assertIn("Body with a marker.[^1] More body.", rest)

    def test_indented_continuation_lines_belong_to_the_note(self):
        text = ("[^2]: A note whose text wraps\n"
                "    onto a second line.\n\nUnrelated paragraph.\n")
        rest, notes = cc.harvest_notes(text)
        self.assertEqual(notes, {2: "A note whose text wraps onto a second line."})
        self.assertNotIn("wraps", rest)
        self.assertIn("Unrelated paragraph.", rest)

    def test_a_repeated_number_keeps_the_first_definition(self):
        text = "[^1]: First.\n\n[^1]: Second.\n"
        _, notes = cc.harvest_notes(text)
        self.assertEqual(notes, {1: "First."})


class TestNoteHelpers(unittest.TestCase):
    def test_inverted_surname(self):
        self.assertEqual(cc.note_surname('Greshake, Kai, "A paper," Venue.'), "Greshake")

    def test_natural_order_surname(self):
        self.assertEqual(cc.note_surname('Kai Greshake, "A paper," Venue.'), "Greshake")

    def test_short_form_surname(self):
        self.assertEqual(cc.note_surname('Greshake, "Not What," 24.'), "Greshake")

    def test_an_apostrophe_is_not_an_opening_quote(self):
        self.assertEqual(cc.note_surname('O\'Brien, "Some Long Title," 24.'), "O'Brien")

    def test_a_shortened_note_is_detected(self):
        ref = cc.parse_entry('Greshake, "Not What," 24.')
        self.assertTrue(cc.is_short_note(ref))

    def test_a_full_note_is_not_short(self):
        ref = cc.parse_entry(
            'Kai Greshake, "Not What You\'ve Signed Up For," in Proceedings '
            "of AISec, 2023.")
        self.assertFalse(cc.is_short_note(ref))

    def test_an_undated_entry_with_a_url_is_not_short(self):
        ref = cc.parse_entry(
            'Anthropic. "A specification." https://example.com. Accessed 3 June 2026.')
        self.assertFalse(cc.is_short_note(ref))

    def test_find_note_target_matches_a_shortened_title_by_prefix(self):
        full = cc.parse_entry(
            'Greshake, Kai. "Not What You\'ve Signed Up For: Compromising '
            'Real-World Applications," AISec, 2023.')
        short = cc.parse_entry('Greshake, "Not What," 24.')
        self.assertIs(cc.find_note_target(short, [full]), full)

    def test_find_note_target_refuses_a_surname_that_merely_contains_it(self):
        # 'Lee' is not 'Leeson', however well the titles match.
        full = cc.parse_entry(
            'Leeson, Peter. 2019. "Some Long Title Here." Journal of Things.')
        short = cc.parse_entry('Lee, "Some Long Title Here," 24.')
        self.assertIsNone(cc.find_note_target(short, [full]))

    def test_find_note_target_refuses_a_different_work(self):
        full = cc.parse_entry('Greshake, Kai. "A different paper entirely," Venue, 2023.')
        short = cc.parse_entry('Greshake, "Not What," 24.')
        self.assertIsNone(cc.find_note_target(short, [full]))


class TestBuildNoteRefs(unittest.TestCase):
    def test_a_full_note_becomes_an_entry(self):
        notes = {1: 'Kai Greshake, "A paper about things," Venue, 2023.'}
        refs, note_map = cc.build_note_refs(notes, [])
        self.assertEqual(len(refs), 1)
        self.assertEqual(note_map, {1: refs[0].key})
        # The footnote number is not a reference-list position, so it is not
        # written into Reference.number, which by_number resolves markers with.
        self.assertEqual(refs[0].number, 0)

    def test_a_note_already_in_the_bibliography_links_instead(self):
        bib = [cc.parse_entry(
            'Greshake, Kai. "Not What You\'ve Signed Up For," AISec, 2023. '
            "doi:10.1145/3605764.3623985.")]
        notes = {1: 'Kai Greshake, "Not What You\'ve Signed Up For," '
                    "in Proceedings of AISec, 2023."}
        refs, note_map = cc.build_note_refs(notes, bib)
        self.assertEqual(refs, [])
        self.assertEqual(note_map, {1: bib[0].key})

    def test_a_shortened_note_links_to_the_full_one(self):
        notes = {1: 'Kai Greshake, "Not What You\'ve Signed Up For," Venue, 2023.',
                 2: 'Greshake, "Not What," 24.'}
        refs, note_map = cc.build_note_refs(notes, [])
        self.assertEqual(len(refs), 1)
        self.assertEqual(note_map[2], note_map[1])

    def test_ibid_repeats_the_previous_note(self):
        notes = {1: 'Kai Greshake, "Not What You\'ve Signed Up For," Venue, 2023.',
                 2: "Ibid., 25."}
        refs, note_map = cc.build_note_refs(notes, [])
        self.assertEqual(len(refs), 1)
        self.assertEqual(note_map[2], note_map[1])

    def test_an_unlinked_shortened_note_is_kept_with_a_caveat(self):
        notes = {1: 'Smith, "A short title," 24.'}
        refs, _ = cc.build_note_refs(notes, [])
        self.assertEqual(len(refs), 1)
        self.assertIn("shortened note", refs[0].notes[0])

    def test_a_leading_ibid_is_flagged_rather_than_dropped(self):
        notes = {1: "Ibid., 25."}
        refs, _ = cc.build_note_refs(notes, [])
        self.assertEqual(len(refs), 1)
        self.assertIn("no earlier citation", refs[0].notes[0])


if __name__ == "__main__":
    unittest.main()
