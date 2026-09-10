# AGENTS.md

## Project

Lightweight product tracking web application for Bilibili membership-store resale products.

* Frontend: Vue 3 + Vite + JavaScript
* Backend: Python + FastAPI + SQLAlchemy
* Crawler: standalone Python CLI in `backend/crawler/crawler.py`
* Database: SQLite at `data/products.db`
* No TypeScript, no UI framework, no unnecessary dependencies.

## Architecture

```text
frontend/              Vue frontend (currently scaffold; business UI not implemented)
backend/               FastAPI application, services, repositories, models and crawler
backend/api/           FastAPI route modules
backend/services/      Business logic
backend/database/      SQLAlchemy models, sessions and repositories
backend/crawler/       Standalone data collection CLI
data/                  Runtime SQLite database and exports
docs/                  API, crawler, runbook and project progress documentation
scripts/               Utility scripts (currently empty)
```

Keep clear boundaries:

* Vue components handle UI and interaction.
* `frontend/src/api/` handles API requests when frontend integration is added.
* FastAPI `api/` handles HTTP endpoints.
* Backend `services/` handles business logic.
* Backend `database/` handles persistence.
* `backend/crawler/` handles data collection and writes crawl results to SQLite.

Do not put database queries directly in API route handlers.

## Frontend

* Use Vue 3 Composition API.
* Use JavaScript, not TypeScript.
* Keep the visual style minimal, clean, modern and premium.
* Strictly follow `frontend/DESIGN.md` for all frontend UI/UX development. Treat it as the source of truth for layout, colors, typography, spacing, radii, shadows, component styles, interaction states and responsive behavior.
* Read and understand the relevant `frontend/DESIGN.md` guidance before modifying frontend templates or styles; do not introduce visual patterns that conflict with it without explicitly updating the design specification first.
* Keep visual language consistent across frontend pages and components. Preserve documented hover, active, focus, loading, empty, error and disabled states when implementing or refactoring UI.

## Backend

* Keep FastAPI routes thin.
* Put business logic in services.
* Put database operations in repositories/database modules.
* Reuse the existing crawler implementation; do not rewrite it unnecessarily.
* Validate API input and return consistent JSON responses.
* Avoid unnecessary abstractions.
* Crawler execution can be initiated from the CLI or through the FastAPI manual trigger endpoint; keep subprocess execution isolated from request handling.
* Keep API behavior and `docs/api.md` synchronized when endpoints change.

## Database

The crawler creates the SQLite schema at startup. The current normalized schema includes:

* `products` — current product information
* `product_snapshots` — historical price and tag snapshots
* `crawl_runs` — crawl execution records
* `catalog_filters` — category, IP and sort options captured from the home endpoint
* `home_snapshots` — home-page overview snapshots
* `product_details` — latest detail summary per product
* `product_deals` — raw deal records
* `product_price_points` — raw chart points
* `favorites` — user favorites (currently keyed by a caller-provided `user_id`, default `default`)

Do not delete or recreate the database as part of normal code changes unless explicitly requested. The project currently permits rebuilding the database during development when the schema changes.

## Current capabilities and limits

* The crawler supports home/filter discovery, paginated product collection, optional detail collection, trend analysis, price alerts and JSON/CSV export.
* `--detail` collects details for every product returned in a run; large runs can be slow and more likely to hit rate limits.
* Detail, deal and price-point APIs only return data previously persisted by a crawler run using `--detail`.
* The frontend is still the default Vue scaffold and has not been connected to the API.
* Automated tests and authentication are not implemented yet.

## Documentation

* `docs/api.md` — HTTP API reference
* `docs/crawler.md` — all crawler CLI parameters and behavior
* `docs/runbook.md` — environment and run commands
* `docs/progress.md` — current project status and remaining work

## Verification

* Python execution is unavailable in the current restricted sandbox. Do not run `python`, `py`, or Python-based validation commands here.
* For Python changes, provide the exact verification commands for the user to run locally; use non-Python static checks in the sandbox where appropriate.
