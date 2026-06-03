# Media & DAM

ArcHub now has a dedicated media application boundary:
`archub_cms.application.media.ArcHubMediaService`. It is intentionally a
metadata/DAM layer over existing registered media references, not a file-storage
provider. Hosts can keep using local files, object storage, CDN URLs, or an
external DAM while ArcHub tracks policy and content usage.

## Responsibilities

| Capability | Implementation |
|---|---|
| Allowed content types | `MediaPolicy.allowed_content_types` from settings or explicit test policy. |
| Image accessibility | Images require alt text by default. |
| Folder reports | Assets are grouped by normalized folder and content type. |
| Duplicate detection | Assets are grouped by metadata hash when present, otherwise by original filename and content type. |
| Usage reports | Draft and published content payloads are scanned for asset ID, URL, or filename references. |
| Orphan detection | Assets with no content usage are surfaced as cleanup candidates. |

## Configuration

| Variable | Purpose |
|---|---|
| `ARCHUB_ALLOWED_MEDIA_CONTENT_TYPES` | Comma-separated MIME allowlist. Supports wildcard groups such as `image/*`. |

Default allowed types include common images, MP4, MP3, PDF, text, Markdown, and
JSON. Production hosts should tighten this list to match their upload provider,
virus scanning, CDN, and compliance policies.

## Admin API

`GET /admin/archub/media.json` keeps the existing route but now returns a richer
report:

```json
{
  "assets": [],
  "total": 0,
  "folders": [],
  "duplicates": [],
  "orphaned_assets": [],
  "policy": {
    "allowed_content_types": ["image/jpeg"],
    "require_alt_text_for_images": true
  }
}
```

Each asset includes `usage`, `usage_count`, and `orphaned` fields.

## Cleanup Workflow

ArcHub deliberately reports orphaned and duplicate assets without deleting them.
Modern CMS/DAM systems make cleanup explicit because assets may be used by
external channels, unpublished campaigns, or hard-coded frontend integrations.
Future cleanup commands should require confirmation and emit domain events such
as `media.orphaned.detected`, `media.duplicate.detected`, and `media.purged`.

## PlantUML

```bash
plantuml -tsvg docs/diagrams/plantuml/media-library-service.puml
plantuml -tsvg docs/diagrams/plantuml/media-usage-report.puml
```

## References

- Local source: `books/umbraco_cms.pdf`, chapters 13-14.
- [Umbraco Media Management](https://docs.umbraco.com/umbraco-cms/tutorials/editors-manual/media-management)
- [Umbraco Media Picker](https://docs.umbraco.com/umbraco-cms/13.latest/fundamentals/backoffice/property-editors/built-in-umbraco-property-editors/media-picker-3)
- [Strapi Media Library](https://docs.strapi.io/cms/features/media-library)
- [Contentful media](https://www.contentful.com/help/media/)
- [Sanity assets](https://www.sanity.io/docs/content-lake/assets)
