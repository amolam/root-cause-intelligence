# Client engagement implementation check

This is an implementation check against the client brief, not an instruction source. The brief's facts are kept separate from implementation assumptions.

| Brief requirement | Current implementation | Status |
|---|---|---|
| Visible frontend a Dhaga user can operate | Responsive dashboard with summary, category/SKU tables, classify form, review queue, and visible errors in `frontend/public/` | Implemented; not yet browser-QA'd against a deployed URL |
| FastAPI backend and PostgreSQL persistence | FastAPI endpoints and SQLAlchemy/Alembic schema; Aiven is configured by `DATABASE_URL` | Implemented; live Aiven aggregation was verified for the synthetic sample |
| Model selection for cost/latency/quality | Jev-only direct classification is the default; optional GPT-4.1 Mini to second-stage routing remains available | Implemented; actual account/model access still depends on OpenRouter |
| Two deliberate patterns | Jev-only direct classification by default; confidence/category routing and sequential prompt chaining remain available in two-stage mode | Implemented |
| Code-versus-model line | Deterministic validation, arithmetic, period grouping, and review routing; language classification is the model boundary | Documented in `BUILD_NOTE.md` |
| Stated temperatures | Classification uses temperature 0.0. No separate extraction, evaluator, or customer-facing generation call is made | Documented |
| Validated structured output | LangChain JSON-schema mode plus Pydantic taxonomy/category-subcategory checks; OpenRouter routing requires supported parameters | Implemented |
| Visible failure path | API reports errors; UI displays them. Missing return ID can be used as an intentional failure demo | Implemented |
| Human review for unresolved cases | Final `OTHER` records go to a review queue; valid specific labels are auto-resolved after second-stage reassessment, and human labels are validated/persisted | Implemented |
| Real-shaped input | 14 schema-provided text cases include Hinglish and varied causes | Partial: this is not the proposed 15,000-return volume, and actual 90-colour spellings are unavailable |
| Cold start in five minutes | README has setup, seed, API, frontend, classifier, and insight commands | Prepared; a fresh-account timed run was not completed |
| GitHub CI/CD | `.github/workflows/ci.yml` installs and runs the tests on push/PR | Implemented in repository files; there is no GitHub remote yet |
| Deployed URL | Vercel configurations and two-project instructions are prepared | Not completed: Vercel CLI/account and repository remote are not connected |

## Remaining before a client demo

1. Connect a GitHub remote and run the workflow on GitHub.
2. Connect the repository to Vercel, deploy API and frontend separately, add Aiven/OpenRouter secrets only to the backend, and verify CORS and model access.
3. Keep the public demo on synthetic data. The API currently has no authentication; add access control before loading real customer comments or exposing real return records.
4. Ask Dhaga for a larger source-shaped sample and a human-labelled benchmark; validate actual accuracy, escalation rate, and cost before making business claims.
5. Record the ranked discovery choice before the first commit in the next project iteration. The current discovery note was written after the initial database work and is transparent about that sequence.
