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

#[derive(Debug, Default)]
pub struct RuntimeSnapshotSyncPlugin;

impl CorePlugin for RuntimeSnapshotSyncPlugin {
    fn manifest(&self) -> CorePluginManifest {
        CorePluginManifest {
            id: "archub.sync.runtime",
            name: "Runtime Snapshot Sync",
            version: "1.0.0",
            capability: "sync",
            provides: &["runtime.snapshot"],
        }
    }
}

#[derive(Debug, Default)]
pub struct MarkdownImporterPlugin;

impl CorePlugin for MarkdownImporterPlugin {
    fn manifest(&self) -> CorePluginManifest {
        CorePluginManifest {
            id: "archub.import.markdown",
            name: "Markdown Importer",
            version: "1.0.0",
            capability: "importer",
            provides: &["import.markdown"],
        }
    }
}

#[derive(Debug, Default)]
pub struct VaultExportPlugin;

impl CorePlugin for VaultExportPlugin {
    fn manifest(&self) -> CorePluginManifest {
        CorePluginManifest {
            id: "archub.export.vault",
            name: "Obsidian Vault Export",
            version: "1.0.0",
            capability: "exporter",
            provides: &["export.vault"],
        }
    }
}

#[derive(Debug, Default)]
pub struct ContentBuilderMacrosPlugin;

impl CorePlugin for ContentBuilderMacrosPlugin {
    fn manifest(&self) -> CorePluginManifest {
        CorePluginManifest {
            id: "archub.macro.blocks",
            name: "Content Builder Macros",
            version: "1.0.0",
            capability: "macro",
            provides: &["macro.blocks"],
        }
    }
}

#[derive(Debug, Default)]
pub struct StructuredEditorPlugin;

impl CorePlugin for StructuredEditorPlugin {
    fn manifest(&self) -> CorePluginManifest {
        CorePluginManifest {
            id: "archub.editor.builder",
            name: "Structured Editor",
            version: "1.0.0",
            capability: "editor",
            provides: &["editor.builder"],
        }
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

    #[test]
    fn cms_adjacent_plugin_manifests_are_stable() {
        assert_eq!(
            RuntimeSnapshotSyncPlugin.manifest().id,
            "archub.sync.runtime"
        );
        assert_eq!(
            MarkdownImporterPlugin.manifest().id,
            "archub.import.markdown"
        );
        assert_eq!(VaultExportPlugin.manifest().id, "archub.export.vault");
        assert_eq!(
            ContentBuilderMacrosPlugin.manifest().id,
            "archub.macro.blocks"
        );
        assert_eq!(
            StructuredEditorPlugin.manifest().id,
            "archub.editor.builder"
        );
    }
}
