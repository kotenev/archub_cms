//! Knowledge-space core plugin contracts for ArcHub.

use archub_core::{CorePlugin, CorePluginManifest};

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct KnowledgeSpace {
    pub key: String,
    pub name: String,
    pub private: bool,
}

impl KnowledgeSpace {
    pub fn is_addressable(&self) -> bool {
        !self.key.trim().is_empty() && !self.name.trim().is_empty()
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Backlink {
    pub source_id: String,
    pub target_id: String,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct TagPath {
    pub parts: Vec<String>,
}

#[derive(Debug, Default)]
pub struct KnowledgeSpacesPlugin;

impl CorePlugin for KnowledgeSpacesPlugin {
    fn manifest(&self) -> CorePluginManifest {
        CorePluginManifest {
            id: "archub.knowledge.spaces",
            name: "Knowledge Spaces",
            version: "1.0.0",
            capability: "knowledge",
            provides: &["spaces", "tags", "graph", "bookmarks", "templates"],
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use archub_core::CorePlugin;

    #[test]
    fn knowledge_space_requires_key_and_name() {
        let space = KnowledgeSpace {
            key: "ENG".to_owned(),
            name: "Engineering".to_owned(),
            private: false,
        };
        assert!(space.is_addressable());
    }

    #[test]
    fn knowledge_plugin_manifest_is_stable() {
        assert_eq!(
            KnowledgeSpacesPlugin.manifest().id,
            "archub.knowledge.spaces"
        );
    }
}
