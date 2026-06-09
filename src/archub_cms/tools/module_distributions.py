"""Build local marketplace repositories from ArcHub platform modules."""

from __future__ import annotations

__all__ = ["build_marketplace", "main"]

import argparse
import json
from dataclasses import replace as dataclass_replace
from pathlib import Path
from typing import Any

from archub_cms.application.plugin_management_service import (
    get_archub_plugin_management_service,
)
from archub_cms.settings import ArcHubSettings


def build_marketplace(
    *,
    output_root: Path | str,
    plugin_dirs: tuple[Path | str, ...] | None = None,
    include_builtins: bool = True,
    include_plugins: bool = True,
    replace: bool = True,
) -> dict[str, Any]:
    settings = ArcHubSettings.from_env()
    if plugin_dirs is not None:
        settings = dataclass_replace(
            settings,
            plugin_dirs=tuple(Path(item) for item in plugin_dirs),
        )
    return get_archub_plugin_management_service(settings=settings).build_marketplace(
        output_root,
        include_builtins=include_builtins,
        include_plugins=include_plugins,
        replace=replace,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="archub-marketplace-build",
        description="Build a local ArcHub marketplace catalog with module archives.",
    )
    parser.add_argument(
        "--output",
        default="dist/archub-marketplace",
        help="Target marketplace directory.",
    )
    parser.add_argument(
        "--plugin-dir",
        action="append",
        default=None,
        help="Plugin/module source directory. Can be passed multiple times.",
    )
    parser.add_argument("--no-builtins", action="store_true", help="Skip built-in platform modules.")
    parser.add_argument("--no-plugins", action="store_true", help="Skip filesystem plugins.")
    parser.add_argument("--no-replace", action="store_true", help="Fail if an archive already exists.")
    parser.add_argument("--json", action="store_true", help="Print full JSON result.")
    args = parser.parse_args(argv)

    result = build_marketplace(
        output_root=args.output,
        plugin_dirs=tuple(args.plugin_dir) if args.plugin_dir is not None else None,
        include_builtins=not args.no_builtins,
        include_plugins=not args.no_plugins,
        replace=not args.no_replace,
    )
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"Built {result['total']} module distributions")
        print(f"Marketplace index: {result['index']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
