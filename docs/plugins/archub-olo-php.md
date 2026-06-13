---
tags:
  - Plugins
  - Deployment
---

# ArcHub OurLifeOrganized PHP Plugin

`archub.olo.php` is an external PHP 8.4 plugin that demonstrates a
MyLifeOrganized/OurLifeOrganized-style task system. It is intentionally separate from
the Python process to show the HTTP plugin model.

## Capabilities

| Capability | Detail |
|---|---|
| Hierarchical outline | projects and sub-tasks with materialized path/depth |
| Computed priority | importance, urgency, due-date amplification and star score |
| GTD contexts | `@calls`, `@errands`, `@computer`, `@waiting` |
| Smart views | To-Do, Next Actions, Inbox, Today, Overdue, Starred |
| Recurrence | RRULE `FREQ` + `INTERVAL`, `FROM_DUE` and `FROM_COMPLETE` modes |
| Audit feed | task lifecycle events exposed as read model |
| ArcHub bridge | `POST /api/arc-tool` |

## API

| Endpoint | Purpose |
|---|---|
| `GET /api/olo/overview` | counts and capability overview |
| `GET /api/olo/tasks` | task list |
| `GET /api/olo/outline` | nested tree |
| `GET /api/olo/todo` | ranked To-Do list |
| `GET /api/olo/contexts` | GTD contexts |
| `GET /api/olo/recurrence/{id}` | next occurrence preview |
| `GET /api/olo/events` | event feed |
| `POST /api/arc-tool` | ArcHub tool bridge |

## Local Run

```bash
cd plugins/archub_olo_php
composer install
composer serve
```

Open `http://127.0.0.1:8098`. Keep the manifest disabled until `/health` responds.

## Docker Run

```bash
docker build -t archub-olo-php plugins/archub_olo_php
docker run --rm -p 8098:8098 --env-file plugins/archub_olo_php/.env.example archub-olo-php
```

## Release Packaging

```bash
archub-marketplace-build --output dist/archub-marketplace --plugin-dir plugins
```

The package includes manifest, source, Composer metadata, OpenAPI and public assets.
Runtime dependency directories are excluded and rebuilt in the plugin image.
