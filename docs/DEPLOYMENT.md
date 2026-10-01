# Vercel deployment guide

Deployment is prepared but requires the group's GitHub and Vercel accounts. Vercel documents zero-configuration FastAPI deployment when a supported Python entry point exports an `app`; this repository provides root `index.py`. The static frontend is in `frontend/public`.

## Backend project

1. Push this repository to the group's GitHub organization.
2. Import the repository in Vercel. Set the project root to the repository root. Vercel should detect the FastAPI app from `index.py`.
3. Add these environment variables to Preview and Production as appropriate: `DATABASE_URL`, `OPENROUTER_API_KEY`, `OPENROUTER_BASE_URL`, `OPENROUTER_LIGHT_MODEL`, `OPENROUTER_HEAVY_MODEL`, `CORS_ORIGINS`.
4. Set `CORS_ORIGINS` to the exact frontend deployment origin(s), comma-separated. Do not add a trailing path.
5. Deploy a preview first and confirm `/health` and `/docs`. Promote only after the Aiven connection and model classification check work.

## Frontend project

1. Create a second Vercel project from the same GitHub repository.
2. Set its root directory to `frontend`. It is a static site from `public/`; no model or database secrets belong in this project.
3. Deploy. Open the page, enter the backend preview URL in **API address**, then select **Connect**.
4. After frontend deployment, add its origin to the backend project's `CORS_ORIGINS` and redeploy the backend.

Vercel documents FastAPI as a single Function and static assets served from `public/`: [FastAPI on Vercel](https://vercel.com/docs/frameworks/backend/fastapi). Actual deployment URL is not available until the repository is pushed and a Vercel project is connected.
