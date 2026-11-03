"""Validate the frozen HR dataset without third-party dependencies (Python 3.11+)."""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
CATEGORY_COUNTS = {
    "pto": 10,
    "remote_work": 10,
    "expenses": 10,
    "conduct": 10,
    "parental_leave": 10,
    "benefits": 10,
    "company": 5,
    "cross_policy": 4,
    "unsupported": 4,
}
ANSWER_TYPE_COUNTS = {"answer": 69, "abstain": 3, "refuse": 1}
KINDS = {
    "lookup", "eligibility", "boundary", "scenario", "calculation",
    "multi_source", "missing_information", "personal_data", "prompt_injection",
}
ENGLISH_MONTHS = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)


class ValidationError(ValueError):
    """The dataset violates its structure or reference-integrity contract."""


def _check(condition: bool, message: str) -> None:
    # Do not use assert: integrity checks must also run under python -O.
    if not condition:
        raise ValidationError(message)


def _equal(actual: Any, expected: Any, message: str) -> None:
    _check(type(actual) is type(expected) and actual == expected, message)


def _text(value: Any, label: str) -> None:
    _check(isinstance(value, str), f"{label} must be a string")
    _check(bool(value.strip()), f"{label} must not be empty")


def _unique(values: Iterable[Any], label: str) -> None:
    items = list(values)
    _check(len(set(items)) == len(items), f"{label} must be unique")


def _iso_date(value: Any, label: str) -> date:
    _text(value, label)
    _check(re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value) is not None,
           f"{label} must use YYYY-MM-DD")
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise ValidationError(f"{label} is invalid") from error


def _safe_path(relative: Any) -> str:
    _text(relative, "Repository-relative path")
    _check(not PurePosixPath(relative).is_absolute()
           and "\\" not in relative
           and re.match(r"^[A-Za-z]:", relative) is None,
           "Use repository-relative POSIX paths")
    _check(all(part not in {"", ".", ".."} for part in relative.split("/")),
           "Unsafe path component")
    return relative


def _sections_of(markdown: str) -> tuple[list[str], dict[str, str]]:
    matches = list(re.finditer(r"^## ([^\r\n]+)\r?$", markdown, re.MULTILINE))
    names = [match[1] for match in matches]
    _unique(names, "Document section headings")
    sections = {"__metadata__": markdown[:matches[0].start()] if matches else markdown}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(markdown)
        sections[match[1]] = markdown[match.end():end]
    return names, sections


def load_dataset(root: Path = ROOT) -> dict[str, Any]:
    """Read the manifest, evaluation files, and actual Markdown corpus."""
    root = Path(root)

    def read_json(relative: str) -> Any:
        return json.loads((root / _safe_path(relative)).read_text(encoding="utf-8"))

    manifest = read_json("data/manifest.json")
    questions = read_json(manifest["evaluation"]["questions_path"])
    answers = read_json(manifest["evaluation"]["expected_answers_path"])
    corpus = root / "data/documents"
    if not corpus.is_dir():
        raise ValidationError("Missing data/documents corpus directory")
    documents = {
        filename.relative_to(root).as_posix(): filename.read_text(encoding="utf-8")
        for filename in sorted(corpus.rglob("*.md"))
        if filename.is_file()
    }
    return {
        "manifest": manifest,
        "questions": questions,
        "answers": answers,
        "documents": documents,
    }


def validate_data(data: dict[str, Any]) -> dict[str, Any]:
    """Check structure and source integrity, not the semantics of reference answers."""
    try:
        return _validate_data(data)
    except (KeyError, TypeError, AttributeError) as error:
        raise ValidationError(f"Invalid dataset structure: {error}") from error


def _validate_data(data: dict[str, Any]) -> dict[str, Any]:
    manifest = data["manifest"]
    questions_file = data["questions"]
    answers_file = data["answers"]
    documents = data["documents"]
    for label, document in (
        ("manifest", manifest), ("questions", questions_file), ("answers", answers_file)
    ):
        _equal(document["schema_version"], "1.0", f"{label}: unsupported schema version")
        _equal(document["dataset_id"], "acme-hr-kb-v1", f"{label}: dataset ID mismatch")
    for field, expected in {
        "dataset_version": "1.0.0", "company": "Acme Technologies", "fictional": True,
        "language": "en-US", "currency": "USD", "path_base": "repository_root",
    }.items():
        _equal(manifest[field], expected, f"Unexpected manifest {field}")
    snapshot = _iso_date(manifest["as_of"], "Dataset as_of")
    docs = manifest["documents"]
    _check(isinstance(docs, list), "Manifest documents must be an array")
    _equal(len(docs), 7, "Expected exactly 7 source documents")
    _unique((doc["document_id"] for doc in docs), "Document IDs")
    _unique((doc["path"] for doc in docs), "Document paths")
    _equal(dict(Counter(doc["document_type"] for doc in docs)),
           {"hr_policy": 6, "company_profile": 1}, "Expected six policies and one profile")
    _equal(set(documents), {doc["path"] for doc in docs},
           "Manifest must list exactly the Markdown corpus")

    references = {}
    for doc in docs:
        for field in ("document_id", "title", "topic", "version", "owner", "applies_to"):
            _text(doc[field], f"{doc['path']}: {field}")
        _check(doc["topic"] in CATEGORY_COUNTS
               and doc["topic"] not in {"cross_policy", "unsupported"},
               "Unknown document topic")
        _equal(doc["classification"], "synthetic_internal", "Invalid classification")
        _check(isinstance(doc["tags"], list) and bool(doc["tags"]),
               "Document tags are required")
        for tag in doc["tags"]:
            _text(tag, "Tag")
        _unique(doc["tags"], "Document tags")
        filename = _safe_path(doc["path"])
        _check(filename.startswith("data/documents/") and filename.endswith(".md"),
               "Documents must be Markdown in the corpus directory")
        effective = _iso_date(doc["effective_date"], f"{doc['document_id']}: effective date")
        _check(effective <= snapshot, "Document is not yet effective at dataset as_of")
        markdown = documents[filename]
        _text(markdown, filename)
        _equal(markdown.splitlines()[0], f"# {doc['title']}", f"{filename}: title mismatch")
        names, sections = _sections_of(markdown)
        _check(isinstance(doc["sections"], list), "Manifest sections must be an array")
        _equal(names, doc["sections"], f"{filename}: section list mismatch")
        _equal(len(names), 6 if doc["document_type"] == "hr_policy" else 5,
               f"{filename}: unexpected section count")
        # English fixture dates must not depend on the machine's locale.
        effective_label = f"{ENGLISH_MONTHS[effective.month - 1]} {effective.day}, {effective.year}"
        fields = {
            "Company": f"{manifest['company']} (fictional)",
            "Document ID": doc["document_id"], "Version": doc["version"],
            "Owner": doc["owner"], "Applies To": doc["applies_to"],
            "Effective Date": effective_label,
        }
        for field, value in fields.items():
            _check(f"**{field}:** {value}" in sections["__metadata__"].splitlines(),
                   f"{filename}: {field} metadata mismatch")
        references[doc["document_id"]] = (doc, sections)
    _unique((doc["topic"] for doc in docs), "Document topics")

    evaluation = manifest["evaluation"]
    _equal(_safe_path(evaluation["questions_path"]), "data/evaluation/questions.json",
           "Unexpected questions path")
    _equal(_safe_path(evaluation["expected_answers_path"]),
           "data/evaluation/expected_answers.json", "Unexpected expected answers path")
    _equal(evaluation["question_count"], 73, "Expected manifest question count of 73")
    _equal(evaluation["category_counts"], CATEGORY_COUNTS, "Manifest category targets changed")
    _equal(evaluation["answer_type_counts"], ANSWER_TYPE_COUNTS,
           "Manifest answer-type targets changed")
    questions = questions_file["questions"]
    answers = answers_file["answers"]
    _check(isinstance(questions, list), "Questions must be an array")
    _check(isinstance(answers, list), "Answers must be an array")
    _equal(len(questions), 73, "Expected exactly 73 questions")
    _equal(len(answers), 73, "Expected exactly 73 answers")
    _unique((question["id"] for question in questions), "Question IDs")
    for question in questions:
        _text(question["question"], f"{question['id']}: question")
    _unique((question["question"].strip().lower() for question in questions), "Question text")
    _unique((answer["question_id"] for answer in answers), "Answer question IDs")
    _equal(dict(Counter(question["category"] for question in questions)), CATEGORY_COUNTS,
           "Question coverage mismatch")
    _equal(dict(Counter(answer["answer_type"] for answer in answers)), ANSWER_TYPE_COUNTS,
           "Answer-type coverage mismatch")
    answer_by_id = {answer["question_id"]: answer for answer in answers}
    policy_sections_used = set()
    for index, question in enumerate(questions, start=1):
        qid = question["id"]
        _equal(qid, f"Q{index:03d}", "Questions must be ordered Q001 through Q073")
        _check(question["kind"] in KINDS, f"{qid}: unknown question kind")
        answer = answer_by_id.get(qid)
        _check(answer is not None, f"{qid}: missing answer")
        expected_type = (
            "refuse" if question["kind"] == "prompt_injection"
            else "abstain" if question["category"] == "unsupported" else "answer"
        )
        _equal(answer["answer_type"], expected_type, f"{qid}: incompatible answer type")
        _text(answer["expected_answer"], f"{qid}: expected answer")
        sources = answer["sources"]
        _check(isinstance(sources, list) and bool(sources), f"{qid}: sources required")
        source_documents = set()
        for source in sources:
            document_id = source["document_id"]
            _check(document_id in references, f"{qid}: unknown source document {document_id}")
            _, sections = references[document_id]
            section_name = source["section"]
            _text(section_name, f"{qid}: source section")
            _check(section_name in sections, f"{qid}: source section not found: {section_name}")
            _text(source["quote"], f"{qid}: source quote")
            _check(source["quote"] in sections[section_name],
                   f"{qid}: source quote not found in {document_id} / {section_name}")
            _check(source.get("source_role", "evidence") in {"evidence", "boundary"},
                   "Invalid source role")
            source_documents.add(document_id)
            policy_sections_used.add((document_id, section_name))
        if question["category"] == "cross_policy":
            _equal(question["kind"], "multi_source", f"{qid}: invalid cross-policy kind")
            _check(len(source_documents) >= 2,
                   f"{qid}: cross-policy answer needs at least two documents")
        elif question["category"] != "unsupported":
            _check(any(references[doc_id][0]["topic"] == question["category"]
                       for doc_id in source_documents),
                   f"{qid}: category has no matching source")
        if answer["answer_type"] != "answer":
            negative = answer.get("must_not_claim")
            _check(isinstance(negative, list) and bool(negative),
                   f"{qid}: negative assertions required")
            for value in negative:
                _text(value, f"{qid}: negative assertion")
            _check(any(source.get("source_role") == "boundary" for source in sources),
                   f"{qid}: missing knowledge-boundary evidence")
    for doc in docs:
        if doc["document_type"] == "hr_policy":
            for section in doc["sections"]:
                _check((doc["document_id"], section) in policy_sections_used,
                       f"Policy section has no evaluation coverage: {doc['document_id']}/{section}")
    return {
        "documents": 7, "policies": 6, "questions": 73, "answers": 73,
        "categories": dict(CATEGORY_COUNTS), "answer_types": dict(ANSWER_TYPE_COUNTS),
    }


def main() -> int:
    """Print a summary, or a concise error and a nonzero exit status."""
    try:
        summary = validate_data(load_dataset())
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        print(f"Dataset validation failed: {error}", file=sys.stderr)
        return 1
    print(
        f"Dataset valid: {summary['policies']} policies, "
        f"{summary['documents'] - summary['policies']} company profile, "
        f"{summary['questions']} questions, {summary['answers']} source-backed answers."
    )
    print(f"Answer types: {json.dumps(summary['answer_types'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())