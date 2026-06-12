"""Example connector plugin: Slack integration for notifications."""

from __future__ import annotations

from archub_cms.extensibility.extension_points import ConnectorExt


class SlackConnectorPlugin(ConnectorExt):
    connector_id = "slack"
    target_system = "slack"

    def sync_pull(self, config: dict) -> list[dict]:
        return []

    def sync_push(self, items: list[dict]) -> int:
        return len(items)
