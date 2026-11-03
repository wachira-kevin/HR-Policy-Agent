# Acme Technologies HR Policy RAG

A controlled, fictional HR knowledge base for developing and evaluating a retrieval-augmented assistant. **Milestone 1 is the dataset only; no RAG implementation or live HR-system integration is included.**

## Knowledge base

- Six HR policies: PTO, remote work, expenses, conduct, parental leave, and benefits enrollment.
- One fictional Acme Technologies company profile.
- Exactly 73 evaluation questions and 73 source-backed expected answers.
- A versioned document metadata manifest.
- A dependency-free Python dataset validator and regression tests (Python 3.11+).

| Resource | Location |
| --- | --- |
| Source documents | [Company profile](data/documents/company_profile.md) and the six policies listed in the [manifest](data/manifest.json) |
| Metadata and dataset snapshot | [data/manifest.json](data/manifest.json) |
| Evaluation inputs | [data/evaluation/questions.json](data/evaluation/questions.json) |
| Expected answers and evidence | [data/evaluation/expected_answers.json](data/evaluation/expected_answers.json) |
| Dataset contract and scoring guidance | [docs/knowledge_base.md](docs/knowledge_base.md) |
| Integrity validator | [scripts/validate_dataset.py](scripts/validate_dataset.py) |
| Validator regression tests | [scripts/test_validate_dataset.py](scripts/test_validate_dataset.py) |

## Validation

Use Python 3.11 or newer. From the repository root, run `python3 scripts/validate_dataset.py` to check the corpus and references, and `python3 -m unittest discover -s scripts -p 'test_*.py' -v` to run the validator's regression tests. Both use only the Python standard library; no package installation, Node.js, API keys, embedding model, or database is needed. The validator locates the dataset relative to its own location, so it does not depend on the terminal's working directory.

Only the seven Markdown documents listed in the manifest are retrieval inputs. **Never index evaluation questions, expected answers, the manifest, or project documentation as HR knowledge.** Doing so would leak the evaluation targets into retrieval.

All company facts, policies, and contacts are synthetic. They are not real employment terms or legal advice. See the [dataset contract](docs/knowledge_base.md) before extending the corpus or implementing retrieval.
