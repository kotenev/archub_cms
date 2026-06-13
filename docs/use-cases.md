# Use Cases

ArcHub is deliberately broad — a CMS, a knowledge base and an ITSM suite on one core — so
the same package fits very different jobs. This page walks through the **typical
scenarios** ArcHub is built for: who it's for, why ArcHub fits, how you'd wire it, and
which capabilities carry the load.

!!! tip "Pick by shape, not by label"
    Most teams adopt ArcHub for **one** pillar first (knowledge, content, or ITSM) and
    grow into the others because they share the same data model, auth boundary and
    deployment artifact.

---

## 1. Air-gapped / regulated corporate knowledge base

**Who:** banks, defense, healthcare, government, industrial — anywhere SaaS knowledge
tools (Confluence Cloud, Notion) are forbidden and data must not leave the perimeter.

**Why ArcHub:** the default stack has **zero external dependencies** — embedded SQLite
plus a fully **offline-extractive LLM**. You get hybrid lexical + semantic search,
backlinks, a knowledge graph and RAG-style answers **with no network egress and no API
keys**. When/if policy allows, point it at an *on-prem* OpenAI-compatible endpoint
(vLLM, Ollama, LM Studio, TGI) for generative answers — the circuit breaker falls back
to offline if it's down.

**How:**

```bash
# Nothing but Python required. No Node, no DB server, no internet.
python -m pip install -e ".[server]"
uvicorn archub_cms.app:create_archub_app --factory --host 0.0.0.0 --port 8088
```

**Key capabilities:** offline-extractive LLM · FTS5 hybrid search · backlinks/graph ·
vault export · `AuditSink` for governance · non-root container. See
[Deployment Map → Air-Gapped Operations](deployment/scenarios.md#air-gapped-operations).

---

## 2. Headless CMS behind a marketing / product site

**Who:** product and marketing teams who want structured content with a **JSON delivery
API**, consumed by a Next.js/Astro/SvelteKit frontend or a mobile app.

**Why ArcHub:** Umbraco-style document types, reusable data types and templates give
editors a real content model — not free-text pages. The published **delivery API**
serves content, tree/navigation, search, tags, RSS and `sitemap.xml` with proper cache
headers, and a Content Builder block registry renders structured blocks to HTML or JSON.

**How:** publish in the backoffice (`/admin/archub`), consume from the frontend:

```http
GET /cms/api/tree                # navigation
GET /cms/api/content/{slug}      # a published node as JSON
GET /cms/api/search?q=pricing    # delivery search
GET /cms/sitemap.xml             # SEO
```

**Key capabilities:** document/data types · Content Builder · versioning & preview
tokens · domains/cultures/variants · delivery cache headers · runtime export. See
[Content Builder](content-builder.md) and [Delivery API](delivery-api.md).

---

## 3. Internal IT / SRE service desk (ITIL)

**Who:** internal IT, platform and SRE teams running incident, request, problem and
change management on infrastructure they already operate.

**Why ArcHub:** a full **Service Desk** with a **Jira-style customizable workflow
engine** and a real **BPMN 2.0 engine** — model your process visually in the **offline
BPMN editor**, import/export BPMN XML losslessly, and start from **10 best-practice ITIL
schemes**. Add **Service Catalog**, **SLA** policies and a **CMDB** with impact/blast-radius
analysis. Runs on SQLite for a team, or **PostgreSQL** for many concurrent agents.

**How:**

```bash
# Team-scale: SQLite is enough.
uvicorn archub_cms.app:create_archub_app --factory --port 8088
# Scale-up: route ITSM to PostgreSQL.
export ARCHUB_ITSM_PG_DSN=postgresql://archub:archub@db:5432/archub_itsm
```

Surfaces: `/admin/itsm` (desk), `/admin/itsm/workflow` (visual editor),
`/api/platform/itsm/*` (REST). **Key capabilities:** workflow state machine · BPMN
engine · ITIL schemes · catalog/SLA/CMDB · ITIL RBAC. See [ITSM / ITIL](capabilities/itsm.md).

---

## 4. Embedded module inside an existing FastAPI product

**Who:** teams who already ship a FastAPI app and want to add docs, a help center, or a
support desk **without** standing up a second system.

**Why ArcHub:** it's a library, not a platform you migrate onto. Mount only the routers
you need; everything host-specific (auth, templates, cache, audit) is a **Protocol port**
you implement against your existing infrastructure.

**How:**

```python
from fastapi import FastAPI
from archub_cms.web.routes import router as archub_router
from archub_cms.web.platform_routes import platform_router
from archub_cms.web.itsm_routes import itsm_router

app = FastAPI()                     # your existing product
app.include_router(archub_router)   # + CMS & delivery
app.include_router(platform_router) # + knowledge/plugins API
app.include_router(itsm_router)     # + ITSM API (optional)
```

**Key capabilities:** router-level embedding · ports/adapters · plugin host · shared
auth boundary. See [Local Deployment → Embed](deployment/local.md#embed-in-another-fastapi-app).

---

## 5. Self-hosted Confluence / Wiki.js replacement

**Who:** engineering and ops orgs that want Confluence-class spaces and search **without**
per-seat licensing or a cloud tenancy.

**Why ArcHub:** spaces, page trees, labels, search, backlinks and a knowledge graph,
self-hosted under **Apache-2.0**. The PHP **Wiki plugin** demonstrates a Confluence-style
space/page/diagram module on the external runtime, and diagrams.net-compatible `.drawio`
storage covers architecture docs.

**Key capabilities:** knowledge base · FTS5 search · backlinks/graph · PHP wiki plugin ·
RBAC/public-access rules. See [PHP Wiki Plugin](plugins/archub-ru-wiki-php.md) and the
[Comparison](comparison.md).

---

## 6. White-label, plugin-extensible platform for ISVs

**Who:** ISVs and solution builders shipping a branded knowledge/content/ITSM product to
their own customers.

**Why ArcHub:** no per-seat license, no vendor tenancy, and a real **plugin runtime** —
extend with in-process Python *or* external HTTP/PHP modules across 25+ extension points,
package them through the **module marketplace** with signed bundles and capability
contracts, and gate everything via manifest permissions and the audited platform adapter.

**Key capabilities:** plugin host (in-process + external) · extension points · marketplace
packager · permission gating · self-describing capabilities. See
[Plugins & Extensibility](capabilities/plugins.md) and [Module Marketplace](architecture/module-marketplace.md).

---

## 7. Developer documentation / docs-as-code portal

**Who:** developer-experience teams publishing API docs and guides, with search and an
AI answer box, owned in-house.

**Why ArcHub:** structured content + delivery API + FTS5 search + agentic RAG answering,
all self-hosted. Editors work in the backoffice; the frontend consumes JSON; an answer
endpoint provides "ask the docs" with offline or online models.

**Key capabilities:** content model · delivery search · agentic answer · vault export ·
runtime/RAG export. See [Delivery API](delivery-api.md) and
[Enterprise Knowledge Platform](architecture/enterprise-knowledge-platform.md).

---

## 8. Personal / team productivity & GTD (OurLifeOrganized)

**Who:** teams wanting a task outliner with computed priority, contexts and recurrence —
a MyLifeOrganized-style GTD surface running inside the platform.

**Why ArcHub:** the **OurLifeOrganized** PHP plugin ports a GTD outliner (hierarchical
tasks, computed star priority from importance/urgency, GTD contexts, due/start dates,
RRULE recurrence, smart views and reports) onto the external runtime — a worked example
of a full application delivered as a plugin.

**Key capabilities:** external (PHP) plugin runtime · computed priority · recurrence
engine · smart views/reports. See [PHP OurLifeOrganized Plugin](plugins/archub-olo-php.md).

---

## Choosing a starting point

| If your priority is… | Start with | Then read |
|---|---|---|
| Self-hosted knowledge + AI search | Pillar 2 (Knowledge) | [Enterprise Knowledge Platform](architecture/enterprise-knowledge-platform.md) |
| Structured content for a frontend | Pillar 1 (CMS) | [Content Builder](content-builder.md), [Delivery API](delivery-api.md) |
| ITIL service desk | Pillar 3 (ITSM) | [ITSM / ITIL](capabilities/itsm.md) |
| Adding all three to your app | Embedding | [Local Deployment](deployment/local.md) |
| Comparing to what you have | — | [Comparison](comparison.md) |
