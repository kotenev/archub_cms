"""Mediator pattern: decouple command/query dispatch from handlers.

A thin in-process dispatcher that routes ``Command`` and ``Query`` objects to
their registered handlers, keeping the sender unaware of *who* handles the
request or *how*. This is the CQRS wire-up: commands mutate state, queries
return projections, and the mediator sits in between so application services
only depend on the message protocol.
"""

from __future__ import annotations

__all__ = [
    "Command",
    "CommandHandler",
    "Mediator",
    "Query",
    "QueryHandler",
    "get_mediator",
]

from collections.abc import Callable
from typing import Any, Protocol, TypeVar, runtime_checkable

TResult = TypeVar("TResult")


@runtime_checkable
class Command(Protocol):
    """Marker protocol for write-side requests."""


@runtime_checkable
class Query(Protocol):
    """Marker protocol for read-side requests."""


CommandHandler = Callable[[Any], Any]
QueryHandler = Callable[[Any], Any]


class Mediator:
    """In-process CQRS dispatcher.

    Registers handlers by message type and dispatches synchronously.
    Supports middleware pipeline for cross-cutting concerns (logging,
    validation, metrics) around each dispatch.
    """

    def __init__(self) -> None:
        self._command_handlers: dict[type, CommandHandler] = {}
        self._query_handlers: dict[type, QueryHandler] = {}
        self._middleware: list[Callable[[Any, Callable[[], Any]], Any]] = []

    def register_command(self, command_type: type, handler: CommandHandler) -> None:
        self._command_handlers[command_type] = handler

    def register_query(self, query_type: type, handler: QueryHandler) -> None:
        self._query_handlers[query_type] = handler

    def add_middleware(self, mw: Callable[[Any, Callable[[], Any]], Any]) -> None:
        self._middleware.append(mw)

    def send(self, command: Command) -> Any:
        handler = self._command_handlers.get(type(command))
        if handler is None:
            raise LookupError(f"no handler registered for command {type(command).__name__}")

        def execute() -> Any:
            return handler(command)

        return self._pipeline(command, execute)

    def query(self, query: Query) -> Any:
        handler = self._query_handlers.get(type(query))
        if handler is None:
            raise LookupError(f"no handler registered for query {type(query).__name__}")

        def execute() -> Any:
            return handler(query)

        return self._pipeline(query, execute)

    def _pipeline(self, message: Any, core: Callable[[], Any]) -> Any:
        if not self._middleware:
            return core()

        def wrap(msg: Any, fn: Callable[[], Any]) -> Any:
            return fn

        result_fn: Callable[[], Any] = core
        for mw in reversed(self._middleware):
            prev = result_fn

            def _make_chain(
                m: Any = message, p: Callable[[], Any] = prev, middleware: Any = mw
            ) -> Any:
                return middleware(m, p)

            result_fn = _make_chain
        return result_fn()

    def handler_count(self) -> dict[str, int]:
        return {
            "commands": len(self._command_handlers),
            "queries": len(self._query_handlers),
            "middleware": len(self._middleware),
        }


_DEFAULT_MEDIATOR: Mediator | None = None


def get_mediator() -> Mediator:
    global _DEFAULT_MEDIATOR
    if _DEFAULT_MEDIATOR is None:
        _DEFAULT_MEDIATOR = Mediator()
    assert _DEFAULT_MEDIATOR is not None
    return _DEFAULT_MEDIATOR
