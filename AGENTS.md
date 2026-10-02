# ChatGPT project context

This is the Dhaga & Co. Return Root-Cause Intelligence project workspace. The canonical local checkout is `G:\FDE-Projects\root-cause-intelligence`; use this checkout, not any old `C:\` mirror.

- Treat every file under `sources/` as read-only reference material.
- Do not edit, rename, move, or delete synced project files.
- These files may be replaced the next time a task is created from this ChatGPT project.

## Give coding agents project context

- Open the repository root in VS Code. Do not open only `app/` or `frontend/` as the workspace root.
- Start by reading `README.md`, this file, `docs/BUILD_NOTE.md`, and `docs/DEPLOYMENT.md` when relevant. Read `app/db/models.py` and the specific module being changed before modifying data or API behavior.
- VS Code agent harnesses that support `AGENTS.md` should load these instructions automatically. In Copilot Chat, use `#codebase` for a repository-wide task and explicitly attach `#file:README.md` or other key files when the task is specific.
- Treat code and documentation as the source of truth. The deployment snapshot below can change; check the current branch, Vercel deployment, environment-variable scope, and dashboard before acting on deployment status.

## Project overview

Dhaga & Co. Return Root-Cause Intelligence is an MVP for classifying free-text return reasons, routing uncertain results to human review, and calculating SKU/category return insights.

- Backend: FastAPI in `app/api.py`; SQLAlchemy models in `app/db/models.py`; Alembic migrations in `migrations/`.
- Data: schema-validated CSV ingestion in `app/ingestion/`; deterministic insight aggregation in `app/insights/`; OpenRouter classification in `app/ai/`.
- Frontend: static dashboard in `frontend/public/`.
- Data/model documentation: `README.md`, `docs/DISCOVERY_NOTE.md`, `docs/BUILD_NOTE.md`, and `docs/DEPLOYMENT.md`.

## Deployment and staging snapshot (2026-10-02)

- Git branch `audit-updates` is the Preview/testing branch. `main` is the Vercel Production branch. Keep testing changes on `audit-updates`; do not merge, promote, or push changes to `main` unless the user explicitly asks.
- Vercel uses separate projects: `root-cause-intelligence-api` and `root-cause-intelligence-web`.
- Preview API URL: `https://root-cause-intelligence-a-git-5c6067-amolmithari-5991s-projects.vercel.app`; frontend branch URL: `https://root-cause-intelligence-w-git-e12a3c-amolmithari-5991s-projects.vercel.app`.
- The API Preview environment variables are branch-scoped to `audit-updates`. `DATABASE_URL` is the staging database and `OPENROUTER_API_KEY` is required for classification. Secrets are maintained in Vercel; never reveal them, request them in chat, write them into Git, or assume the local `.env` is the staging database.
- The Vercel CLI blocks pulling secret environment values. For local staging database work, use a user-provided local ignored file such as `.env.preview.local`; check only non-secret target metadata, and never print the URL/password.
- Latest known Preview fix is commit `4b24674` (`Limit database connections in Vercel functions`). `app/db/session.py` uses `NullPool` on Vercel so each request closes its DB connection; local development keeps the normal SQLAlchemy pool. This reduces idle connections but cannot cap simultaneous connections across concurrent functions.
- Latest verified dashboard snapshot: 3,100 returns, 1,364 `Other` reasons, six analyzed returns, with SKU and category insight rows visible. Counts change as classifications/reviews run; verify live state before relying on this snapshot.
- Aiven previously rejected connections because regular connection slots were full. Do not restart the database or terminate sessions as an unapproved recovery action. Check Aiven's connection metrics and use its PgBouncer pooler if the plan supports it.

## Data operations

- Synthetic MVP data is under `sample_data/dhaga_synthetic_mvp/`; deterministic generator: `scripts/generate_synthetic_data.py`. It includes `order_items.csv` to satisfy the return-to-order-item relationship.
- Seed/load order: `vendors`, `customers`, `products`, `orders`, `order_items`, `returns`, `vendor_purchase_orders`, `support_tickets`, `app_search_events`. The dataset README contains exact commands and row counts.
- Insight aggregation is a separate manual operation after loading/classification; classification does not refresh insight tables automatically. The generated order cohort spans `2025-01-01` through `2026-09-13`; for monthly aggregation use start `2025-01-01`, exclusive end `2026-09-14`, grain `month`.
- Before running an ingestion, migration, classifier batch, or aggregator, confirm which database the process will use. Never point synthetic data or staging operations at Production.
- Do not run the test suite unless the user asks. Do not include untracked synthetic datasets or credential files in a commit unless explicitly requested.


## Project instructions

Keep changes small and consistent with the existing modules. Preserve referential integrity and fail visibly on invalid input; do not silently normalize colour/fabric text or invent business taxonomy. Keep credentials out of source files, terminal output, screenshots, and chat.
