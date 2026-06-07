"""Example security policy plugin demonstrating SecurityPolicyExt."""

from __future__ import annotations

from typing import Any

from archub_cms.extensibility.extension_points import SecurityPolicyExt


class PiiDetectionPlugin:
    """A simple PII-detection security policy plugin."""

    def setup(self, context: Any) -> None:
        context.register(PiiDetectionPolicy())


_PII_PATTERNS = ("@example.com", "password=", "secret=", "api_key=", "token=")


class PiiDetectionPolicy(SecurityPolicyExt):
    policy_name = "pii-detection"

    def check_publish(self, content: dict[str, Any]) -> tuple[bool, str]:
        body = str(content.get("body", "")) + str(content.get("summary", ""))
        for pattern in _PII_PATTERNS:
            if pattern in body.casefold():
                return False, f"potential PII detected: {pattern}"
        return True, ""

    def check_access(self, user: Any, content: dict[str, Any]) -> tuple[bool, str]:
        return True, ""
