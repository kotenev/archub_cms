# Governance & Access

ArcHub governance now has a dedicated application boundary:
`archub_cms.application.governance.ArcHubGovernanceService`. It centralizes
editor permissions, content-scoped actions, public delivery policies, and
member-gated access checks while keeping the existing admin routes stable.

## Responsibilities

| Capability | Implementation |
|---|---|
| Editor permissions | `grant_permission()`, `revoke_permission()`, and `permissions_report()`. |
| Route authorization | `_guard()` and `_can()` call `ArcHubGovernanceService` instead of the store. |
| Public access | `set_public_access_rule()`, `remove_public_access_rule()`, and `public_access_rule()`. |
| Delivery protection | Public HTML and API delivery call `can_access_public_content()`. |
| Events | Permission and access changes emit governance domain events. |

## Policy Model

Editor permissions are action scoped: `browse`, `create`, `update`, `publish`,
`delete`, `workflow`, `model`, `media`, `settings`, and `admin`. A rule can be
global or scoped to a content node with optional descendant inheritance.

Public access policies are intentionally small:

- `public`: anonymous visitors can read content.
- `authenticated`: any logged-in member can read content.
- `members`: logged-in members must match at least one configured group.

This keeps the standalone package predictable while leaving enterprise identity,
SSO, teams, and external policy engines behind host-provided auth ports.

## Admin API Boundary

The permissions and access routes now call `ArcHubGovernanceService`:

- `GET /admin/archub/permissions.json`
- `POST /admin/archub/permissions`
- `POST /admin/archub/permissions/{rule_id}/delete`
- `GET /admin/archub/access.json`
- `GET|POST /admin/archub/content/{node_id}/access`
- `POST /admin/archub/content/{node_id}/access/delete`

## PlantUML

```bash
plantuml -tsvg docs/diagrams/plantuml/governance-service.puml
plantuml -tsvg docs/diagrams/plantuml/public-access-flow.puml
```

## References

- Local source: `books/umbraco_cms.pdf`, chapters 13-14.
- [Umbraco Security](https://docs.umbraco.com/umbraco-cms/reference/security)
- [Umbraco Members](https://docs.umbraco.com/umbraco-cms/fundamentals/data/members/)
- [Contentful roles](https://www.contentful.com/help/roles/)
- [Contentful content permissions](https://www.contentful.com/help/content-permissions/)
- [Sanity roles](https://www.sanity.io/docs/user-guides/roles)
- [Strapi custom roles and permissions](https://strapi.io/features/custom-roles-and-permissions)
