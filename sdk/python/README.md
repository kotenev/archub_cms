# ArcHub Platform SDK for Python

Typed, dependency-free Python SDK for ArcHub platform APIs, plugin manifests,
marketplace modules and delivery endpoints.

## Install from source

```bash
python -m pip install ./sdk/python
```

## Usage

```python
from archub_platform_sdk import ArcHubClient, PluginManifest

client = ArcHubClient("http://127.0.0.1:8088")
print(client.capabilities()["product"])

manifest = PluginManifest(
    plugin_id="acme.wiki.bridge",
    name="Acme Wiki Bridge",
    version="1.0.0",
    capability="connector",
    runtime="external",
    entrypoint="https://wiki.example.test/api/arc-tool",
)
print(manifest.to_json())
```

## Covered API Groups

- Platform capabilities, route index and health-style read models.
- Core plugin and Rust workspace coverage.
- Plugin and module management catalogs.
- Marketplace repository inspection and module installation.
- Published delivery API: tree, content, search, tags, feeds.
- Knowledge API: search, graph, tools and grounded answers.
- Runtime export/status/search endpoints.
