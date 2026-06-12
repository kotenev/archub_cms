//! Governance, RBAC and compliance core plugin contracts for ArcHub.

use archub_core::{CorePlugin, CorePluginManifest};

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum GovernanceRole {
    Reader,
    Contributor,
    Editor,
    Publisher,
    Administrator,
    ServiceManager,
    ChangeManager,
    ComplianceAuditor,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Permission {
    Read,
    Create,
    Update,
    Publish,
    Administer,
    Audit,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RbacPolicy {
    pub role: GovernanceRole,
    pub grants: Vec<Permission>,
}

impl RbacPolicy {
    pub fn allows(&self, permission: Permission) -> bool {
        self.grants.contains(&permission)
    }
}

#[derive(Debug, Default)]
pub struct GovernanceRbacPlugin;

impl CorePlugin for GovernanceRbacPlugin {
    fn manifest(&self) -> CorePluginManifest {
        CorePluginManifest {
            id: "archub.governance.rbac",
            name: "Governance RBAC",
            version: "1.0.0",
            capability: "governance",
            provides: &["governance.rbac", "governance.itil_roles"],
        }
    }
}

#[derive(Debug, Default)]
pub struct AuditTrailPlugin;

impl CorePlugin for AuditTrailPlugin {
    fn manifest(&self) -> CorePluginManifest {
        CorePluginManifest {
            id: "archub.compliance.audit",
            name: "Audit Trail",
            version: "1.0.0",
            capability: "compliance",
            provides: &["audit.trail", "audit.immutable_log"],
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use archub_core::CorePlugin;

    #[test]
    fn rbac_policy_checks_grants() {
        let policy = RbacPolicy {
            role: GovernanceRole::Publisher,
            grants: vec![Permission::Read, Permission::Publish],
        };
        assert!(policy.allows(Permission::Publish));
        assert!(!policy.allows(Permission::Administer));
    }

    #[test]
    fn governance_plugin_manifests_are_stable() {
        assert_eq!(GovernanceRbacPlugin.manifest().id, "archub.governance.rbac");
        assert_eq!(AuditTrailPlugin.manifest().id, "archub.compliance.audit");
    }
}
