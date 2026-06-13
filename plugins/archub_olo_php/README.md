# ArcHub OurLifeOrganized (OLO) PHP Plugin

External ArcHub plugin that ports the **OurLifeOrganized** (MyLifeOrganized-style)
GTD task manager to a modern PHP stack — PHP 8.4 and Symfony 8 components —
mirroring the `archub_ru_wiki_php` wiki plugin layout.

It reproduces the core domain of the upstream OLO platform
(`/Users/vladimir/IdeaProjects/ourlifeorganized`, a CQRS / Event-Sourcing system)
as a self-contained, in-process read model so it can run anywhere PHP runs.

## Capabilities

- **Hierarchical task outline** — projects and sub-tasks with a materialised
  `path`/`depth`, exactly like the OLO `rm_task` read model.
- **Computed star priority** — the signature MyLifeOrganized feature: a 0..100
  score and 0..5 stars derived from importance, urgency and due-date proximity
  (see `Domain/PriorityCalculator`). It powers the ranked **To-Do** view.
- **GTD contexts** — `@calls`, `@errands`, `@computer`, `@waiting` with live
  active-task counts and per-context views.
- **Due & start dates, reminders, flags/stars.**
- **Recurrence** — a pragmatic RRULE engine (`FREQ` + `INTERVAL`) with the two
  OLO modes `FROM_DUE` and `FROM_COMPLETE`, plus a next-occurrence preview that
  mirrors the OLO Temporal recurrence workflow (`TaskRecurrenceAdvanced`).
- **Smart views** — To-Do, Next Actions, Inbox, Today, Overdue, Starred.
- **Operator reports** — per-user summary mirroring the OLO `admin-cli`.
- **Event-sourced audit feed** — `TaskCreated`, `TaskMoved`, `TaskDueAtSet`,
  `TaskCompleted`, `TaskRecurrenceSet`, `TaskRecurrenceAdvanced`.
- **HTTP integration endpoint** for the ArcHub external plugin runtime:
  `POST /api/arc-tool`.

## Architecture

DDD layering identical to the wiki plugin:

```
src/
  ArcHubOloApplication.php      # HTTP router + /api/arc-tool bridge
  Application/TaskService.php   # views, computed priority, reports, recurrence, search
  Domain/Task.php               # outline node (rm_task-style path/depth)
  Domain/Context.php            # GTD context value object
  Domain/Recurrence.php         # RRULE engine, FROM_DUE / FROM_COMPLETE
  Domain/PriorityCalculator.php # MLO computed star priority
  Infrastructure/SeedTaskRepository.php  # seed outline + contexts + event feed
  Renderer/TaskRenderer.php     # dashboard, smart views, task detail, outline tree
```

## Run Locally

```bash
cd plugins/archub_olo_php
composer install
composer serve
```

Open `http://127.0.0.1:8098`.

Docker:

```bash
docker build -t archub-olo-php .
docker run --rm -p 8098:8098 --env-file .env.example archub-olo-php
```

## ArcHub Integration

The module is discovered through `plugin.json` and stays disabled by default in
development. Start the PHP service, then enable `archub.olo.php` from the ArcHub
plugin management surface to test the external runtime bridge.
