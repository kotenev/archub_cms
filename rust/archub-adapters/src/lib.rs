//! Rust adapter contracts for ArcHub core plugins.

use archub_core::{CorePlugin, CorePluginManifest};

pub trait StorageAdapter {
    fn backend(&self) -> &'static str;
    fn read(&self, key: &str) -> Option<Vec<u8>>;
    fn write(&mut self, key: &str, value: &[u8]);
}

pub trait AuditAdapter {
    fn record(&mut self, action: &str, target: &str);
}

#[derive(Debug, Default)]
pub struct SqliteContentStoreAdapterPlugin;

impl CorePlugin for SqliteContentStoreAdapterPlugin {
    fn manifest(&self) -> CorePluginManifest {
        CorePluginManifest {
            id: "archub.adapter.sqlite",
            name: "SQLite Content Store Adapter",
            version: "1.0.0",
            capability: "adapter",
            provides: &["storage.sqlite", "repository.sqlite"],
        }
    }
}

#[derive(Debug, Default)]
pub struct PluginStoreAdapterPlugin;

impl CorePlugin for PluginStoreAdapterPlugin {
    fn manifest(&self) -> CorePluginManifest {
        CorePluginManifest {
            id: "archub.adapter.plugin-store",
            name: "Plugin Store Adapter",
            version: "1.0.0",
            capability: "adapter",
            provides: &["plugin.store", "plugin.audit"],
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use archub_core::CorePlugin;

    #[test]
    fn plugin_store_adapter_manifest_is_stable() {
        let manifest = PluginStoreAdapterPlugin.manifest();
        assert_eq!(manifest.capability, "adapter");
        assert!(manifest.provides.contains(&"plugin.audit"));
    }

    #[test]
    fn sqlite_adapter_manifest_is_stable() {
        let manifest = SqliteContentStoreAdapterPlugin.manifest();
        assert_eq!(manifest.id, "archub.adapter.sqlite");
        assert!(manifest.provides.contains(&"storage.sqlite"));
    }
}
