//! ArcHub CMS core plugin skeleton.

use archub_core::{CorePlugin, CorePluginHealth, CorePluginManifest};

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ContentStatus {
    Draft,
    Published,
    Trashed,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ContentNode {
    pub id: String,
    pub parent_id: String,
    pub name: String,
    pub route_path: String,
    pub status: ContentStatus,
}

impl ContentNode {
    pub fn can_publish(&self) -> bool {
        matches!(self.status, ContentStatus::Draft | ContentStatus::Published)
            && !self.name.trim().is_empty()
            && self.route_path.starts_with('/')
    }
}

#[derive(Debug, Default)]
pub struct CmsCorePlugin;

impl CorePlugin for CmsCorePlugin {
    fn manifest(&self) -> CorePluginManifest {
        CorePluginManifest {
            id: "archub.cms.core",
            name: "ArcHub CMS Core",
            version: "1.0.0",
            capability: "cms",
            provides: &["content", "modeling", "publishing", "delivery", "runtime"],
        }
    }

    fn health(&self) -> CorePluginHealth {
        CorePluginHealth::ready("cms core contract loaded")
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use archub_core::CorePlugin;

    #[test]
    fn content_node_publish_guard_matches_core_contract() {
        let node = ContentNode {
            id: "n1".to_owned(),
            parent_id: "root".to_owned(),
            name: "Page".to_owned(),
            route_path: "/cms/page".to_owned(),
            status: ContentStatus::Draft,
        };
        assert!(node.can_publish());
    }

    #[test]
    fn cms_core_plugin_manifest_is_stable() {
        assert_eq!(CmsCorePlugin.manifest().id, "archub.cms.core");
    }
}
