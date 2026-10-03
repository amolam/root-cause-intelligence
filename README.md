# Root-Cause Intelligence

An FDE MVP for Dhaga & Co.'s return root-cause problem. It ingests schema-shaped CSVs, classifies return comments through two LangChain models on OpenRouter, sends uncertain classifications to human review, and calculates SKU/category insights. It uses Aiven PostgreSQL, a FastAPI API, a mobile-friendly frontend, GitHub Actions, and two Vercel projects.

## Included

- SQLAlchemy 2 ORM models for customers, vendors, products, vendor size charts, orders, order items, status history, returns, reviews, catalogue attributes, AI analysis, human review, vendor purchase orders, support tickets, app search events, and SKU/category insight tables.
- Alembic migrations for the initial schema, normalized vendor master and relationships, and operational data tables.
- Environment-based PostgreSQL configuration with the `psycopg` driver and Aiven TLS URL support.
- CSV ingestion with header/field validation, typed values, basic whitespace cleanup, line-level errors, and one transaction per dataset.
- Small sample CSV fixtures plus a larger deterministic synthetic MVP dataset (12 vendors, 500 SKUs, 1,000 customers, 10,000 orders, 3,100 returns, and related operational tables).
- Return-text classification with validated structured output, low-confidence escalation, and human-review routing.
- FastAPI endpoints for dashboard metrics, insights, classification, and human review.
- A responsive static frontend for the category user, with visible API/model failures.
- Offline labelled-case evaluation and GitHub Actions CI.
- Discovery, build, and deployment notes under `docs/`.
- A detailed [architecture and technology stack guide](docs/ARCHITECTURE.md).
- Tests that do not require a database server.

## Use this project in VS Code with AI models

Open the canonical workspace folder `G:\FDE-Projects\root-cause-intelligence` (File → Open Folder). Do not use the old `C:\` mirror or open only a subfolder as the workspace root. This repository's root `AGENTS.md` provides reusable project context to Codex and VS Code agent harnesses that support it.

For a broad Copilot Chat task, include `#codebase`. For a focused change, add `#file:README.md`, `#file:AGENTS.md`, and the relevant source/docs files from the Chat context picker (for example, `#file:app/db/models.py` or `#file:docs/BUILD_NOTE.md`). If Copilot does not include repository instructions, enable `github.copilot.chat.codeGeneration.useInstructionFiles` in VS Code Settings. VS Code supports repository-wide instructions using `AGENTS.md` and/or `.github/copilot-instructions.md`; instruction support depends on the selected agent harness. See the [VS Code context guide](https://code.visualstudio.com/docs/chat/copilot-chat-context) and [custom instructions guide](https://code.visualstudio.com/docs/agent-customization/custom-instructions).

Suggested first prompt:

> Read `AGENTS.md`, `README.md`, and the relevant files under `docs/`. This is Dhaga & Co.'s Return Root-Cause Intelligence MVP. Work from this repository root on `audit-updates` for Preview changes. Keep `sources/` read-only, don't expose or commit credentials, and don't target Production with synthetic data. First summarize the existing implementation and current state, then make only the requested change.

`AGENTS.md` is the compact operational context; this README and `docs/` provide the fuller product, schema, setup, and deployment details. Verify branch and deployment state before relying on dated status notes.

## Local setup

Requires Python 3.11+ and an Aiven PostgreSQL service (or compatible local PostgreSQL).

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
```

Set `DATABASE_URL` in `.env` to the connection URL shown by Aiven and set `OPENROUTER_API_KEY` from OpenRouter. Keep Aiven TLS requirements from the service connection instructions. Never commit `.env` or credentials.

For Vercel, the API project's `audit-updates` Preview environment has a separate staging `DATABASE_URL` and an `OPENROUTER_API_KEY`; Production values are separate. Vercel's CLI does not export Secret variables. Do not assume `.env` is the Preview database, and never paste credentials into chat or source control. For a local staging operation, use an ignored `.env.preview.local` and verify only its non-secret host/database metadata before running a command.

The static frontend build requires `API_BASE_URL`, a non-secret API origin. Set it separately in the Vercel web project's Preview and Production environments; it is embedded in the generated dashboard config at build time.

Apply the schema:

```powershell
alembic upgrade head
```

Run the database metadata tests:

```powershell
pytest
```

## Load data

Load a single dataset after its referenced parent datasets exist. The loader accepts only columns from that dataset's mapped schema, checks required fields and parses dates, numbers, booleans, UUIDs, and JSON. It trims leading/trailing whitespace and maps blank optional cells to `NULL`; it does not guess colour/fabric aliases or recode return reasons. If validation or database loading fails, that dataset transaction is rolled back and the error identifies the CSV line or database failure.

```powershell
python -m app.ingestion.cli load products path\to\products.csv
```

To load the bundled synthetic example data in foreign-key order (including a placeholder vendor row):

```powershell
python -m app.ingestion.cli seed
```

The seed command can be repeated: existing rows with the same schema key are updated. The examples use fictional IDs and values and must not be treated as client data. It seeds the customer/order/return path plus vendor purchase order, support ticket, and app search examples. Other mapped datasets can be loaded with `load` after their referenced parents exist. The sample vendor's name and city are explicit `Unknown` placeholders because the available fixture has no vendor master details.

### Larger synthetic MVP dataset

The deterministic generator is `scripts/generate_synthetic_data.py`. Its output is in `sample_data/dhaga_synthetic_mvp/`; see that folder's README for every CSV schema, sample blocks, volumes, exact ratios, and manual load commands. It includes `order_items.csv` because returns have a composite foreign key to their order item. The generated files and generator currently exist in this local workspace; confirm they are present before relying on them in a new clone.

To load them to the database configured by `.env` (confirm that it is a disposable staging/test database first):

```powershell
python -m app.ingestion.cli seed --directory sample_data/dhaga_synthetic_mvp
```

The operation upserts matching identifiers and commits one dataset at a time in foreign-key order. Do not run it against Production. To use a local `.env.preview.local` without printing the secret, set `DATABASE_URL` inside the same Python process before importing the loader; the dataset README documents the complete command.

## Classify return reasons

Classification uses Jev directly through OpenRouter by default (`CLASSIFICATION_MODE=jev_only`, `JEV_OPENROUTER_MODEL=typesafe/jev-1.13`). Configure `OPENROUTER_API_KEY` in `.env`. Jev returns a taxonomy-constrained category/subcategory choice plus sentiment; `extracted_issue` and exact `evidence_text` are empty because this endpoint does not return free-form spans. To opt into the older two-stage flow, set `CLASSIFICATION_MODE=two_stage`; it uses `OPENROUTER_LIGHT_MODEL` (`openai/gpt-4.1-mini` by default) and escalates low-confidence/`OTHER` results to `SECOND_STAGE_BACKEND` (`openrouter` by default, or `jev`). The OpenRouter second-stage model defaults to `OPENROUTER_HEAVY_MODEL=openai/gpt-4.1`. All model choices use the same API key. `CUSTOMER_PREFERENCE/CHANGED_MIND` is available for explicit changed-mind returns.

Classify the seeded sample return:

```powershell
python -m app.ai.cli --return-id RET-SAMPLE-001
```

Or process up to 100 returns with no existing AI analysis:

```powershell
python -m app.ai.cli --limit 100
```

To reclassify returns whose latest analysis is pending human review, preserving prior AI and human-review history:

```powershell
python -m app.ai.cli --reclassify-pending --limit 3000
```

The classifier adds a new analysis row for each return. The newest row becomes the active prediction and its review status is calculated from its result; do not delete old analyses or manually change their status to trigger reclassification.

In Jev-only mode, Jev classifies each return directly without a GPT first pass or confidence-based second call. In two-stage mode, confidence below 0.75 or `OTHER` triggers escalation. In either mode, after the final result only `OTHER` is marked `PENDING`; specific taxonomy labels are `NOT_REQUIRED`, even at low confidence. Confidence remains stored for reporting, so review reduction should be monitored against human-labelled accuracy. Model input contains only the return reason and free-text comment, plus the first structured prediction in two-stage mode; expected/human labels are never used for inference. Model/API failures are printed as failed rows and do not create AI analysis rows. The recorded model version is the configured identifier because the provider does not return an immutable build ID.

Evaluate against the 14 labelled text cases from the schema document, including Hinglish:

```powershell
python -m app.ai.evaluate
```

Expected labels are read only after each prediction for score calculation. This small set supports a demo check; it does not establish production accuracy.

## Calculate SKU and category insights

Aggregation is deterministic Python/database work and makes no model calls. The period is based on the order-created date (an order cohort): returns are counted against the cohort of their original order. Supported grains are day, week, and month, and `analysis_period` stores the start date of that bucket. The schema does not define this convention, so it is an MVP assumption. Return rate is `returns / distinct orders` (a ratio from 0 to 1); issue rates use the same order denominator. Only the latest AI analysis per return contributes to issue counts; returns without analysis still contribute to total returns.

Calculate insights for the sample order cohort:

```powershell
python -m app.insights.cli --start 2025-01-01 --end 2026-01-01 --grain month
```

This writes/upserts the documented `sku_return_insights` and `category_return_insights` rows. `top_problem_skus` is stored as a JSON list of up to five objects containing `sku_id`, `return_rate`, and `total_returns`; this representation is another assumption because the schema only specifies the JSON type.

Dashboard API classification refreshes the affected monthly insight cohort after saving the AI analysis, so FIT/QUALITY issue rates update with the classification. Classification through `python -m app.ai.cli` does not refresh insights; rerun the aggregation command after a CLI batch.

## Run the API and frontend

After migration and sample seed, start the API in one terminal:

```powershell
uvicorn app.api:app --reload
```

In another terminal, serve the static UI:

```powershell
python -m http.server 5173 --directory frontend/public
```

The local `frontend/public/runtime-config.js` points to `http://localhost:8000`. Open `http://localhost:5173`; the dashboard connects automatically and shows sample counts, insights, a classification form, and the human-review queue. Try a missing return ID to see the visible failure path. FastAPI's interactive endpoint documentation is at `http://localhost:8000/docs`.

The API returns an existing classification for repeated requests to avoid accidental additional model calls. To deliberately re-run classification, use `python -m app.ai.cli --return-id <ID>`.

The review queue's **Reset classifications** action calls `POST /api/admin/reset-classifications`. This demo endpoint deletes AI analyses and human review records, then recalculates SKU/category insights; returns, orders, customers, and products are retained. The endpoint is intentionally unauthenticated for this demo. The **Recalculate insights** button in Category to SKU recomputes the aggregates from current classifications without changing them. Page load, **Refresh**, and date-range changes only reload the displayed data.

## Build and deployment status

The project covers the Phase 2 implementation items: visible responsive frontend, API, two model tiers, structured output, human review, a realistic text-case fixture, visible failures, and a build note with code/model split, patterns, temperature, and estimated cost. See [docs/BUILD_NOTE.md](docs/BUILD_NOTE.md) and [docs/DISCOVERY_NOTE.md](docs/DISCOVERY_NOTE.md).

The app is deployed as separate Vercel projects. `audit-updates` is the Preview/testing branch; `main` is Production. The latest known API Preview fix is commit `4b24674` (`Limit database connections in Vercel functions`), which uses SQLAlchemy `NullPool` in Vercel so request connections close instead of remaining idle in warm serverless instances. This reduces idle connections but does not cap simultaneous requests. The Preview OpenRouter key and staging database URL are configured in Vercel for `audit-updates`; keep Production secrets separate.

At the last verified dashboard check, the staging database had 3,100 returns, 1,364 marked `Other`, six classified returns, and populated SKU/category insight tables. Treat counts and deployment IDs as a dated snapshot, not a constant. Aiven previously returned “remaining connection slots are reserved for roles with the SUPERUSER attribute”; check Aiven connection metrics if it recurs. See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for project URLs and branch workflow.

## Schema mapping and assumptions

The field lists follow the schema document. The document does not specify primary keys for several entities, nullability for many fields, or identifier strategy for the aggregate insight rows. This implementation uses the listed natural IDs as primary keys where available, a composite `(size_chart_id, vendor_id, size_label)` key for vendor/size-specific size chart records, `(sku_id, attribute_name)` for catalogue attributes, `(sku_id, analysis_period)` for SKU insights, and `(category, subcategory, analysis_period)` for category insights. UUIDs are used for the two UUID fields explicitly specified by the document.

Required fields are enforced where the schema says “Yes”; where the document omits requiredness, fields are nullable unless they are necessary identifiers or foreign-key links. `return_reason` is free text so the documented `Other` value remains accepted. No proposed AI taxonomy or status vocabulary is enforced as a database enum.

Foreign keys encode the stated entity relationships: order→customer, order item→order/product, return→order/order item/product/customer, review→product/customer, analysis→return/product, human review→analysis, and insights/attributes→product. To make the return's order and order item linkage consistent, order items have a unique `(order_item_id, order_id)` pair.

### Gaps requiring discovery before production

- Exact nullable/required rules where the document leaves `Required` blank.
- Stable ID formats and whether source systems ever reuse IDs.
- Whether size-chart measurements have units beyond the optional `unit` field and whether charts need version/effective dates.
- The schema has no acquisition/campaign entity or explicit attribution key. The brief says returns connect downstream to Customer Acquisition, but does not define the join; this layer does not invent one.
- Colour/fabric normalization rules and canonical values need client-approved mappings before ingestion.
- Insight period grain is represented by the provided `DATE` field; whether it means day, week, or month remains unspecified.

## Ingestion limitations and next discovery

The MVP loader reads each CSV into memory before inserting it, so it is intended for the schema document's test-data scale, not a direct one-shot import of all 11 million production orders. Larger production imports should use chunked staging and bulk loading after agreeing source file contracts. Validation errors stop that file visibly rather than silently skipping bad rows. Canonical colour/fabric normalization is deferred until Dhaga approves mapping rules.
