"""Serialize a workflow scheme to BPMN 2.0 XML and to a Mermaid state diagram.

The BPMN export is layout-complete: it emits a ``<bpmndi:BPMNDiagram>`` with shape
bounds and edge waypoints computed by a simple BFS layering, so the result renders
directly in bpmn.io / Camunda Modeler without a manual layout pass. The Mermaid
export targets ArcHub's existing inline Mermaid rendering for knowledge pages.
"""

from __future__ import annotations

__all__ = ["to_bpmn_xml", "to_mermaid"]

from collections import deque
from xml.sax.saxutils import escape, quoteattr

from archub_cms.extensibility.example_plugins.itsm.workflow import (
    StatusCategory,
    WorkflowScheme,
    resolved_edges,
)

# Layout constants (BPMN diagram interchange coordinates, in pixels).
_COL_WIDTH = 200
_ROW_HEIGHT = 120
_TASK_W = 120
_TASK_H = 80
_EVENT_SIZE = 36
_ORIGIN_X = 80
_ORIGIN_Y = 80


def _layers(scheme: WorkflowScheme) -> dict[str, int]:
    """Assign each status a horizontal layer via BFS from the initial status."""

    layer: dict[str, int] = {}
    if not scheme.initial_status_id:
        # No initial status: fall back to declaration order on a single row.
        return {status_id: index for index, status_id in enumerate(scheme.statuses)}
    layer[scheme.initial_status_id] = 0
    queue: deque[str] = deque([scheme.initial_status_id])
    adjacency: dict[str, list[str]] = {status_id: [] for status_id in scheme.statuses}
    for origin, _transition, target in resolved_edges(scheme):
        adjacency[origin].append(target)
    while queue:
        current = queue.popleft()
        for target in adjacency.get(current, ()):
            if target not in layer:
                layer[target] = layer[current] + 1
                queue.append(target)
    # Any status not reached keeps to the last column so it still gets a position.
    fallback = max(layer.values(), default=0) + 1
    for status_id in scheme.statuses:
        layer.setdefault(status_id, fallback)
    return layer


def _positions(scheme: WorkflowScheme) -> dict[str, tuple[int, int]]:
    """Map every status id to an ``(x, y)`` shape origin, stacking ties vertically."""

    layers = _layers(scheme)
    by_layer: dict[int, list[str]] = {}
    for status_id, column in sorted(layers.items(), key=lambda kv: (kv[1], kv[0])):
        by_layer.setdefault(column, []).append(status_id)
    positions: dict[str, tuple[int, int]] = {}
    for column, status_ids in by_layer.items():
        for row, status_id in enumerate(status_ids):
            x = _ORIGIN_X + column * _COL_WIDTH
            y = _ORIGIN_Y + row * _ROW_HEIGHT
            positions[status_id] = (x, y)
    return positions


def to_mermaid(scheme: WorkflowScheme) -> str:
    """Render the scheme as a Mermaid ``stateDiagram-v2`` for inline knowledge pages."""

    lines = ["stateDiagram-v2", f"  %% {scheme.name}"]
    alias: dict[str, str] = {}
    for status in scheme.statuses.values():
        alias[status.id] = status.id
        lines.append(f'  state "{status.name}" as {status.id}')
    if scheme.initial_status_id:
        lines.append(f"  [*] --> {scheme.initial_status_id}")
    for transition in scheme.transitions.values():
        label = transition.name + (" *" if transition.is_global else "")
        origins = (
            transition.from_statuses
            if transition.from_statuses
            else tuple(s for s in scheme.statuses if s != transition.to_status)
        )
        for origin in origins:
            if origin in alias and transition.to_status in alias:
                lines.append(f"  {origin} --> {transition.to_status}: {label}")
    for status in scheme.statuses.values():
        if status.category is StatusCategory.DONE:
            lines.append(f"  {status.id} --> [*]")
    return "\n".join(lines)


def _shape_xml(element_id: str, x: int, y: int, w: int, h: int) -> str:
    return (
        f"      <bpmndi:BPMNShape id={quoteattr(element_id + '_di')} "
        f"bpmnElement={quoteattr(element_id)}>\n"
        f'        <dc:Bounds x="{x}" y="{y}" width="{w}" height="{h}" />\n'
        f"      </bpmndi:BPMNShape>"
    )


def _edge_xml(
    flow_id: str, source: tuple[int, int, int, int], target: tuple[int, int, int, int]
) -> str:
    sx = source[0] + source[2]
    sy = source[1] + source[3] // 2
    tx = target[0]
    ty = target[1] + target[3] // 2
    return (
        f"      <bpmndi:BPMNEdge id={quoteattr(flow_id + '_di')} "
        f"bpmnElement={quoteattr(flow_id)}>\n"
        f'        <di:waypoint x="{sx}" y="{sy}" />\n'
        f'        <di:waypoint x="{tx}" y="{ty}" />\n'
        f"      </bpmndi:BPMNEdge>"
    )


def to_bpmn_xml(scheme: WorkflowScheme) -> str:
    """Serialize the scheme to a layout-complete BPMN 2.0 XML document.

    Statuses become user tasks, transitions become sequence flows. A start event
    feeds the initial status; every Done status without an outgoing transition gets
    its own end event so the process is properly bounded.
    """

    process_id = f"itsm_{scheme.key}"
    positions = _positions(scheme)
    bounds: dict[str, tuple[int, int, int, int]] = {}

    flow_elements: list[str] = []
    shapes: list[str] = []
    edges: list[str] = []
    flow_counter = 0

    # Start event, placed just left of the initial status.
    start_id = f"{process_id}_start"
    if scheme.initial_status_id and scheme.initial_status_id in positions:
        ix, iy = positions[scheme.initial_status_id]
        sx = ix - _COL_WIDTH + (_TASK_W - _EVENT_SIZE)
        sy = iy + (_TASK_H - _EVENT_SIZE) // 2
    else:
        sx, sy = _ORIGIN_X - _COL_WIDTH, _ORIGIN_Y
    bounds[start_id] = (sx, sy, _EVENT_SIZE, _EVENT_SIZE)
    flow_elements.append(f'    <bpmn:startEvent id={quoteattr(start_id)} name="Created" />')
    shapes.append(_shape_xml(start_id, sx, sy, _EVENT_SIZE, _EVENT_SIZE))

    # One user task per status.
    for status in scheme.statuses.values():
        x, y = positions[status.id]
        bounds[status.id] = (x, y, _TASK_W, _TASK_H)
        flow_elements.append(
            f"    <bpmn:userTask id={quoteattr(status.id)} name={quoteattr(status.name)} />"
        )
        shapes.append(_shape_xml(status.id, x, y, _TASK_W, _TASK_H))

    def _next_flow(name: str, source: str, target: str) -> None:
        nonlocal flow_counter
        flow_counter += 1
        flow_id = f"{process_id}_flow_{flow_counter}"
        flow_elements.append(
            f"    <bpmn:sequenceFlow id={quoteattr(flow_id)} name={quoteattr(name)} "
            f"sourceRef={quoteattr(source)} targetRef={quoteattr(target)} />"
        )
        edges.append(_edge_xml(flow_id, bounds[source], bounds[target]))

    # Start -> initial status.
    if scheme.initial_status_id and scheme.initial_status_id in scheme.statuses:
        _next_flow("Create", start_id, scheme.initial_status_id)

    # Transitions -> sequence flows (global transitions expanded to explicit edges).
    for origin, transition, target in resolved_edges(scheme):
        _next_flow(transition.name, origin, target)

    # End events for Done statuses that have no outgoing transitions.
    outgoing = {origin for origin, _t, _to in resolved_edges(scheme)}
    end_counter = 0
    for status in scheme.statuses.values():
        if status.category is StatusCategory.DONE and status.id not in outgoing:
            end_counter += 1
            end_id = f"{process_id}_end_{end_counter}"
            x, y = positions[status.id]
            ex = x + _COL_WIDTH
            ey = y + (_TASK_H - _EVENT_SIZE) // 2
            bounds[end_id] = (ex, ey, _EVENT_SIZE, _EVENT_SIZE)
            flow_elements.append(f'    <bpmn:endEvent id={quoteattr(end_id)} name="Closed" />')
            shapes.append(_shape_xml(end_id, ex, ey, _EVENT_SIZE, _EVENT_SIZE))
            _next_flow("Done", status.id, end_id)

    documentation = f"    <bpmn:documentation>{escape(scheme.name)}</bpmn:documentation>"
    body = "\n".join([documentation, *flow_elements])
    diagram = "\n".join([*shapes, *edges])

    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<bpmn:definitions "
        'xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" '
        'xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI" '
        'xmlns:dc="http://www.omg.org/spec/DD/20100524/DC" '
        'xmlns:di="http://www.omg.org/spec/DD/20100524/DI" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
        f"id={quoteattr('defs_' + process_id)} "
        'targetNamespace="http://archub.dev/itsm/bpmn">\n'
        f"  <bpmn:process id={quoteattr(process_id)} "
        f'name={quoteattr(scheme.name)} isExecutable="false">\n'
        f"{body}\n"
        "  </bpmn:process>\n"
        '  <bpmndi:BPMNDiagram id="diagram">\n'
        f'    <bpmndi:BPMNPlane id="plane" bpmnElement={quoteattr(process_id)}>\n'
        f"{diagram}\n"
        "    </bpmndi:BPMNPlane>\n"
        "  </bpmndi:BPMNDiagram>\n"
        "</bpmn:definitions>\n"
    )
