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
        body, block = cc.split_document(text)
        self.assertEqual(cc.detect_style(body, block), "author-date")


class TestSplitDocument(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(FIXTURES, "sample.md"), encoding="utf-8") as fh:
            self.text = fh.read()

    def test_prefers_the_last_heading_that_actually_has_entries(self):
        # The fixture opens with a decoy '## References management' section. A
        # first-match-wins splitter would stop there and find no entries.
        body, block = cc.split_document(self.text)
        self.assertIn("References management", body)
        self.assertNotIn("References management", block)
        self.assertIn("Debenedetti", block)

    def test_body_excludes_the_reference_list(self):
        body, _ = cc.split_document(self.text)
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
        body, block = cc.split_document(text)
        self.assertIn("Body text", body)
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

    def test_trailing_url_punctuation_is_trimmed(self):
        ref = cc.parse_entry(
            "Example Corp (2024) 'A post'. Available at: https://example.com/post.")
        self.assertEqual(ref.url, "https://example.com/post")

    def test_series_identifier_is_trimmed_from_an_unquoted_title(self):
        ref = cc.parse_entry(
            "Bradner, S. (1997) Key words for use in RFCs, RFC 2119.")
        self.assertNotIn("RFC 2119", ref.title)


if __name__ == "__main__":
    unittest.main()
