"""Standalone FastAPI web helpers for ArcHub CMS."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import parse_qs

from fastapi import Request
from fastapi.templating import Jinja2Templates

__all__ = ["CurrentUser", "current_user", "money", "parse_form", "templates"]

_TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"


@dataclass(frozen=True)
class CurrentUser:
    username: str = "admin"
    is_admin: bool = True


def _format_datetime(ts: float) -> str:
    try:
        return datetime.fromtimestamp(ts, UTC).strftime("%d.%m.%Y %H:%M")
    except Exception:
        return str(ts)


def _format_clock(ts: float) -> str:
    try:
        return datetime.fromtimestamp(ts, UTC).strftime("%H:%M")
    except Exception:
        return ""


def money(amount, currency: str = "tok.") -> str:
    try:
        return f"{int(amount):,}".replace(",", " ") + f" {currency}"
    except Exception:
        return f"{amount} {currency}"


def templates() -> Jinja2Templates:
    template_env = Jinja2Templates(directory=str(_TEMPLATES_DIR))
    template_env.env.filters["datetime"] = _format_datetime
    template_env.env.filters["clock"] = _format_clock
    template_env.env.filters["money"] = money
    return template_env


async def parse_form(request: Request) -> dict[str, str]:
    raw = await request.body()
    parsed = parse_qs(raw.decode("utf-8", errors="replace"), keep_blank_values=True)
    return {key: values[-1] for key, values in parsed.items()}


def current_user(request: Request) -> CurrentUser | None:
    user = getattr(request.state, "user", None)
    if user is not None:
        return user
    username = request.headers.get("X-ArcHub-User") or request.cookies.get("archub_user")
    if username:
        is_admin = (request.headers.get("X-ArcHub-Admin") or "1").strip() not in {"0", "false"}
        return CurrentUser(username=username, is_admin=is_admin)
    return CurrentUser()
