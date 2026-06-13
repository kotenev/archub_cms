# ArcHub Lite (PHP)

The **shared-hosting edition** of the ArcHub platform. Where the full platform is a
Python/FastAPI app, ArcHub Lite is a small, **dependency-free PHP application** that runs
anywhere a typical shared host gives you **PHP-FPM + nginx + PostgreSQL** — no Composer,
no Docker, no root, no background daemons. Upload a folder over FTP, point the document
root at `public/`, and it runs.

It distils the platform's core into two pillars that fit shared hosting:

- **Headless CMS + knowledge base** — a hierarchical page tree with draft/publish, a JSON
  **delivery API** (`/api/content/*`), and **PostgreSQL full-text search** (`tsvector` +
  GIN, `websearch_to_tsquery`).
- **Lite ITIL service desk** — raise incidents / service requests / questions and walk
  them through a **guarded status workflow** (open → in&nbsp;progress → resolved → closed).

## Why a "lite" edition?

| Full ArcHub platform | ArcHub Lite |
|---|---|
| Python 3.11+ / FastAPI / uvicorn | PHP 8.1+ / PHP-FPM |
| Long-running ASGI process | Stateless per-request (PHP-FPM) |
| SQLite or PostgreSQL | PostgreSQL (or in-memory trial) |
| Offline + online LLM/RAG | PostgreSQL full-text search |
| Plugin runtime, BPMN engine, CMDB/SLA | CMS + delivery API + lite service desk |
| Docker / Compose / cluster | **One folder on shared hosting** |

It is **API-compatible in spirit** (`/api/content/tree`, `/api/content/{slug}`,
`/api/search`) so a headless frontend built against ArcHub Lite can later point at the
full platform.

## Requirements

- PHP **8.1+** with `pdo_pgsql`, `mbstring`, `session` (all standard on shared hosts).
- **PostgreSQL 12+** (generated columns for full-text search).
- nginx + PHP-FPM (an Apache `.htaccess` fallback is included).

## Install (5 minutes)

1. **Upload** the `archub-lite-php/` folder to your host (e.g. `/var/www/archub-lite`).
2. **Configure** — copy and edit the config file:
   ```bash
   cp config.php.example config.php
   # set db_* credentials and an admin password hash:
   php -r "echo password_hash('your-password', PASSWORD_DEFAULT), PHP_EOL;"
   ```
   Paste the hash into `admin_password_hash` in `config.php`.
3. **Point the web root** at `public/`:
   - nginx: adapt `deploy/nginx.conf.example`.
   - Apache: the bundled `public/.htaccess` handles routing.
4. **Open the site.** The schema is created automatically on the first request. Prefer a
   deploy step? Run `php bin/migrate.php` (or load `deploy/schema.sql` with `psql`).

## Try it with no database

Set `'storage' => 'memory'` in `config.php` for a non-persistent demo (data lives for one
request only) — handy to verify hosting before creating the database.

## URLs

| URL | What |
|---|---|
| `/` | Public site (page tree + search) |
| `/p/{slug}` | A published page |
| `/search?q=…` | Full-text search |
| `/support` | Raise a service-desk request |
| `/support/{key}` | Track a request (e.g. `REQ-12`) |
| `/admin` | Backoffice (pages + service desk) |
| `/api/content/tree` | Published tree (JSON) |
| `/api/content/{slug}` | A published page (JSON) |
| `/api/search?q=…` | Search (JSON) |
| `/api/requests` | Create a request (JSON, `POST`) |
| `/api/content` | Create a page (JSON, `POST`, `X-Admin-Token`) |
| `/health` | Health check |

## Architecture

DDD layering consistent with the platform's PHP plugins:

```
public/index.php          # front controller (point the web root here)
config.php                # your settings (copied from config.php.example)
src/
  Kernel/                 # Autoloader (PSR-4, no Composer), Config, Request,
                          #   Response, Router, Database (PDO/Postgres)
  Domain/                 # Page, ServiceRequest + repository interfaces (ports)
  Application/            # ContentService, ServiceDeskService, Auth
  Infrastructure/         # Pdo* repositories, InMemory* repositories, Migrator
  Renderer/               # Layout, SiteRenderer, AdminRenderer
  App.php                 # composition root + routing
bin/migrate.php           # optional CLI schema bootstrap
deploy/                   # nginx.conf.example, schema.sql
tests/smoke.php           # dependency-free smoke test (in-memory backend)
```

Storage sits behind repository **ports**, so PostgreSQL (`PdoPageRepository`,
`PdoServiceRequestRepository`) is the production adapter and the in-memory adapters power
tests and the no-database trial.

## Security notes

- The admin UI is **locked** until you configure `admin_password_hash` (safe by default).
- The headless write API requires a shared-secret `X-Admin-Token`.
- The nginx/Apache configs **deny** access to `config.php`, `src/`, `bin/` and dotfiles —
  keep `config.php` outside any path the web server will serve directly.

## Test

```bash
php tests/smoke.php
```

Runs 23 checks across delivery, search, the service desk, admin auth and the workflow
guard — no PostgreSQL needed (uses the in-memory backend).
