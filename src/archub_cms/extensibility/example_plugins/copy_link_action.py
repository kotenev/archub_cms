"""Example page action: copy to clipboard."""

from __future__ import annotations

from archub_cms.extensibility.extension_points import PageActionExt


class CopyLinkAction(PageActionExt):
    action_id = "copy_link"
    action_label = "Copy Link"
    icon = "🔗"

    def is_available(self, page_context: dict) -> bool:
        return bool(page_context.get("route_path"))

    def execute(self, page_context: dict) -> dict:
        route_path = page_context.get("route_path", "")
        return {
            "action": "copy_to_clipboard",
            "value": route_path,
            "message": "Link copied to clipboard",
        }
