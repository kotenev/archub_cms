"""Inspect ArcHub core plugin Rust workspace coverage."""

from __future__ import annotations

__all__ = ["main"]

import argparse
import json
from typing import Any

from archub_cms.application.core_plugins import core_plugin_coverage
from archub_cms.application.plugins import ArcHubPluginRegistry


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="archub-core-plugins",
        description="Report Rust workspace coverage for ArcHub core plugins.",
    )
    parser.add_argument("--json", action="store_true", help="print the full coverage JSON")
    parser.add_argument(
        "--fail-on-missing",
        action="store_true",
        help="exit with status 1 when a core plugin lacks a crate or Rust declaration",
    )
    args = parser.parse_args(argv)

    coverage = core_plugin_coverage(ArcHubPluginRegistry(plugin_dirs=()).manifests())
    if args.json:
        print(json.dumps(coverage, indent=2, sort_keys=True))
    else:
        _print_summary(coverage)

    if args.fail_on_missing and (
        coverage["missing_total"] > 0 or coverage["undeclared_total"] > 0
    ):
        return 1
    return 0


def _print_summary(coverage: dict[str, Any]) -> None:
    print(
        "Core plugins: "
        f"{coverage['core_plugin_total']} total, "
        f"{coverage['covered_total']} crate-covered, "
        f"{coverage['declared_total']} Rust-declared"
    )
    print(
        "Rust workspace: "
        f"{coverage['workspace']['members_total']} crates, "
        f"{coverage['coverage_percent']}% coverage, "
        f"{coverage['contract_percent']}% contract"
    )
    if coverage["missing"]:
        print("Missing crates:")
        for item in coverage["missing"]:
            print(f"- {item['plugin_id']} -> {item['rust_crate']}")
    if coverage["undeclared"]:
        print("Undeclared plugin ids:")
        for item in coverage["undeclared"]:
            print(f"- {item['plugin_id']} -> {item['rust_crate']}")


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
