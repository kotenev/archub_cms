# ArcHub SDK Release

This directory contains the ArcHub Platform SDK 1.0.0 release artifacts.

## Contents

- `python/` - dependency-free Python client package `archub-platform-sdk`.
- `openapi/archub-platform-sdk.openapi.yaml` - SDK-facing OpenAPI 3.1 subset.
- `release/archub-sdk-1.0.0.json` - machine-readable release manifest.

## Validate

```bash
python -m archub_cms.tools.sdk_release --json
pytest tests/test_platform_sdk_release.py -q
```

## Install Python SDK

```bash
python -m pip install ./sdk/python
```
