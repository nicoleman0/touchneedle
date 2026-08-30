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
            body, block = cc.split_document(fh.read())
        refs = [cc.parse_entry(e) for e in cc.split_entries(block)]
        cites = cc.match_citations(refs, cc.find_citations(body))
        self.assertEqual(cc.ambiguous_suffixes(refs, cites), [])


class TestFixtureEndToEnd(unittest.TestCase):
    """The fixture is the contract: what the parser is expected to find."""

    @classmethod
    def setUpClass(cls):
        cls.refs, cls.cites = cc.collect(os.path.join(FIXTURES, "sample.md"))

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


if __name__ == "__main__":
    unittest.main()
