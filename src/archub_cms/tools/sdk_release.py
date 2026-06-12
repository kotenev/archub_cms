"""Print ArcHub Platform SDK release metadata."""

from __future__ import annotations

__all__ = ["main"]

import argparse
import json

from archub_cms.application.sdk_release import sdk_release_manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="archub-sdk-release",
        description="Print ArcHub Platform SDK release metadata.",
    )
    parser.add_argument("--json", action="store_true", help="print full release JSON")
    args = parser.parse_args(argv)

    manifest = sdk_release_manifest()
    if args.json:
        print(json.dumps(manifest, indent=2, sort_keys=True))
    else:
        print(f"{manifest['name']} {manifest['version']} ({manifest['status']})")
        print(f"Package: {manifest['package']}")
        print("API groups: " + ", ".join(manifest["api_groups"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
