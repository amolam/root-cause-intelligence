# Root-Cause Intelligence

An FDE MVP for Dhaga & Co.'s return root-cause problem. It ingests schema-shaped CSVs, routes return comments through two LangChain models on OpenRouter, sends uncertain classifications to human review, and calculates SKU/category insights. It uses Aiven PostgreSQL, a FastAPI API, a mobile-friendly frontend, GitHub Actions, and Vercel-ready deployment layouts.

## Included

- SQLAlchemy 2 ORM models for customers, vendors, products, vendor size charts, orders, order items, status history, returns, reviews, catalogue attributes, AI analysis, human review, vendor purchase orders, support tickets, app search events, and SKU/category insight tables.
- Alembic migrations for the initial schema, normalized vendor master and relationships, and operational data tables.
- Environment-based PostgreSQL configuration with the `psycopg` driver and Aiven TLS URL support.
- CSV ingestion with header/field validation, typed values, basic whitespace cleanup, line-level errors, and one transaction per dataset.
- Small, clearly synthetic sample CSVs for the vendor/customer → product/order → order item → return path.
- Return-text classification with validated structured output, low-confidence escalation, and human-review routing.
- FastAPI endpoints for dashboard metrics, insights, classification, and human review.
- A responsive static frontend for the category user, with visible API/model failures.
- Offline labelled-case evaluation and GitHub Actions CI.
- Discovery, build, and deployment notes under `docs/`.
- Tests that do not require a database server.

## Local setup

Requires Python 3.11+ and an Aiven PostgreSQL service (or compatible local PostgreSQL).

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
```

Set `DATABASE_URL` in `.env` to the connection URL shown by Aiven and set `OPENROUTER_API_KEY` from OpenRouter. Keep Aiven TLS requirements from the service connection instructions. Never commit `.env` or credentials.

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

## Classify return reasons

The AI layer uses LangChain's OpenAI-compatible chat integration through OpenRouter, with structured output validated against the proposed schema taxonomy. Configure `OPENROUTER_API_KEY`, `OPENROUTER_BASE_URL`, `OPENROUTER_LIGHT_MODEL`, and `OPENROUTER_HEAVY_MODEL` in `.env`. Defaults route `openai/gpt-4.1-mini` ordinary cases and `openai/gpt-4.1` escalations through OpenRouter; change either model slug if your OpenRouter account cannot access it. Structured-output routing is required so requests fail visibly rather than falling back to an endpoint that ignores the schema. The key is only needed when calling the classifier.

Classify the seeded sample return:

```powershell
python -m app.ai.cli --return-id RET-SAMPLE-001
```

Or process up to 100 returns with no existing AI analysis:

```powershell
python -m app.ai.cli --limit 100
```

The light model handles normal cases. A result below the configured 0.75 confidence threshold or in `OTHER` is sent to the heavier model. The second prompt receives the source text and first structured prediction, then reassesses it. This provides two patterns: routing and prompt chaining. If the final result is still below the threshold or `OTHER`, `human_review_status` is set to `PENDING`; otherwise it is `NOT_REQUIRED`. These status strings and the threshold are MVP choices requiring calibration against human-labelled Dhaga examples. Model input contains only the return reason and free-text comment; expected/human labels are not used for inference. Model/API failures are printed as failed rows and do not create AI analysis rows. The recorded model version is the configured identifier because the provider does not return an immutable build ID.

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

## Run the API and frontend

After migration and sample seed, start the API in one terminal:

```powershell
uvicorn app.api:app --reload
```

In another terminal, serve the static UI:

```powershell
python -m http.server 5173 --directory frontend/public
```

Open `http://localhost:5173`, keep the API address at `http://localhost:8000`, and select **Connect**. The dashboard shows sample counts, insights, a classification form, and the human-review queue. Try a missing return ID to see the visible failure path. FastAPI's interactive endpoint documentation is at `http://localhost:8000/docs`.

The API returns an existing classification for repeated requests to avoid accidental additional model calls. To deliberately re-run classification, use `python -m app.ai.cli --return-id <ID>`.

## Build and deployment status

The project covers the Phase 2 implementation items: visible responsive frontend, API, two model tiers, structured output, human review, a realistic text-case fixture, visible failures, and a build note with code/model split, patterns, temperature, and estimated cost. See [docs/BUILD_NOTE.md](docs/BUILD_NOTE.md) and [docs/DISCOVERY_NOTE.md](docs/DISCOVERY_NOTE.md).

Vercel setup is in [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md). The frontend and API are prepared as separate Vercel projects. They are not deployed yet: the workspace has no GitHub remote, and Vercel CLI/account connection is not configured.

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
