# Build note

## What the MVP does

The browser dashboard connects to a build-configured FastAPI origin, displays “Other” share and pending reviews, classifies returns, and presents category-to-SKU insights. The review queue distinguishes unclassified returns from classified results awaiting human review. The repository contains a Vercel-ready static frontend and FastAPI entry point. No Dhaga production systems are connected. `sample_data/return_text_test_cases.csv` carries the 14 project-schema text cases, including Hinglish; these are test examples, not production records. The brief's proposed 15,000-return MVP volume is not supplied as a dataset.

## Code and model decisions

| Step | Implementation | Why |
|---|---|---|
| CSV checks and cleaning | Python | Headers, required fields, types, whitespace and referential constraints are deterministic. Unknown fields and bad values fail visibly. |
| Return classification | LangChain structured output via OpenRouter | Free-text/Hinglish mapping into the proposed taxonomy needs language judgment; JSON schema output is validated again with Pydantic. Temperature is 0.0 for repeatable classification. |
| Routing and prompt chain | `openai/gpt-4.1-mini` first; selected second-stage model on low confidence or `OTHER` | Reduces routine latency/cost. `SECOND_STAGE_BACKEND` defaults to `openrouter` (`OPENROUTER_HEAVY_MODEL`) and can select Jev (`JEV_OPENROUTER_MODEL`) through OpenRouter's typed decisions endpoint, using the same API key. |
| Review decision | Python threshold + category rule | A final result below 0.75 confidence or in `OTHER` is queued for a human. A high-confidence `OTHER` remains pending because confidence in that label does not mean it is a supported root cause. The threshold is not calibrated. |
| Bulk classification | Dashboard selects 10, 50, or 100 returns and submits sequential requests capped at five each | No model calls on dashboard load; progress is shown, failures stop further chunks, and each result is saved separately. |
| Rates and aggregates | SQLAlchemy/Python | Counts and ratios are arithmetic and grouping, not model work. API classification refreshes the affected monthly cohort; CLI classification still needs an explicit aggregation run. The dashboard sums stored periods over the selected inclusive date range. |
| Classification reset | Demo FastAPI endpoint | The review queue reset deletes AI analyses and human reviews, then recalculates insights. Returns and orders are retained. This endpoint is intentionally unauthenticated for the demo. |
| Dashboard and review UI | HTML/CSS/JavaScript | Category/subcategory rows expand to related SKU counts, rates, issue mix, and small-sample flags. The explicit Recalculate insights action recomputes aggregates; page load, Review Queue Refresh, and date-range changes only reload displayed data. `API_BASE_URL` is embedded at static build time. |

These are two deliberate patterns: **routing** (light to second-stage by ambiguity) and **prompt chaining** (the second stage receives the first structured output). With Jev, category/subcategory is a Choice over the existing taxonomy and sentiment is a separate Choice; Jev-escalated records intentionally have empty evidence text and no extracted issue because Jev does not return free-form spans. No parallelization or evaluator-optimizer is used. The app has no customer-facing generated answer or separate evaluator; the first-stage classifier runs at temperature 0.0. Human review, rather than an automatic third model call, resolves uncertain labels.

## Cost line

Estimate only; actual token use varies with comment length and structured response size. Using 200 input + 100 output tokens for the light call and 300 input + 100 output tokens for an escalation, and the listed OpenRouter rates at the time this note was written ($0.40/$1.60 per million input/output tokens for GPT-4.1 Mini; $2/$8 for GPT-4.1):

- Light call: `(200 × $0.40 + 100 × $1.60) / 1,000,000 = $0.00024` per return.
- Escalation: `(300 × $2 + 100 × $8) / 1,000,000 = $0.00140` additional; total escalated case is about `$0.00164`.
- At 10% escalation: `$0.00024 + 10% × $0.00140 = $0.00038` per return. The brief's 48,000 weekly orders × 31% returns implies about 14,880 weekly returns; this scenario is about `$5.65/week` or `$294/year` at 52 weeks.
- If every case escalated, the estimate is `$24.40/week`. This is an upper scenario at the assumed token counts, not a forecast.

Rates: [GPT-4.1 Mini on OpenRouter](https://openrouter.ai/openai/gpt-4.1-mini) and [GPT-4.1 on OpenRouter](https://openrouter.ai/openai/gpt-4.1/pricing). Recalculate from actual usage and selected provider before presenting as a budget. The 10% escalation assumption is for arithmetic only, not a measured result.

The project owner verified Jev's OpenRouter rate on 2026-10-03 as `$0.042` per million input tokens and `$0` per million output tokens. A 300-input-token request at that rate would cost `$0.0000126`, but Jev's taxonomy/options contribute to input usage; use OpenRouter's returned token usage and observed escalation volume for a realistic estimate. This rate should be rechecked before budgeting.

## Failure behavior and remaining limits

Invalid structured output, model/API failure, unknown return ID, database failure, or invalid reviewer taxonomy produces a visible error; no analysis is saved on model failure. Low-confidence rows stay pending human review. The confidence score is not calibrated. The 14-case test set is too small to claim production accuracy. API authentication/rate limiting and a deployed demo URL still need project account setup; do not expose real customer comments on an unauthenticated demo. The discovery note and implementation were not completed before the first code, and there is no human-labelled benchmark yet.
