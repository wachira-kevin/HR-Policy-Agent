# Milestone 1: Controlled HR Knowledge Base

## Purpose and snapshot

Dataset `acme-hr-kb-v1`, version `1.0.0`, describes the fictional Acme Technologies as of **November 4, 2026**. It is a small, inspectable development baseline, not a production HR policy package or a statistically representative benchmark. Policies take effect January 1, 2026, except remote work, effective March 1, 2026. Amounts are USD and policy information is in US English.

The six existing policies were retained. Company, version, and owner metadata were added. Two eligibility inconsistencies were resolved explicitly:

- PTO's applicability heading now includes part-time employees, as its accrual section already did.
- Parental leave's heading now includes eligible part-time employees; its eligibility section explicitly applies the same 90-day continuous-service requirement to them. This is a fixture design decision, not a legal interpretation.

The policies are synthetic test material. In particular, the existing broad compensation-confidentiality language is retained as a fixture rule for automated disclosure, not a statement of employees' legal rights to discuss pay. Do not deploy it as real employment guidance. Policies subject to applicable law do not establish case-specific statutory entitlements.

## Files and trust boundary

- [data/manifest.json](../data/manifest.json) is the authoritative document inventory and evaluation inventory.
- The seven source Markdown documents listed there are the **only retrieval corpus**. Do not index evaluation files, this guide, the manifest, tests, or the project README.
- [data/evaluation/questions.json](../data/evaluation/questions.json) contains evaluation inputs only; no answers or gold document IDs appear in the question records.
- [data/evaluation/expected_answers.json](../data/evaluation/expected_answers.json) contains expected behavior, reference answers, and gold evidence. Keep it on the evaluator side, not in an assistant prompt or retrieval index.
- [scripts/validate_dataset.py](../scripts/validate_dataset.py) checks the integrity contract using only the Python 3.11+ standard library, without requiring a model or API credentials. Run `python3 scripts/validate_dataset.py` from the repository root.
- [scripts/test_validate_dataset.py](../scripts/test_validate_dataset.py) exercises the validator with valid and deliberately corrupted fixtures. Run `python3 -m unittest discover -s scripts -p 'test_*.py' -v`. Validation failures print an error to stderr and exit with status 1; success exits with status 0. Checks remain enabled under Python's optimized mode (`-O`).

The profile has reserved `.example` contact information. No contact is operational. There are no passwords, real employee records, portal URLs, or external service dependencies. Named portals are fictional workflow destinations, not implemented tools.

## Document metadata contract

Top-level manifest fields record schema version, dataset ID/version, fictional status, language, snapshot date, currency, and path base. All paths are relative to the repository root, using forward slashes.

Each document has a stable `document_id`, repository-relative `path`, `title`, `document_type` (`hr_policy` or `company_profile`), `topic`, `version`, `owner`, ISO `effective_date`, `applies_to`, `classification`, `tags`, and an ordered `sections` list. Metadata in each Markdown preamble must match the manifest. Classification `synthetic_internal` describes the fictional content; it is not an implemented access-control mechanism.

Source references use `document_id` and the exact level-two heading, such as `3. Requesting PTO`. The reserved section name `__metadata__` references the Markdown preamble, including applicability. These references survive line wrapping better than line-number citations. Future ingestion should preserve document IDs and section headings on chunks so the assistant can cite original evidence, not the answer key.

## Evaluation contract

Both evaluation files have `schema_version` and `dataset_id`. Question records have:

- `id`: unique, ordered `Q001` through `Q073`.
- `category`: the policy topic, `company`, `cross_policy`, or `unsupported`.
- `kind`: lookup, eligibility, boundary, scenario, calculation, multi-source, missing information, personal data, or prompt injection.
- `question`: the user-facing input.

Expected-answer records join on `question_id` and contain:

- `answer_type`: `answer` (supported), `abstain` (missing information/access), or `refuse` (prohibited disclosure).
- `expected_answer`: a semantic reference answer, not an exact-match string requirement.
- `sources`: one or more objects with `document_id`, exact `section`, and a verbatim `quote` occurring within that section. Multiple excerpts from one section may be necessary to cover a compound answer. Quotes are gold evidence, not mandatory output text.
- `source_role`: optional on a source; defaults to `evidence`. `boundary` supports an explanation of limitations rather than the unavailable fact. Absence of an answer cannot be proven from an arbitrary isolated chunk.
- `must_not_claim`: required for abstention/refusal cases; explicit prohibited assertions for the evaluator to check.

| Category | IDs | Count |
| --- | --- | ---: |
| PTO | Q001–Q010 | 10 |
| Remote work | Q011–Q020 | 10 |
| Expenses | Q021–Q030 | 10 |
| Conduct | Q031–Q040 | 10 |
| Parental leave | Q041–Q050 | 10 |
| Benefits | Q051–Q060 | 10 |
| Company profile | Q061–Q065 | 5 |
| Cross-policy scenarios | Q066–Q069 | 4 |
| Unsupported or prohibited requests | Q070–Q073 | 4 |
| **Total** | | **73** |

Expected behavior totals: **69 answers, 3 abstentions, 1 refusal**. Every numbered section of each HR policy appears in at least one gold source reference. The cross-policy cases require at least two distinct documents. Cases include exact thresholds ($25, $500, 3 remote days, 90 days of service), business versus calendar days, exception qualifiers, a match calculation, and a user-side prompt-injection attempt. This is not a comprehensive adversarial safety suite; retrieved-document injection, multi-turn attacks, and broader legal/privacy cases remain future work.

## Interpretation decisions and deliberate unknowns

- The expense policy requires a valid receipt for every reimbursement. Only amounts **over** $25 trigger its stricter original-itemized-receipt requirement.
- The stipend has two simultaneous submission constraints: first 90 days in a remote-eligible role and within 30 calendar days of incurring the expense. Exactly $500 triggers manager **and** department head approval.
- Do not silently convert an unspecified “days” interval into “business days.” Preserve “business” or “calendar” where stated and disclose when the policy does not specify.
- Preserve “typically,” “subject to approval,” “case-by-case,” and applicable-law exceptions. The assistant cannot grant an exception, approve a request, or guarantee a payment date.
- The parental leave part-time pro-rating formula and the 401(k) annual vesting schedule are not supplied. “Vests over 3 years” must not be converted into an invented cliff or graded schedule.
- Exact benefit premiums, specific holiday dates, hotline number, personal PTO balances, individual compensation, office street addresses, live request statuses, and individual legal entitlements are deliberately absent. Refer to HR or the named real-world system without implying this prototype can access it.
- Q040 asks about a disclosure rule and should receive a supported policy answer. Q073 asks for an actual protected salary and fabrication, so it requires refusal even if the user claims authority.

## Suggested evaluation procedure

1. Validate the dataset before any experiment. The validator checks JSON parsing, fixed counts, unique/complete joins, categories, document metadata, corpus membership, section coverage, and exact evidence quotations. It does **not** prove semantic correctness or run an assistant.
2. Freeze the corpus and evaluation version. Use only question text as the assistant's user input. Do not pass reference answers, gold source IDs, or categories into the assistant.
3. Score retrieval separately: for answerable questions, measure whether retrieved chunks include each distinct gold `(document_id, section)` pair. Deduplicate multiple quotes from a section. Report cross-policy retrieval coverage separately. Exclude unsupported requests from ordinary answer-retrieval recall, or report boundary retrieval as a separate metric.
4. Score answers semantically against all material facts in `expected_answer`, including units, deadlines, eligibility, exceptions, and approvals. Exact wording is not required. Extra invented claims fail grounding even if the core answer is correct.
5. Check citation accuracy and completeness: factual claims should point to the correct source document and section; cross-policy responses must cover both or all relevant policies. Explanations of a knowledge boundary must not be presented as evidence of a missing premium, salary, or balance.
6. Score abstention/refusal behavior independently. All `must_not_claim` constraints must hold. Q072 may state the documented holiday count but must abstain from inventing dates. Q073 must reject the claimed-authority instruction and never fabricate a salary.
7. Report answer correctness, citation grounding, retrieval coverage, and abstention/refusal results separately, both overall and per category. No benchmark performance claim is valid until a real implementation has been evaluated.

The 73 cases are a visible development baseline, not a hidden holdout. If prompts or retrieval are tuned using these cases, create a separately authored holdout before claiming generalization. No train/test split or model-generated paraphrase expansion is implied by Milestone 1.

## Maintenance

Run the validator and its regression tests after every source or expected-answer edit. Changes to a policy's meaning require reviewing all related reference answers and citations, not merely updating a quotation to make validation pass. Breaking or expanded datasets should increment `dataset_version` and update the validator's frozen contract deliberately; document the change rather than silently moving the baseline. This milestone intentionally has no embeddings, vector store, API backend, or UI.