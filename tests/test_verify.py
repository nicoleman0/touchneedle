"""Metadata comparison, status assignment, and the HTTP cache.

Nothing here touches the network: the Fetcher is always constructed offline,
and records are planted in the cache directly.
"""

import hashlib
import json
import os
import tempfile
import time
import unittest

from context import cc


def ref(raw="Smith, J. (2020) 'A study of prompt injection in language models', "
            "Journal of Things."):
    return cc.parse_entry(raw)


class TestTitleScore(unittest.TestCase):
    def test_identical_titles_score_one(self):
        self.assertEqual(cc.title_score("A paper about things",
                                        "A paper about things"), 1.0)

    def test_a_contained_title_scores_one(self):
        # A record that carries a subtitle the entry omits is still the same work.
        self.assertEqual(cc.title_score(
            "Attention is all you need",
            "Attention is all you need for machine translation tasks"), 1.0)

    def test_unrelated_titles_score_low(self):
        self.assertLess(cc.title_score(
            "A study of prompt injection in language models",
            "Quantum error correction thresholds in superconducting qubits"), 0.60)

    def test_empty_input_scores_zero(self):
        self.assertEqual(cc.title_score("", "A paper"), 0.0)


class TestAuthorPresent(unittest.TestCase):
    def test_surname_found_in_a_full_name_list(self):
        self.assertTrue(cc.author_present("Greshake", ["Kai Greshake", "Sahar Abdelnabi"]))

    def test_surname_absent(self):
        self.assertFalse(cc.author_present("Greshake", ["Ada Lovelace", "Alan Turing"]))

    def test_accents_do_not_defeat_the_match(self):
        self.assertTrue(cc.author_present("Öztürk", ["Mehmet Ozturk"]))

    def test_a_substring_of_another_surname_does_not_match(self):
        self.assertFalse(cc.author_present("Smith", ["Smithson, Jane"]))


class TestCheckMetadata(unittest.TestCase):
    def test_exact_record_verifies(self):
        r = ref()
        cc.check_metadata(r, "A study of prompt injection in language models",
                          ["Jane Smith"], "2020", "Crossref")
        self.assertEqual(r.status, "VERIFIED")

    def test_loose_title_match_is_partial_not_a_failure(self):
        r = cc.parse_entry(
            "Debenedetti, E. (2024) 'AgentDojo: A Dynamic Environment to Evaluate "
            "Attacks', NeurIPS.")
        cc.check_metadata(
            r, "AgentDojo: A Dynamic Environment for Evaluating Prompt Injection "
               "Attacks and Defenses", ["Edoardo Debenedetti"], "2024", "Crossref")
        self.assertEqual(r.status, "PARTIAL")
        self.assertTrue(any("partly matches" in n for n in r.notes))

    def test_a_different_title_is_a_mismatch(self):
        r = ref()
        cc.check_metadata(r, "Quantum error correction thresholds in "
                             "superconducting qubits", ["Jane Smith"], "2020", "Crossref")
        self.assertEqual(r.status, "MISMATCH")

    def test_right_title_wrong_authors_is_the_fabrication_signature(self):
        r = ref()
        cc.check_metadata(r, "A study of prompt injection in language models",
                          ["Ada Lovelace", "Alan Turing"], "2020", "Crossref")
        self.assertEqual(r.status, "MISMATCH")
        self.assertTrue(any("not among" in n for n in r.notes))

    def test_year_off_by_one_is_tolerated(self):
        # Preprint in one year, proceedings in the next -- routine, not an error.
        r = ref()
        cc.check_metadata(r, "A study of prompt injection in language models",
                          ["Jane Smith"], "2021", "Crossref")
        self.assertEqual(r.status, "VERIFIED")

    def test_year_off_by_more_than_one_is_a_mismatch(self):
        r = ref()
        cc.check_metadata(r, "A study of prompt injection in language models",
                          ["Jane Smith"], "2015", "Crossref")
        self.assertEqual(r.status, "MISMATCH")
        self.assertTrue(any("2020 vs 2015" in n for n in r.notes))

    def test_organisation_entries_skip_the_author_check(self):
        r = cc.parse_entry("Anthropic (2024) 'Model Context Protocol specification'.")
        cc.check_metadata(r, "Model Context Protocol specification", ["Some Person"],
                          "2024", "Crossref")
        self.assertEqual(r.status, "VERIFIED")

    def test_the_retrieved_record_is_recorded_as_evidence(self):
        r = ref()
        cc.check_metadata(r, "A study of prompt injection in language models",
                          ["Jane Smith"], "2020", "Crossref 10.1/x")
        self.assertTrue(any("Crossref 10.1/x" in e for e in r.evidence))


class TestSeverityOrdering(unittest.TestCase):
    def test_problem_statuses_sort_above_advisory_ones(self):
        for bad in cc.PROBLEM_STATUSES:
            for ok in ("PARTIAL", "LINK_MOVED", "UNVERIFIABLE", "VERIFIED"):
                with self.subTest(bad=bad, ok=ok):
                    self.assertLess(cc.SEVERITY[bad], cc.SEVERITY[ok])

    def test_partial_and_unverifiable_are_not_failures(self):
        self.assertNotIn("PARTIAL", cc.PROBLEM_STATUSES)
        self.assertNotIn("UNVERIFIABLE", cc.PROBLEM_STATUSES)


class TestOfflineVerify(unittest.TestCase):
    def test_offline_marks_entries_unverifiable_not_failed(self):
        # Absence of a lookup is not a finding against the citation.
        with tempfile.TemporaryDirectory() as tmp:
            f = cc.Fetcher(tmp, offline=True)
            r = cc.parse_entry("Smith, J. (2020) 'A paper', Journal. doi:10.1/x")
            cc.verify(r, f)
        self.assertEqual(r.status, "UNVERIFIABLE")
        self.assertNotIn(r.status, cc.PROBLEM_STATUSES)

    def test_an_entry_with_nothing_checkable_is_unverifiable(self):
        with tempfile.TemporaryDirectory() as tmp:
            # No quoted title and no academic container, so nothing routes to a
            # lookup -- this exercises the final branch without any network call.
            r = cc.parse_entry("Smith, J. (2020) An internal report held on file.")
            cc.verify(r, cc.Fetcher(tmp, offline=False))
        self.assertEqual(r.status, "UNVERIFIABLE")
        self.assertTrue(any("no DOI" in n for n in r.notes))


class TestOutagesAreNotFindings(unittest.TestCase):
    """The worst thing this tool can do is tell someone a correct citation is
    wrong. A lookup that never happened must never become evidence."""

    def plant(self, tmp, url, body="", ok=True, status=200, error=None):
        key = hashlib.sha256((url + "application/json").encode()).hexdigest() + ".json"
        with open(os.path.join(tmp, key), "w", encoding="utf-8") as fh:
            json.dump({"ok": ok, "status": status, "body": body,
                       "final_url": url, "error": error}, fh)

    def crossref_url(self, doi):
        import urllib.parse
        return f"https://api.crossref.org/works/{urllib.parse.quote(doi)}"

    def test_a_rate_limited_crossref_does_not_condemn_the_doi(self):
        r = ref("Smith, J. (2020) 'A paper', Journal of Things. doi:10.1145/1234")
        with tempfile.TemporaryDirectory() as tmp:
            self.plant(tmp, self.crossref_url(r.doi), ok=False, status=429,
                       error="HTTP 429")
            verdict = cc.verify_doi(r, cc.Fetcher(tmp))
        self.assertFalse(verdict)                 # no verdict, next route gets a turn
        self.assertNotEqual(r.status, "NOT_FOUND")
        self.assertTrue(any("could not be reached" in n for n in r.notes), r.notes)

    def test_a_404_from_crossref_still_condemns_the_doi(self):
        # The distinction the fix rests on: the server answered.
        r = ref("Smith, J. (2020) 'A paper', Journal of Things. doi:10.1000/nope")
        with tempfile.TemporaryDirectory() as tmp:
            self.plant(tmp, self.crossref_url(r.doi), ok=False, status=404,
                       error="HTTP 404")
            verdict = cc.verify_doi(r, cc.Fetcher(tmp))
        self.assertTrue(verdict)
        self.assertEqual(r.status, "NOT_FOUND")

    def test_a_silent_search_engine_is_named_and_withholds_the_verdict(self):
        import urllib.parse
        r = ref("Liu, Y. (2024) 'Formalizing and benchmarking prompt injection "
                "attacks and defenses', Proceedings of the USENIX Security Symposium.")
        q = urllib.parse.quote(r.title[:250])
        with tempfile.TemporaryDirectory() as tmp:
            self.plant(tmp, f"https://api.crossref.org/works?query.bibliographic={q}&rows=5",
                       body=json.dumps({"message": {"items": [
                           {"title": ["Something else entirely"],
                            "author": [{"given": "A", "family": "Other"}],
                            "issued": {"date-parts": [[2024]]}, "DOI": "10.1/x"}]}}))
            self.plant(tmp, f"https://api.openalex.org/works?per-page=5&filter=title.search:{q}",
                       ok=False, status=429, error="HTTP 429")
            verdict = cc.verify_by_title(r, cc.Fetcher(tmp))
        self.assertFalse(verdict)
        self.assertNotEqual(r.status, "NOT_FOUND")
        self.assertTrue(any("OpenAlex" in n and "429" in n for n in r.notes), r.notes)

    def test_a_search_both_engines_answered_still_reports_not_found(self):
        import urllib.parse
        r = ref()
        q = urllib.parse.quote(r.title[:250])
        with tempfile.TemporaryDirectory() as tmp:
            self.plant(tmp, f"https://api.crossref.org/works?query.bibliographic={q}&rows=5",
                       body=json.dumps({"message": {"items": []}}))
            self.plant(tmp, f"https://api.openalex.org/works?per-page=5&filter=title.search:{q}",
                       body=json.dumps({"results": []}))
            verdict = cc.verify_by_title(r, cc.Fetcher(tmp))
        self.assertTrue(verdict)
        self.assertEqual(r.status, "NOT_FOUND")
        self.assertTrue(any("Crossref or OpenAlex" in n for n in r.notes), r.notes)

    def test_a_search_route_verdict_is_never_a_condemnation(self):
        # The invariant that replaced the old downgrade: whatever a searched
        # record disagrees about, the entry cannot leave this route condemned.
        import urllib.parse
        r = ref()
        q = urllib.parse.quote(r.title[:250])
        with tempfile.TemporaryDirectory() as tmp:
            self.plant(tmp, f"https://api.crossref.org/works?query.bibliographic={q}&rows=5",
                       ok=False, status=429, error="HTTP 429")
            self.plant(tmp, f"https://api.openalex.org/works?per-page=5&filter=title.search:{q}",
                       body=json.dumps({"results": [
                           {"display_name": r.title,
                            "authorships": [{"author": {"display_name": "Jane Smith"}}],
                            "publication_year": 2015}]}))
            cc.verify_by_title(r, cc.Fetcher(tmp))
        self.assertNotIn(r.status, cc.PROBLEM_STATUSES)
        self.assertTrue(any("reprint or a duplicate record" in n for n in r.notes), r.notes)
        self.assertTrue(any("could not search Crossref" in n for n in r.notes), r.notes)

    def test_a_timeout_does_not_make_a_link_dead(self):
        r = cc.parse_entry("Example Corp (2024) 'A post'. "
                           "Available at: https://example.com/post")
        with tempfile.TemporaryDirectory() as tmp:
            key = hashlib.sha256(b"https://example.com/post").hexdigest() + ".json"
            with open(os.path.join(tmp, key), "w", encoding="utf-8") as fh:
                json.dump({"ok": False, "status": None, "body": "",
                           "final_url": r.url, "error": "TimeoutError: timed out",
                           "transient": True}, fh)
            cc.verify_web(r, cc.Fetcher(tmp))
        self.assertEqual(r.status, "UNVERIFIABLE")

    def test_a_404_still_makes_a_link_dead(self):
        r = cc.parse_entry("Example Corp (2024) 'A post'. "
                           "Available at: https://example.com/gone")
        with tempfile.TemporaryDirectory() as tmp:
            key = hashlib.sha256(b"https://example.com/gone").hexdigest() + ".json"
            with open(os.path.join(tmp, key), "w", encoding="utf-8") as fh:
                json.dump({"ok": False, "status": 404, "body": "",
                           "final_url": r.url, "error": "HTTP 404"}, fh)
            cc.verify_web(r, cc.Fetcher(tmp))
        self.assertEqual(r.status, "LINK_DEAD")


class TestSearchCandidates(unittest.TestCase):
    """A title search returns candidates, not the cited work. Only a candidate
    confident enough to *be* the work earns a metadata comparison."""

    plant = TestOutagesAreNotFindings.plant

    def search(self, tmp, r, title, authors, year=2024):
        import urllib.parse
        q = urllib.parse.quote(r.title[:250])
        self.plant(tmp, f"https://api.crossref.org/works?query.bibliographic={q}&rows=5",
                   body=json.dumps({"message": {"items": [
                       {"title": [title],
                        "author": [{"given": g, "family": f} for g, f in authors],
                        "issued": {"date-parts": [[year]]}, "DOI": "10.1/x"}]}}))
        self.plant(tmp, f"https://api.openalex.org/works?per-page=5&filter=title.search:{q}",
                   body=json.dumps({"results": []}))
        return cc.verify_by_title(r, cc.Fetcher(tmp))

    def test_a_near_neighbour_by_other_authors_is_not_a_mismatch(self):
        # The real case: a USENIX paper neither index covers, and Crossref
        # offers a different paper on the same subject. The search missed; the
        # citation is not thereby wrong.
        r = ref("Liu, Y. (2024) 'Formalizing and benchmarking prompt injection "
                "attacks and defenses', Proceedings of the USENIX Security Symposium.")
        with tempfile.TemporaryDirectory() as tmp:
            self.search(tmp, r, "Benchmarking prompt injection attacks and defenses "
                                "in language models", [("Eleena", "Mathew")])
        self.assertEqual(r.status, "NOT_FOUND")
        self.assertTrue(any("no confident match" in n for n in r.notes), r.notes)
        self.assertTrue(any("check this one by eye" in n for n in r.notes), r.notes)

    def test_a_matching_title_over_the_wrong_authors_is_not_found_not_mismatch(self):
        # On a search this is ambiguous: either the citation is fabricated, or
        # the search landed on a neighbour sharing the title -- which is what
        # happened to "Attention is all you need", a phrase that sits inside
        # book chapters that are not it. The report names the neighbour and
        # leaves the judgement to a person, rather than asserting a conflict.
        r = ref()
        with tempfile.TemporaryDirectory() as tmp:
            self.search(tmp, r, r.title, [("Eleena", "Mathew")], year=2020)
        self.assertEqual(r.status, "NOT_FOUND")
        self.assertTrue(any("closest" in n for n in r.notes), r.notes)

    def test_the_fabrication_signature_still_fires_on_an_identifier_lookup(self):
        # Where the record is the work by construction -- a DOI, an arXiv id --
        # a real title over the wrong authors remains exactly the signature this
        # tool exists to catch.
        r = ref()
        cc.check_metadata(r, r.title, ["Eleena Mathew"], "2020", "Crossref 10.1/x")
        self.assertEqual(r.status, "MISMATCH")
        self.assertTrue(any("not among" in n for n in r.notes), r.notes)

    def test_a_middling_title_with_the_cited_author_is_accepted(self):
        # Same author, title differing by a subtitle: the same work, described
        # loosely. Worth a glance, not an accusation.
        r = ref()
        with tempfile.TemporaryDirectory() as tmp:
            self.search(tmp, r, "Prompt injection in language models: a survey "
                                "of defences", [("Jane", "Smith")], year=2020)
        self.assertEqual(r.status, "PARTIAL")

    def test_an_organisation_entry_needs_the_stronger_title_match(self):
        # No author surname to corroborate with, so the title has to carry it.
        r = cc.parse_entry("Internet Engineering Task Force (2024) 'A study of "
                           "prompt injection in language models', Proceedings of IETF.")
        self.assertTrue(r.is_org)
        with tempfile.TemporaryDirectory() as tmp:
            self.search(tmp, r, "Prompt injection in language models: a survey "
                                "of defences", [("Jane", "Smith")])
        self.assertEqual(r.status, "NOT_FOUND")


class TestFetcherCache(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = self.tmp.name

    def plant(self, url, accept=None, body="cached body", age=0):
        key = hashlib.sha256((url + (accept or "")).encode()).hexdigest() + ".json"
        path = os.path.join(self.dir, key)
        os.makedirs(self.dir, exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"ok": True, "status": 200, "body": body,
                       "final_url": url, "error": None}, fh)
        if age:
            os.utime(path, (time.time() - age, time.time() - age))
        return path

    def test_offline_returns_a_clean_miss_rather_than_reaching_out(self):
        rec = cc.Fetcher(self.dir, offline=True).get("https://example.com/never")
        self.assertFalse(rec["ok"])
        self.assertEqual(rec["error"], "offline")

    def test_a_cached_record_is_served_even_offline(self):
        self.plant("https://example.com/x")
        rec = cc.Fetcher(self.dir, offline=True).get("https://example.com/x")
        self.assertTrue(rec["ok"])
        self.assertEqual(rec["body"], "cached body")

    def test_the_cache_key_includes_the_accept_header(self):
        self.plant("https://example.com/x", accept="application/json", body="json body")
        f = cc.Fetcher(self.dir, offline=True)
        self.assertEqual(f.get("https://example.com/x",
                               accept="application/json")["body"], "json body")
        self.assertFalse(f.get("https://example.com/x")["ok"])

    def test_a_record_past_the_ttl_is_not_served(self):
        self.plant("https://example.com/x", age=cc.CACHE_TTL + 60)
        rec = cc.Fetcher(self.dir, offline=True).get("https://example.com/x")
        self.assertFalse(rec["ok"])
        self.assertEqual(rec["error"], "offline")

    def test_the_user_agent_carries_the_version_and_a_contact_url(self):
        self.assertIn(cc.__version__, cc.UA)
        self.assertIn("http", cc.UA)


if __name__ == "__main__":
    unittest.main()
