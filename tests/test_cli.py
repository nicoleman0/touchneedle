"""End-to-end runs of the command line, always offline."""

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from context import FIXTURES, SCRIPT, cc

SAMPLE = os.path.join(FIXTURES, "sample.md")


def run(*args):
    return subprocess.run([sys.executable, SCRIPT, *args],
                          capture_output=True, text=True)


class TestCheckCommand(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = os.path.join(cls.tmp.name, "report.md")
        cls.data = os.path.join(cls.tmp.name, "data.json")
        cls.proc = run("check", SAMPLE, "--offline",
                       "--out", cls.out, "--json", cls.data,
                       "--cache", os.path.join(cls.tmp.name, "cache"))
        with open(cls.out, encoding="utf-8") as fh:
            cls.report = fh.read()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_a_clean_offline_run_exits_zero(self):
        self.assertEqual(self.proc.returncode, 0, self.proc.stderr)

    def test_the_report_names_the_document_and_the_totals(self):
        self.assertIn("# Citation check — sample.md", self.report)
        self.assertIn("8 reference entries, 8 in-text citation instances.", self.report)

    def test_offline_runs_say_so_prominently(self):
        # Nobody should mistake an offline run for a verified bibliography.
        self.assertIn("offline mode, nothing was verified against a live source",
                      self.report)

    def test_uncited_entries_are_listed(self):
        section = self.report.split("### Reference-list entries never cited")[1]
        self.assertIn("Uncited (2021)", section.split("###")[0])

    def test_unresolved_citations_are_listed_with_their_caveat(self):
        section = self.report.split("### In-text citations with no matching")[1]
        self.assertIn("Nonexistent (2019)", section)
        self.assertIn("Expect false positives here", section)

    def test_the_report_states_what_it_did_not_check(self):
        self.assertIn("supports the claim it is attached to", self.report)

    def test_progress_goes_to_stderr_so_stdout_stays_pipeable(self):
        self.assertIn("[1/8]", self.proc.stderr)

    def test_json_output_is_machine_readable(self):
        with open(self.data, encoding="utf-8") as fh:
            data = json.load(fh)
        self.assertEqual(len(data["references"]), 8)
        self.assertEqual(len(data["citations"]), 8)
        self.assertEqual(data["style"], "author-date")
        self.assertTrue(all("status" in r for r in data["references"]))

    def test_the_report_names_the_citation_style(self):
        self.assertIn("Style: author-date (detected)", self.report)


class TestStyleOverride(unittest.TestCase):
    def test_a_forced_style_is_reported_as_forced(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "r.md")
            proc = run("check", SAMPLE, "--offline", "--style", "author-date",
                       "--out", out, "--cache", os.path.join(tmp, "cache"))
            with open(out, encoding="utf-8") as fh:
                report = fh.read()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("Style: author-date (forced)", report)

    def test_an_unknown_style_is_rejected_before_any_work(self):
        proc = run("check", SAMPLE, "--style", "footnotes")
        self.assertNotEqual(proc.returncode, 0)


class TestClaimsCommand(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        out = os.path.join(cls.tmp.name, "claims.md")
        cls.proc = run("claims", SAMPLE, "--out", out)
        with open(out, encoding="utf-8") as fh:
            cls.worklist = fh.read()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_exits_zero(self):
        self.assertEqual(self.proc.returncode, 0, self.proc.stderr)

    def test_one_row_per_in_text_citation(self):
        self.assertEqual(self.worklist.count("- **Verdict**:"), 8)

    def test_each_row_carries_the_sentence_making_the_claim(self):
        self.assertIn("Prompt injection was first characterised", self.worklist)

    def test_rows_carry_a_locator_for_the_source(self):
        self.assertIn("arXiv:2406.13352", self.worklist)
        self.assertIn("https://modelcontextprotocol.io/specification", self.worklist)

    def test_a_citation_with_no_entry_says_so_rather_than_inventing_one(self):
        self.assertIn("_no matching reference-list entry_", self.worklist)

    def test_the_worklist_forbids_guessing(self):
        self.assertIn("Do not guess", self.worklist)


class TestExitCodes(unittest.TestCase):
    def test_a_problem_status_exits_two_so_it_can_gate_ci(self):
        def fake_verify(ref, fetcher):
            ref.status = "MISMATCH"
            ref.notes.append("planted by the test")

        with tempfile.TemporaryDirectory() as tmp:
            argv = ["touchneedle.py", "check", SAMPLE,
                    "--out", os.path.join(tmp, "r.md"),
                    "--cache", os.path.join(tmp, "cache")]
            with mock.patch.object(cc, "verify", fake_verify), \
                 mock.patch.object(sys, "argv", argv), \
                 contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(cc.main(), 2)

    def test_an_unreadable_document_fails_loudly(self):
        proc = run("check", os.path.join(FIXTURES, "does-not-exist.md"), "--offline")
        self.assertNotEqual(proc.returncode, 0)

    def test_a_document_with_no_reference_list_explains_why(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "bare.md")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("# Just a document\n\nNo reference list here.\n")
            proc = run("check", path, "--offline")
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("no 'References'", proc.stderr)


class TestMailtoIsOptIn(unittest.TestCase):
    def test_mailto_defaults_to_unset(self):
        # It goes to third parties, so it must never be inferred.
        with tempfile.TemporaryDirectory() as tmp:
            f = cc.Fetcher(tmp, offline=True)
        self.assertIsNone(f.mailto)

    def test_help_documents_that_mailto_is_sent_to_third_parties(self):
        proc = run("check", "--help")
        self.assertIn("Crossref/OpenAlex", proc.stdout)


if __name__ == "__main__":
    unittest.main()
