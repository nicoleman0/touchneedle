"""In-text citation detection and matching against the reference list."""

import os
import unittest

from context import FIXTURES, cc


class TestFindCitations(unittest.TestCase):
    def names(self, body):
        return [(c.name, c.year + c.suffix, c.form) for c in cc.find_citations(body)]

    def test_parenthetical_and_narrative_forms(self):
        found = self.names(
            "As shown (Smith, 2020), and Jones (2021) agreed.")
        self.assertIn(("Smith", "2020", "parenthetical"), found)
        self.assertIn(("Jones", "2021", "narrative"), found)

    def test_semicolon_separated_group_yields_one_citation_each(self):
        found = self.names("Several agree (Smith, 2020; Jones, 2021; Patel, 2022).")
        self.assertEqual([n for n, _, _ in found], ["Smith", "Jones", "Patel"])

    def test_year_suffix_is_carried_through(self):
        self.assertIn(("IETF", "2025a", "parenthetical"),
                      self.names("The draft (IETF, 2025a) says so."))

    def test_et_al_is_part_of_the_name(self):
        found = self.names("Reported by Greshake et al. (2023) in detail.")
        self.assertEqual(found, [("Greshake et al.", "2023", "narrative")])

    def test_cross_references_are_not_citations(self):
        for noise in ("(Table 3, 2024)", "(Figure 2, 2024)", "(Section 4, 2024)",
                      "(see Smith 2020, 2021)", "(Appendix B, 2024)"):
            with self.subTest(noise=noise):
                self.assertEqual(self.names("Text " + noise + " more text."), [])

    def test_chicago_no_comma_parenthetical(self):
        found = self.names("The vocabulary (Bradner 1997) predates.")
        self.assertIn(("Bradner", "1997", "parenthetical"), found)

    def test_apa_page_locator_is_carried_on_the_citation(self):
        cite = cc.find_citations("As shown (Smith, 2020, p. 5) and elsewhere.")[0]
        self.assertEqual((cite.name, cite.year), ("Smith", "2020"))
        self.assertEqual(cite.page, "p. 5")

    def test_harvard_page_only_locator(self):
        cite = cc.find_citations("As shown (Smith, 2020, 25) and elsewhere.")[0]
        self.assertEqual(cite.page, "25")

    def test_narrative_citation_with_page_locator(self):
        cite = cc.find_citations("Smith (2020, pp. 4-6) argues the point.")[0]
        self.assertEqual(cite.form, "narrative")
        self.assertEqual(cite.page, "pp. 4-6")

    def test_trailing_words_after_the_year_are_not_a_citation(self):
        # Anything after the year that is not a page locator disqualifies the
        # match rather than being silently swallowed.
        self.assertEqual(self.names("See (Smith, 2020 and friends) for more."), [])

    def test_accessed_dates_are_not_citations(self):
        self.assertEqual(self.names("The page (Accessed: 1 May 2026) is live."), [])

    def test_lowercase_openers_are_rejected(self):
        self.assertEqual(self.names("Built in the period (spring, 2024) here."), [])

    def test_context_is_captured_for_the_claim_worklist(self):
        body = ("An unrelated sentence sits here. "
                "Injection is the dominant failure mode (Smith, 2020). "
                "Another unrelated sentence follows.")
        cite = cc.find_citations(body)[0]
        self.assertIn("Injection is the dominant failure mode", cite.context)
        self.assertNotIn("An unrelated sentence sits here", cite.context)


class TestNormalise(unittest.TestCase):
    def test_strips_accents_case_and_punctuation(self):
        self.assertEqual(cc.normalise("Bär-Öztürk, A."), "bar ozturk a")

    def test_drops_et_al(self):
        self.assertEqual(cc.normalise("Greshake et al."), "greshake")

    def test_citation_key_keeps_only_the_first_author(self):
        self.assertEqual(cc.citation_key("Smith and Jones", "2020", ""), "smith|2020")
        self.assertEqual(cc.citation_key("Smith & Jones", "2020", "b"), "smith|2020b")


class TestMatchCitations(unittest.TestCase):
    def setUp(self):
        self.refs = [
            cc.parse_entry("Smith, J. and Jones, K. (2020) 'A paper', Journal."),
            cc.parse_entry("IETF (2025a) 'The OAuth 2.1 Framework', Internet-Draft."),
            cc.parse_entry("IETF (2025b) 'OAuth Security Topics', Internet-Draft."),
        ]

    def match(self, body):
        return cc.match_citations(self.refs, cc.find_citations(body))

    def test_surname_only_citation_matches_a_multi_author_entry(self):
        cite = self.match("As shown (Smith et al., 2020).")[0]
        self.assertEqual(cite.key, "smith|2020")

    def test_organisation_matches_on_its_full_name(self):
        cite = self.match("The draft (IETF, 2025a) says so.")[0]
        self.assertEqual(cite.key, "ietf|2025a")

    def test_suffix_disambiguates_two_entries_from_one_author_year(self):
        cites = self.match("Both (IETF, 2025a) and (IETF, 2025b) apply.")
        self.assertEqual([c.key for c in cites], ["ietf|2025a", "ietf|2025b"])

    def test_citation_with_no_entry_is_left_unmatched(self):
        self.assertEqual(self.match("An orphan (Nonexistent, 2019).")[0].key, "")

    def test_matching_records_which_entries_were_cited(self):
        self.match("As shown (Smith, 2020).")
        cited = {r.key: bool(r.cited_by) for r in self.refs}
        self.assertTrue(cited["smith|2020"])
        self.assertFalse(cited["ietf|2025a"])


class TestFindNumericCitations(unittest.TestCase):
    def numbers(self, body):
        return [c.number for c in cc.find_numeric_citations(body)]

    def test_bracket_marker(self):
        self.assertEqual(self.numbers("As shown [3] previously."), [3])

    def test_comma_and_semicolon_groups(self):
        self.assertEqual(self.numbers("As shown [2, 5] and [3;7] previously."),
                         [2, 5, 3, 7])

    def test_a_range_expands(self):
        self.assertEqual(self.numbers("As shown [5-7] previously."), [5, 6, 7])

    def test_mixed_group_and_range(self):
        self.assertEqual(self.numbers("As shown [2, 5-7] previously."),
                         [2, 5, 6, 7])

    def test_dashed_bracket_pair_expands_without_duplicates(self):
        self.assertEqual(self.numbers("As shown [1]–[3] previously."), [1, 2, 3])

    def test_reversed_range_is_not_a_citation(self):
        self.assertEqual(self.numbers("As shown [7-3] previously."), [])

    def test_pandoc_superscript(self):
        self.assertEqual(self.numbers("Shown here.^8^"), [8])

    def test_exponent_looking_superscripts_are_not_citations(self):
        self.assertEqual(self.numbers("E = mc^2^ and x^10^ and f^3^."), [])

    def test_unicode_superscripts(self):
        self.assertEqual(self.numbers("Vancouver style.¹² Done."), [12])

    def test_markdown_links_are_not_citations(self):
        body = ("See [1]: https://example.com and [text][2] and [3](url) "
                "for more.")
        self.assertEqual(self.numbers(body), [])

    def test_footnote_markers_are_not_numeric_citations(self):
        self.assertEqual(self.numbers("A footnote[^1] here."), [])

    def test_context_is_captured(self):
        cite = cc.find_numeric_citations(
            "One sentence. The claim appears here [4]. Another sentence.")[0]
        self.assertIn("The claim appears here", cite.context)
        self.assertNotIn("One sentence", cite.context)


class TestMatchNumericCitations(unittest.TestCase):
    def setUp(self):
        self.refs = [
            cc.parse_entry('[1] S. Bradner, "Key Words for Use in RFCs," RFC 2119, 1997.'),
            cc.parse_entry("[2] K. Greshake, \"Not What You've Signed Up For,\" AISec, 2023."),
        ]

    def match(self, body):
        return cc.match_citations(self.refs, cc.find_numeric_citations(body))

    def test_a_marker_resolves_to_its_entry(self):
        cites = self.match("As shown [1].")
        self.assertEqual(cites[0].key, self.refs[0].key)
        self.assertTrue(self.refs[0].cited_by)
        self.assertFalse(self.refs[1].cited_by)

    def test_a_marker_beyond_the_list_is_left_unresolved(self):
        cites = self.match("An orphan [9].")
        self.assertEqual(cites[0].key, "")


class TestAmbiguousSuffixes(unittest.TestCase):
    def test_flags_a_bare_citation_when_the_list_splits_a_b(self):
        refs = [cc.parse_entry("IETF (2025a) 'The OAuth 2.1 Framework', Internet-Draft."),
                cc.parse_entry("IETF (2025b) 'OAuth Security Topics', Internet-Draft.")]
        cites = cc.match_citations(refs, cc.find_citations("The draft (IETF, 2025) says."))
        problems = cc.ambiguous_suffixes(refs, cites)
        self.assertTrue(any("without a suffix" in p for p in problems))

    def test_flags_a_list_entry_that_is_missing_its_suffix(self):
        refs = [cc.parse_entry("IETF (2025) 'The OAuth 2.1 Framework', Internet-Draft."),
                cc.parse_entry("IETF (2025b) 'OAuth Security Topics', Internet-Draft.")]
        problems = cc.ambiguous_suffixes(refs, [])
        self.assertTrue(any("not all carry an a/b suffix" in p for p in problems))

    def test_silent_when_suffixes_are_used_consistently(self):
        with open(os.path.join(FIXTURES, "sample.md"), encoding="utf-8") as fh:
            body, block, _ = cc.split_document(fh.read())
        refs = [cc.parse_entry(e) for e in cc.split_entries(block)]
        cites = cc.match_citations(refs, cc.find_citations(body))
        self.assertEqual(cc.ambiguous_suffixes(refs, cites), [])


class TestFixtureEndToEnd(unittest.TestCase):
    """The fixture is the contract: what the parser is expected to find."""

    @classmethod
    def setUpClass(cls):
        cls.refs, cls.cites, cls.style = cc.collect(os.path.join(FIXTURES, "sample.md"))

    def test_every_entry_is_parsed(self):
        self.assertEqual(len(self.refs), 8)

    def test_every_real_citation_is_found_and_the_noise_is_not(self):
        self.assertEqual(len(self.cites), 8)

    def test_entry_kinds_route_to_the_right_authority(self):
        kinds = {r.key: r.kind for r in self.refs}
        self.assertEqual(kinds["debenedetti|2024"], "arxiv")
        self.assertEqual(kinds["greshake|2023"], "doi")
        self.assertEqual(kinds["bradner|1997"], "rfc")
        self.assertEqual(kinds["ietf|2025a"], "ietf-draft")
        self.assertEqual(kinds["anthropic|2024"], "web")

    def test_uncited_entry_is_identified(self):
        uncited = [r.key for r in self.refs if not r.cited_by]
        self.assertEqual(uncited, ["uncited|2021"])

    def test_orphan_citation_is_identified(self):
        orphans = [c.name for c in self.cites if not c.key]
        self.assertEqual(orphans, ["Nonexistent"])


class TestChicagoFixtureEndToEnd(unittest.TestCase):
    """The Chicago author-date fixture: bare-year entries, author-date text."""

    @classmethod
    def setUpClass(cls):
        cls.refs, cls.cites, cls.style = cc.collect(
            os.path.join(FIXTURES, "sample-chicago-ad.md"))

    def test_chicago_author_date_is_the_author_date_family(self):
        # The entry grammar differs but the in-text form is author-date.
        self.assertEqual(self.style, "author-date")

    def test_every_entry_is_parsed_with_the_bare_year_grammar(self):
        self.assertEqual(len(self.refs), 7)
        self.assertTrue(all(r.style == "chicago-ad" for r in self.refs))

    def test_every_real_citation_is_found(self):
        self.assertEqual(len(self.cites), 8)

    def test_entry_kinds_route_to_the_right_authority(self):
        kinds = {r.key: r.kind for r in self.refs}
        self.assertEqual(kinds["bradner|1997"], "rfc")
        self.assertEqual(kinds["debenedetti|2024"], "arxiv")
        self.assertEqual(kinds["greshake|2023"], "doi")
        self.assertEqual(kinds["anthropic|2024"], "web")
        self.assertEqual(kinds["smith|2020a"], "paper")

    def test_uncited_entry_is_identified(self):
        uncited = [r.key for r in self.refs if not r.cited_by]
        self.assertEqual(uncited, ["uncited|2021"])

    def test_orphan_citation_is_identified(self):
        orphans = [c.name for c in self.cites if not c.key]
        self.assertEqual(orphans, ["Nonexistent"])

    def test_bare_citation_of_an_ab_split_is_flagged(self):
        problems = cc.ambiguous_suffixes(self.refs, self.cites)
        self.assertTrue(any("without a suffix" in p for p in problems))

    def test_page_locator_survives_the_whole_pipeline(self):
        located = [c for c in self.cites if c.name.startswith("Debenedetti")]
        self.assertEqual(len(located), 1)
        self.assertEqual(located[0].page, "pp. 4-6")


class TestNumericFixtureEndToEnd(unittest.TestCase):
    """The IEEE-shaped fixture: numbered entries, bracket and superscript
    markers, a code block that must be ignored."""

    @classmethod
    def setUpClass(cls):
        cls.refs, cls.cites, cls.style = cc.collect(
            os.path.join(FIXTURES, "sample-numeric.md"))

    def test_style_is_detected_as_numeric(self):
        self.assertEqual(self.style, "numeric")

    def test_every_entry_is_parsed_with_its_number(self):
        self.assertEqual(len(self.refs), 10)
        self.assertEqual([r.number for r in self.refs], list(range(1, 11)))

    def test_every_marker_instance_is_found_including_ranges(self):
        # 11 bracket markers (one a 3-range, one a dashed 3-pair), one
        # repeated marker, one superscript: 17 instances.
        self.assertEqual(len(self.cites), 17)
        self.assertTrue(all(c.form == "numeric" for c in self.cites))

    def test_code_block_indices_are_not_citations(self):
        self.assertNotIn(1, [c.number for c in self.cites
                             if "array index" in c.context])

    def test_entry_kinds_route_to_the_right_authority(self):
        kinds = {r.number: r.kind for r in self.refs}
        self.assertEqual(kinds[1], "rfc")
        self.assertEqual(kinds[2], "doi")
        self.assertEqual(kinds[3], "arxiv")
        self.assertEqual(kinds[5], "paper")
        self.assertEqual(kinds[8], "web")
        self.assertEqual(kinds[9], "ietf-draft")

    def test_uncited_entry_is_identified(self):
        uncited = [r.number for r in self.refs if not r.cited_by]
        self.assertEqual(uncited, [10])

    def test_orphan_marker_is_identified(self):
        orphans = {c.number for c in self.cites if not c.key}
        self.assertEqual(orphans, {12})

    def test_claims_collapse_to_one_row_per_source_and_sentence(self):
        worklist = cc.build_claims(self.refs, self.cites, "sample-numeric.md")
        self.assertEqual(worklist.count("- **Verdict**:"), 13)

    def test_a_trailing_superscript_context_is_its_own_sentence(self):
        sup = [c for c in self.cites if c.number == 8][0]
        self.assertEqual(sup.context, "A superscript citation appears here.")


class TestFindMlaCitations(unittest.TestCase):
    def found(self, body):
        return [(c.name, c.page) for c in cc.find_mla_citations(body)]

    def test_author_page_parenthetical(self):
        self.assertEqual(self.found("The claim (Smith 42) holds."), [("Smith", "42")])

    def test_comma_between_name_and_page(self):
        self.assertEqual(self.found("The claim (Smith, 42) holds."), [("Smith", "42")])

    def test_et_al_is_part_of_the_name(self):
        self.assertEqual(self.found("The claim (Greshake et al. 12) holds."),
                         [("Greshake et al.", "12")])

    def test_two_authors_joined_by_and(self):
        self.assertEqual(self.found("The claim (Jones and Patel 12) holds."),
                         [("Jones and Patel", "12")])

    def test_page_range_and_list(self):
        self.assertIn(("Smith", "42-45"), self.found("The claim (Smith 42-45) holds."))
        self.assertIn(("Smith", "42, 50"), self.found("The claim (Smith 42, 50) holds."))

    def test_semicolon_group_yields_one_citation_each(self):
        self.assertEqual(self.found("As shown (Smith 42; Lee 3)."),
                         [("Smith", "42"), ("Lee", "3")])

    def test_a_year_where_the_page_would_be_is_author_date_not_mla(self):
        self.assertEqual(self.found("As shown (Smith 2020) and (Smith, 2020)."), [])

    def test_cross_references_are_not_citations(self):
        for noise in ("(Table 3)", "(Figure 2)", "(Section 4)", "(Appendix B)"):
            with self.subTest(noise=noise):
                self.assertEqual(self.found("Text " + noise + " more."), [])

    def test_a_page_only_parenthetical_is_not_a_citation(self):
        # MLA narrative form ends '(42)'; matching a bare number would fire
        # on every parenthesised digit in the document.
        self.assertEqual(self.found("Smith argues the point (42) here."), [])

    def test_accessed_dates_are_not_citations(self):
        self.assertEqual(self.found("The page (Accessed 3 June 2026) is live."), [])


class TestMatchMlaCitations(unittest.TestCase):
    def setUp(self):
        self.refs = [
            cc.parse_entry('Greshake, Kai. "A paper about things." Journal, 2023.'),
            cc.parse_entry('Hou, Xiaoxia. "Another paper." Journal, 2025.'),
        ]

    def match(self, body):
        return cc.match_citations(self.refs, cc.find_mla_citations(body))

    def test_a_unique_surname_resolves(self):
        cites = self.match("As shown (Greshake 12).")
        self.assertEqual(cites[0].key, "greshake|2023")
        self.assertTrue(self.refs[0].cited_by)

    def test_an_ambiguous_surname_is_left_unresolved_rather_than_guessed(self):
        refs = [cc.parse_entry('Smith, John. "First." Journal, 2020.'),
                cc.parse_entry('Smith, Karen. "Second." Journal, 2019.')]
        cites = cc.match_citations(refs, cc.find_mla_citations("As shown (Smith 42)."))
        self.assertEqual(cites[0].key, "")

    def test_a_surname_with_no_entry_is_left_unresolved(self):
        cites = self.match("An orphan (Nonexistent 7).")
        self.assertEqual(cites[0].key, "")


class TestMlaFixtureEndToEnd(unittest.TestCase):
    """The MLA fixture: Works Cited, author-page parentheticals, an undated
    web source, and two authors sharing a surname."""

    @classmethod
    def setUpClass(cls):
        cls.refs, cls.cites, cls.style = cc.collect(
            os.path.join(FIXTURES, "sample-mla.md"))

    def test_style_is_detected_as_mla(self):
        self.assertEqual(self.style, "mla")

    def test_every_entry_is_parsed(self):
        self.assertEqual(len(self.refs), 6)
        self.assertTrue(all(r.style == "mla" for r in self.refs))

    def test_every_author_page_citation_is_found(self):
        self.assertEqual(len(self.cites), 7)
        self.assertTrue(all(c.form == "mla" for c in self.cites))

    def test_the_undated_web_entry_has_no_year(self):
        anthropic = [r for r in self.refs if r.name == "Anthropic"][0]
        self.assertEqual(anthropic.year, "")
        self.assertEqual(anthropic.kind, "web")

    def test_entry_kinds_route_to_the_right_authority(self):
        kinds = {r.key: r.kind for r in self.refs}
        self.assertEqual(kinds["greshake|2023"], "doi")
        self.assertEqual(kinds["hou|2025"], "arxiv")
        self.assertEqual(kinds["smith|2020"], "paper")

    def test_resolved_citations(self):
        keys = {c.key for c in self.cites}
        self.assertIn("greshake|2023", keys)
        self.assertIn("hou|2025", keys)
        self.assertIn("anthropic|", keys)

    def test_the_shared_surname_is_left_unresolved(self):
        smiths = [c for c in self.cites if c.name == "Smith"]
        self.assertEqual(len(smiths), 2)
        self.assertTrue(all(c.key == "" for c in smiths))

    def test_uncited_entries_include_both_smiths(self):
        uncited = sorted(r.key for r in self.refs if not r.cited_by)
        self.assertEqual(uncited, ["smith|2019", "smith|2020", "uncited|2021"])

    def test_orphan_citation_is_identified(self):
        orphans = [c.name for c in self.cites if not c.key and c.name != "Smith"]
        self.assertEqual(orphans, ["Nonexistent"])

    def test_claims_rows_render_author_page(self):
        worklist = cc.build_claims(self.refs, self.cites, "sample-mla.md")
        self.assertIn("Greshake et al. 12", worklist)
        self.assertEqual(worklist.count("- **Verdict**:"), 7)


class TestFindNoteCitations(unittest.TestCase):
    def test_footnote_markers_are_found_with_context(self):
        cites = cc.find_note_citations(
            "One sentence. The claim appears here.[^3] Another sentence.")
        self.assertEqual(len(cites), 1)
        self.assertEqual(cites[0].number, 3)
        self.assertEqual(cites[0].form, "note")
        self.assertIn("The claim appears here", cites[0].context)
        self.assertNotIn("One sentence", cites[0].context)


class TestNotesFixtureEndToEnd(unittest.TestCase):
    """The notes fixture, in the shape pandoc produces from a .docx: a full
    citation first, shortened repeats, an Ibid., an organisation, and a
    bibliography that already lists one cited work."""

    @classmethod
    def setUpClass(cls):
        cls.refs, cls.cites, cls.style = cc.collect(
            os.path.join(FIXTURES, "sample-notes.md"))

    def test_style_is_detected_as_notes(self):
        self.assertEqual(self.style, "notes")

    def test_every_marker_is_a_citation(self):
        self.assertEqual(len(self.cites), 6)
        self.assertTrue(all(c.form == "note" for c in self.cites))

    def test_the_bibliography_work_cited_by_note_one_is_not_duplicated(self):
        # Note 1 is the full Greshake citation and the bibliography already
        # lists it: one entry, not two.
        keys = [r.key for r in self.refs]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertEqual(len([r for r in self.refs if "greshake" in r.key]), 1)

    def test_shortened_and_ibid_notes_resolve_to_the_full_citation(self):
        keys = {c.number: c.key for c in self.cites}
        self.assertEqual(keys[1], keys[4])
        self.assertEqual(keys[1], keys[5])

    def test_new_entries_from_notes_route_correctly(self):
        kinds = {r.key: r.kind for r in self.refs}
        self.assertEqual(kinds["edoardo debenedetti jiace zhang and nicholas "
                               "carlini|2024"], "arxiv")
        self.assertEqual(kinds["internet engineering task force|2025"], "ietf-draft")

    def test_uncited_entries_are_identified(self):
        uncited = sorted(r.key for r in self.refs if not r.cited_by)
        self.assertEqual(uncited, ["hou|2025", "uncited|2021"])

    def test_orphan_marker_is_left_unresolved(self):
        orphans = [c.number for c in self.cites if not c.key]
        self.assertEqual(orphans, [9])

    def test_the_repeated_work_is_cited_three_times_through_notes(self):
        greshake = [r for r in self.refs if "greshake" in r.key][0]
        self.assertEqual(greshake.cited_by.count("note"), 3)


if __name__ == "__main__":
    unittest.main()
