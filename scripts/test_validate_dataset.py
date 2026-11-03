"""Regression tests for the dataset contract; run with unittest discovery."""

from __future__ import annotations

import copy
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from validate_dataset import ROOT, ValidationError, load_dataset, main, validate_data


class DatasetValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.baseline = load_dataset()

    def setUp(self) -> None:
        self.data = copy.deepcopy(self.baseline)

    def answer(self, qid: str) -> dict:
        return next(answer for answer in self.data["answers"]["answers"]
                    if answer["question_id"] == qid)

    def rejects(self, message: str) -> None:
        with self.assertRaisesRegex(ValidationError, message):
            validate_data(self.data)

    def test_baseline(self) -> None:
        summary = validate_data(self.data)
        self.assertEqual(summary["documents"], 7)
        self.assertEqual(summary["questions"], 73)
        self.assertEqual(summary["answers"], 73)

    def test_missing_questions(self) -> None:
        self.data["questions"]["questions"].pop()
        self.rejects("exactly 73 questions")

    def test_duplicate_question_ids(self) -> None:
        self.data["questions"]["questions"][1]["id"] = "Q001"
        self.rejects("Question IDs must be unique")

    def test_duplicate_question_text(self) -> None:
        questions = self.data["questions"]["questions"]
        questions[1]["question"] = questions[0]["question"]
        self.rejects("Question text must be unique")

    def test_orphaned_answer(self) -> None:
        self.answer("Q001")["question_id"] = "Q999"
        self.rejects("Q001: missing answer")

    def test_invented_source(self) -> None:
        self.answer("Q001")["sources"][0]["document_id"] = "UNKNOWN"
        self.rejects("unknown source document")

    def test_incorrect_section(self) -> None:
        self.answer("Q001")["sources"][0]["section"] = "9. Missing"
        self.rejects("source section not found")

    def test_incorrect_quote(self) -> None:
        self.answer("Q001")["sources"][0]["quote"] = "Employees receive 100 days of PTO."
        self.rejects("source quote not found")

    def test_metadata_mismatch(self) -> None:
        self.data["manifest"]["documents"][0]["owner"] = "Finance"
        self.rejects("Owner metadata mismatch")

    def test_future_effective_date(self) -> None:
        self.data["manifest"]["documents"][0]["effective_date"] = "2027-01-01"
        self.rejects("not yet effective")

    def test_invalid_calendar_date(self) -> None:
        self.data["manifest"]["as_of"] = "2026-02-30"
        self.rejects("Dataset as_of is invalid")

    def test_unmanifested_markdown(self) -> None:
        self.data["documents"]["data/documents/extra.md"] = "# Unexpected"
        self.rejects("exactly the Markdown corpus")

    def test_cross_policy_needs_multiple_documents(self) -> None:
        self.answer("Q066")["sources"] = self.answer("Q016")["sources"]
        self.rejects("cross-policy answer needs at least two documents")

    def test_unsupported_requires_negative_assertions(self) -> None:
        del self.answer("Q070")["must_not_claim"]
        self.rejects("negative assertions required")

    def test_unknown_cannot_become_answer(self) -> None:
        self.answer("Q070")["answer_type"] = "answer"
        self.rejects("Answer-type coverage mismatch")

    def test_path_cannot_escape_root(self) -> None:
        self.data["manifest"]["evaluation"]["questions_path"] = "../private.json"
        self.rejects("Unsafe path component")

    def test_invalid_path_variants(self) -> None:
        for filename in ("/private.json", "C:/private.json", "data\\private.json",
                         "data//private.json", "./data/private.json"):
            with self.subTest(filename=filename):
                self.data["manifest"]["evaluation"]["questions_path"] = filename
                self.rejects("POSIX paths|Unsafe path component")

    def test_boundary_evidence_required(self) -> None:
        self.answer("Q070")["sources"][0].pop("source_role")
        self.rejects("missing knowledge-boundary evidence")

    def test_invalid_source_role(self) -> None:
        self.answer("Q001")["sources"][0]["source_role"] = "invented"
        self.rejects("Invalid source role")

    def test_policy_section_coverage(self) -> None:
        self.answer("Q003")["sources"] = self.answer("Q001")["sources"]
        self.rejects("Policy section has no evaluation coverage: HR-PTO-001/2. Carryover")

    def test_duplicate_section_headings(self) -> None:
        filename = "data/documents/pto_policy.md"
        self.data["documents"][filename] += "\n## 1. Accrual\nDuplicate content.\n"
        self.rejects("Document section headings must be unique")

    def test_questions_must_remain_ordered(self) -> None:
        questions = self.data["questions"]["questions"]
        questions[0], questions[1] = questions[1], questions[0]
        self.rejects("Questions must be ordered")

    def test_missing_answer_field_is_validation_error(self) -> None:
        del self.answer("Q001")["expected_answer"]
        self.rejects("Invalid dataset structure")

    def test_crlf_document_sections(self) -> None:
        self.data["documents"] = {
            filename: markdown.replace("\n", "\r\n")
            for filename, markdown in self.data["documents"].items()
        }
        self.assertEqual(validate_data(self.data)["questions"], 73)

    def test_cli_works_outside_repository(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                [sys.executable, "-B", str(ROOT / "scripts/validate_dataset.py")],
                cwd=directory, text=True, capture_output=True, check=False,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("73 source-backed answers", result.stdout)

    def test_cli_failure_has_nonzero_status_and_stderr(self) -> None:
        self.data["questions"]["questions"].pop()
        with patch("validate_dataset.load_dataset", return_value=self.data), \
                patch("sys.stderr") as stderr:
            self.assertEqual(main(), 1)
        self.assertIn("Dataset validation failed", "".join(
            call.args[0] for call in stderr.write.call_args_list
        ))

    def test_invalid_json_rejected_by_loader(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "data").mkdir()
            (root / "data/manifest.json").write_text("{", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_dataset(root)

    def test_missing_corpus_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "data/evaluation").mkdir(parents=True)
            for relative in ("data/manifest.json", "data/evaluation/questions.json",
                             "data/evaluation/expected_answers.json"):
                (root / relative).write_text((ROOT / relative).read_text(encoding="utf-8"),
                                            encoding="utf-8")
            with self.assertRaisesRegex(ValidationError, "Missing data/documents"):
                load_dataset(root)


if __name__ == "__main__":
    unittest.main()