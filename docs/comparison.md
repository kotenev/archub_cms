# Platform Comparison

ArcHub overlaps with three different product categories — knowledge bases, headless
CMSs, and ITSM suites — because it ships all three on one core. This page compares it
honestly with the well-known tools in each category, including where ArcHub is **not**
the right choice.

!!! note "How to read this"
    ArcHub's distinguishing trait is **consolidation + self-hosting + offline AI** in one
    Apache-2.0 Python package. It is not trying to out-polish a category leader's editor
    UI or mobile apps. Weigh breadth and control against the depth and ecosystem of a
    focused product.

---

## Positioning in one line

| Product | Category | Model |
|---|---|---|
| **ArcHub** | Knowledge + CMS + ITSM | Self-hosted Apache-2.0 Python library |
| Confluence | Knowledge / wiki | SaaS or Data Center (paid) |
| Notion | Knowledge / docs | SaaS (paid) |
| Wiki.js | Knowledge / wiki | Self-hosted OSS (Node.js) |
| Obsidian | Personal knowledge / notes | Local app (proprietary) |
| Strapi | Headless CMS | Self-hosted OSS (Node.js) |
| Contentful | Headless CMS | SaaS (paid) |
| ServiceNow | ITSM / ITIL | Enterprise SaaS (paid) |
| Jira Service Management | ITSM | SaaS or Data Center (paid) |

---

## Knowledge base / wiki

| Feature | ArcHub | Confluence | Notion | Wiki.js | Obsidian |
|---|:--:|:--:|:--:|:--:|:--:|
| Self-hosted | ✅ | DC only | ❌ | ✅ | local only |
| Open-source license | ✅ Apache-2.0 | ❌ | ❌ | ✅ AGPL | ❌ |
| Spaces / page tree | ✅ | ✅ | ✅ | ✅ | vault |
| Full-text search | ✅ FTS5/BM25 | ✅ | ✅ | ✅ | ✅ |
| Semantic / hybrid search | ✅ | partial | partial | ❌ | plugin |
| Backlinks & graph | ✅ | partial | ✅ | ❌ | ✅ |
| **Offline AI answers (no cloud)** | ✅ | ❌ | ❌ | ❌ | plugin/BYO |
| Online LLM (optional) | ✅ + breaker | ✅ Atlassian | ✅ Notion AI | ❌ | plugin |
| Rich WYSIWYG editor | basic | ✅✅ | ✅✅ | ✅ | ✅ (md) |
| Real-time co-editing | via plugin | ✅ | ✅ | partial | ❌ |
| Per-seat pricing | **none** | yes | yes | none | yes (sync) |

**Takeaway:** ArcHub matches the *retrieval* side (search, backlinks, graph) and uniquely
offers **offline AI answers with zero data egress**. Confluence/Notion win on
**editor polish and real-time collaboration**; ArcHub wins on **control, licensing and
air-gapped AI**.

---

## Headless CMS

| Feature | ArcHub | Strapi | Contentful | Umbraco Heartcore |
|---|:--:|:--:|:--:|:--:|
| Self-hosted | ✅ | ✅ | ❌ SaaS | ❌ SaaS |
| Open-source license | ✅ Apache-2.0 | ✅ (partly) | ❌ | ❌ |
| Document/content types | ✅ | ✅ | ✅ | ✅ |
| Reusable data types | ✅ | ✅ | ✅ | ✅ |
| Block/component builder | ✅ | ✅ | ✅ | ✅ |
| Versioning & preview | ✅ | partial | ✅ | ✅ |
| Domains / cultures / variants | ✅ | i18n plugin | ✅ | ✅ |
| Delivery (content) API | ✅ JSON | ✅ REST/GraphQL | ✅ | ✅ |
| RSS / sitemap built-in | ✅ | plugin | ❌ | partial |
| GraphQL | ❌ (REST/JSON) | ✅ | ✅ | ❌ |
| Admin UI maturity | basic | ✅✅ | ✅✅ | ✅✅ |
| Language / runtime | Python | Node.js | — | .NET |

**Takeaway:** ArcHub gives a credible **content model + delivery API in Python** that
embeds into a FastAPI app. Strapi/Contentful win on **admin UX and GraphQL**; ArcHub wins
when you want the CMS to be **one router in your existing Python service** rather than a
separate Node/SaaS system — and to share auth and storage with knowledge + ITSM.

---

## ITSM / ITIL

| Feature | ArcHub | ServiceNow | Jira Service Management |
|---|:--:|:--:|:--:|
| Self-hosted | ✅ | ❌ | DC only |
| Open-source license | ✅ Apache-2.0 | ❌ | ❌ |
| Incident / request / problem / change | ✅ | ✅ | ✅ |
| Customizable workflow engine | ✅ Jira-style | ✅✅ | ✅ |
| **BPMN 2.0 engine + visual editor** | ✅ offline | ✅ (Flow) | partial |
| Best-practice ITIL schemes | ✅ 10 | ✅✅ | ✅ |
| Service Catalog | ✅ | ✅✅ | ✅ |
| SLA management | ✅ | ✅✅ | ✅ |
| CMDB + impact analysis | ✅ | ✅✅ | partial |
| ITIL RBAC roles | ✅ | ✅ | ✅ |
| SQLite **or** PostgreSQL | ✅ | ❌ | ❌ |
| Ecosystem / marketplace depth | small | ✅✅✅ | ✅✅ |
| Per-seat / per-agent pricing | **none** | high | yes |

**Takeaway:** ArcHub delivers the **core ITIL practices + a real BPMN engine** with no
licensing and full self-hosting. ServiceNow/JSM win decisively on **breadth, ecosystem,
integrations and enterprise scale**; ArcHub wins for **teams that want an ITIL desk on
their own infra without an enterprise contract**, or to embed ticketing into an existing
product.

---

## What makes ArcHub different

1. **Three products, one artifact.** Knowledge + CMS + ITSM share a data model, auth
   boundary, plugin runtime and deployment. No glue between three vendors.
2. **Offline-first AI.** Hybrid search and RAG-style answers run with **no network and no
   API keys**; online LLMs are an optional upgrade with a circuit breaker.
3. **Embeddable library, not a platform you migrate to.** Mount routers into an existing
   FastAPI app; implement host concerns as Protocol ports.
4. **Apache-2.0, no per-seat pricing.** Self-host on a laptop or a cluster; the cost is
   infrastructure, not licenses.
5. **Genuinely extensible.** In-process Python *and* external HTTP/PHP plugins over 25+
   extension points, with a marketplace packager and permission gating.

## When to choose ArcHub

- You need **self-hosted** knowledge/content/ITSM with **no data egress** (air-gapped,
  regulated, on-prem).
- You want to **consolidate** three tools onto one stack and one auth model.
- You're a **Python/FastAPI shop** and want these capabilities as library routers.
- You want **offline AI** over your own content, optionally upgradable to an on-prem LLM.
- You're an **ISV** building a white-label, plugin-extensible product without per-seat
  licensing.

## When **not** to choose ArcHub

- You need a **best-in-class WYSIWYG editor** and real-time co-authoring today →
  Confluence / Notion.
- You need **GraphQL** and a mature content-admin UX → Strapi / Contentful.
- You need **enterprise ITSM breadth** — large integration catalog, discovery, ITOM,
  global scale, vendor SLAs → ServiceNow / Jira Service Management.
- You want a **fully managed SaaS** with zero ops → any of the hosted options above.

See the [Capability catalog](capabilities/index.md) for the full ArcHub feature list and
[Use Cases](use-cases.md) for the scenarios it's designed around.
