# ArcHub OurLifeOrganized (OLO) PHP Plugin

`archub.olo.php` is an external ArcHub productivity plugin that ports the
**OurLifeOrganized** (MyLifeOrganized-style) GTD task manager to PHP 8.4 and
Symfony 8 components. It mirrors the `archub.ru.wiki.php` plugin layout and
reproduces the core domain of the upstream OLO platform — a CQRS / Event-Sourcing
system — as a self-contained, in-process read model.

## Capabilities

- **Hierarchical task outline** — projects and sub-tasks with a materialised
  `path`/`depth`, exactly like the OLO `rm_task` read model.
- **Computed star priority** — the signature MyLifeOrganized feature: a 0..100
  score and 0..5 stars derived from importance, urgency and due-date proximity.
  It powers the ranked **To-Do** view.
- **GTD contexts** — `@calls`, `@errands`, `@computer`, `@waiting` with live
  active-task counts and per-context views.
- **Due & start dates, reminders and flags/stars.**
- **Recurrence** — an RRULE engine (`FREQ` + `INTERVAL`) with the two OLO modes
  `FROM_DUE` and `FROM_COMPLETE`, plus a next-occurrence preview that mirrors the
  OLO Temporal recurrence workflow (`TaskRecurrenceAdvanced`).
- **Smart views** — To-Do, Next Actions, Inbox, Today, Overdue, Starred.
- **Operator reports** — per-user summary mirroring the OLO `admin-cli`.
- **Event-sourced audit feed** — `TaskCreated`, `TaskMoved`, `TaskDueAtSet`,
  `TaskCompleted`, `TaskRecurrenceSet`, `TaskRecurrenceAdvanced`.
- ArcHub external runtime endpoint: `POST /api/arc-tool`.

## Computed priority

The To-Do list is ranked by a derived score rather than a hand-entered field:

```
score = 0.6 * importance + 0.4 * urgency
      + due-date amplification (overdue +35, today +25, soon +15, upcoming +5)
      + star bonus (+10)        # clamped to 0..100, completed tasks score 0
stars = round(score / 20)       # 0..5
```

See `src/Domain/PriorityCalculator.php`.

## HTTP API

| Endpoint | Purpose |
|---|---|
| `GET /api/olo/overview` | Capability overview + counts |
| `GET /api/olo/tasks` / `/{id}` | Flat task list / single task with sub-tasks |
| `GET /api/olo/outline` | Nested project tree |
| `GET /api/olo/todo` | Computed-priority To-Do list |
| `GET /api/olo/next-actions` `/inbox` `/today` `/overdue` `/starred` | Smart views |
| `GET /api/olo/due-soon?days=N` | Tasks due within N days |
| `GET /api/olo/contexts` / `/{key}` | GTD contexts and their tasks |
| `GET /api/olo/recurrence/{id}` | Next-occurrence preview |
| `GET /api/olo/reports/summary` | Per-user operator report |
| `GET /api/olo/events` | Event-sourced audit feed |
| `GET /api/olo/search?q=` | Search by title, notes and context |
| `POST /api/arc-tool` | ArcHub external runtime bridge |

## Local Run

```bash
cd plugins/archub_olo_php
composer install
composer serve
```

Open `http://127.0.0.1:8098`. The ArcHub manifest keeps the plugin disabled by
default; enable it from plugin management only after the PHP service is running.

Docker:

```bash
cd plugins/archub_olo_php
docker build -t archub-olo-php .
docker run --rm -p 8098:8098 --env-file .env.example archub-olo-php
```

## Packaging

The marketplace generator packages the full plugin directory:

```bash
archub-marketplace-build --output dist/archub-marketplace
```

The archive includes `plugin.json`, `composer.json`, `public/`, `src/`,
`openapi.yaml` and the static task-manager assets.
