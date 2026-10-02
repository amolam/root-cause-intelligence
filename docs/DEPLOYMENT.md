# Vercel deployment guide

The repository is connected to GitHub and Vercel. The backend uses root `index.py` to export the FastAPI app; the static frontend is in `frontend/public`. The API and web frontend are separate Vercel projects.

## Current branch workflow

- `audit-updates` is the Preview/testing branch. Push test changes here and inspect the API and frontend Preview deployments.
- `main` is the Production branch. Do not merge or promote Preview to Production until the user explicitly requests it after validation.
- API project: `root-cause-intelligence-api`.
- Frontend project: `root-cause-intelligence-web`.
- Current API branch alias: `https://root-cause-intelligence-a-git-5c6067-amolmithari-5991s-projects.vercel.app`.
- Current frontend branch alias: `https://root-cause-intelligence-w-git-e12a3c-amolmithari-5991s-projects.vercel.app`.
- Latest known API Preview fix: commit `4b24674`, “Limit database connections in Vercel functions”. Verify latest branch deployment status in Vercel before relying on this snapshot.

The API Preview uses branch-scoped `DATABASE_URL`, `OPENROUTER_API_KEY`, and `CORS_ORIGINS` values for `audit-updates`. The database URL is the staging DB. Production values remain separate. Do not move, reveal, or commit secrets; do not use the Production database for synthetic-data loads.

## Backend project

1. Keep the project root as the API root. Vercel detects the FastAPI app from `index.py`.
2. Set `DATABASE_URL` and `OPENROUTER_API_KEY` for the Preview branch `audit-updates`; keep Production credentials scoped to Production.
3. Set Preview `CORS_ORIGINS` to the exact frontend Preview origin with no trailing path.
4. Check the API Preview `/health` endpoint, connect the frontend, and validate counts/classification/insight paths.
5. When environment variables change, redeploy the API Preview from Vercel's Deployments page; environment updates apply to new deployments.

## Frontend project

1. Keep the frontend project root at `frontend`. It is a static site from `public/`; no model or database secrets belong in this project.
2. Open the frontend Preview URL, set **API address** to the API Preview URL above, and select **Connect**.
3. If the frontend Preview origin changes, update the API Preview `CORS_ORIGINS` branch variable and redeploy the API Preview.

The API uses SQLAlchemy `NullPool` when running on Vercel so idle connections are closed after each request. Local development retains the regular SQLAlchemy pool. Aiven's own PgBouncer pooler is an additional option on eligible plans. Vercel documents FastAPI deployment as a Function and static assets served from `public/`: [FastAPI on Vercel](https://vercel.com/docs/frameworks/backend/fastapi).
