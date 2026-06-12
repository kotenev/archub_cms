//! Media and DAM core plugin contracts for ArcHub.

use archub_core::{CorePlugin, CorePluginManifest};

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct MediaAsset {
    pub id: String,
    pub path: String,
    pub content_type: String,
    pub bytes: u64,
}

impl MediaAsset {
    pub fn is_valid_asset(&self) -> bool {
        !self.id.trim().is_empty()
            && self.path.starts_with('/')
            && self.content_type.contains('/')
            && self.bytes > 0
    }
}

pub trait BlobStore {
    fn put(&mut self, path: &str, bytes: &[u8]);

    fn get(&self, path: &str) -> Option<Vec<u8>>;
}

#[derive(Debug, Default)]
pub struct MediaAssetsPlugin;

impl CorePlugin for MediaAssetsPlugin {
    fn manifest(&self) -> CorePluginManifest {
        CorePluginManifest {
            id: "archub.media.assets",
            name: "Media Assets",
            version: "1.0.0",
            capability: "media",
            provides: &["media.assets", "media.dam", "media.blob_store"],
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use archub_core::CorePlugin;

    #[test]
    fn media_asset_validates_storage_contract() {
        let asset = MediaAsset {
            id: "logo".to_owned(),
            path: "/assets/logo.png".to_owned(),
            content_type: "image/png".to_owned(),
            bytes: 1024,
        };
        assert!(asset.is_valid_asset());
    }

    #[test]
    fn media_plugin_manifest_is_stable() {
        assert_eq!(MediaAssetsPlugin.manifest().id, "archub.media.assets");
    }
}
