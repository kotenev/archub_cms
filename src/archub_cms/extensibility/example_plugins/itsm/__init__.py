"""ITSM Service Desk: a Jira-style customizable workflow engine with BPMN export.

This package is a self-contained, executable ArcHub plugin that turns the platform
into an IT Service Management (ITSM) Service Desk for a cloud provider:

* :mod:`workflow` — a customizable status/transition workflow engine modelled on
  Jira workflow schemes (statuses with categories, guarded transitions, global
  "from-any" transitions, conditions and post-functions).
* :mod:`bpmn` — serialize any workflow scheme to BPMN 2.0 XML (for bpmn.io) and to
  Mermaid state diagrams (for inline rendering inside ArcHub knowledge pages).
* :mod:`request` — the Service Desk domain in ITIL terms: requests (incident /
  service request / problem / change), priorities, SLA policies and cloud context.
* :mod:`repository` — request repository port and in-memory storage for tests.
* :mod:`rbac` — ITIL-aligned platform roles and ITSM route permissions.
* :mod:`service_desk` — the :class:`ServiceDesk` application facade that binds the
  workflow engine to the request repository and ships default cloud-provider schemes.
* :mod:`plugin` — the plugin entrypoint and the extension implementations it
  registers (workflow action, BPMN macro, dashboard widget, page action, cloud
  connector and an offline triage LLM tool).
"""

from __future__ import annotations

from archub_cms.extensibility.example_plugins.itsm.bpmn import (
    from_bpmn_xml,
    to_bpmn_xml,
    to_mermaid,
)
from archub_cms.extensibility.example_plugins.itsm.catalog import (
    CatalogService,
    ServiceCatalog,
    ServiceLifecycle,
)
from archub_cms.extensibility.example_plugins.itsm.cmdb import (
    CIRelationship,
    CIStatus,
    CIType,
    Cmdb,
    ConfigurationItem,
    RelationshipType,
)
from archub_cms.extensibility.example_plugins.itsm.documents import (
    DocumentRepository,
    InMemoryDocumentRepository,
)
from archub_cms.extensibility.example_plugins.itsm.itsm_service import (
    ItsmService,
    SchemeValidationError,
)
from archub_cms.extensibility.example_plugins.itsm.rbac import (
    ITILRole,
    ITSMPermission,
    actor_role_for_groups,
    has_itsm_permission,
    itil_role_report,
    permissions_for_groups,
    roles_for_groups,
)
from archub_cms.extensibility.example_plugins.itsm.repository import (
    InMemoryRequestRepository,
    RequestRepository,
)
from archub_cms.extensibility.example_plugins.itsm.request import (
    CloudResource,
    Priority,
    Request,
    RequestType,
    SlaPolicy,
)
from archub_cms.extensibility.example_plugins.itsm.service_desk import ServiceDesk
from archub_cms.extensibility.example_plugins.itsm.sla import SlaDefinition, SlaRegistry
from archub_cms.extensibility.example_plugins.itsm.workflow import (
    StatusCategory,
    WorkflowError,
    WorkflowScheme,
    WorkflowStatus,
    WorkflowTransition,
    register_condition,
)

__all__ = [
    "CIRelationship",
    "CIStatus",
    "CIType",
    "CatalogService",
    "CloudResource",
    "Cmdb",
    "ConfigurationItem",
    "DocumentRepository",
    "ITILRole",
    "ITSMPermission",
    "InMemoryDocumentRepository",
    "InMemoryRequestRepository",
    "ItsmService",
    "Priority",
    "RelationshipType",
    "Request",
    "RequestRepository",
    "RequestType",
    "SchemeValidationError",
    "ServiceCatalog",
    "ServiceDesk",
    "ServiceLifecycle",
    "SlaDefinition",
    "SlaPolicy",
    "SlaRegistry",
    "StatusCategory",
    "WorkflowError",
    "WorkflowScheme",
    "WorkflowStatus",
    "WorkflowTransition",
    "actor_role_for_groups",
    "from_bpmn_xml",
    "has_itsm_permission",
    "itil_role_report",
    "permissions_for_groups",
    "register_condition",
    "roles_for_groups",
    "to_bpmn_xml",
    "to_mermaid",
]
