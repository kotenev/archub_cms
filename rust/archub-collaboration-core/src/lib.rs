//! Collaboration and live-edit core plugin contracts for ArcHub.

use archub_core::{CorePlugin, CorePluginManifest};

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Presence {
    pub user_id: String,
    pub content_id: String,
    pub cursor: usize,
}

impl Presence {
    pub fn is_active(&self) -> bool {
        !self.user_id.trim().is_empty() && !self.content_id.trim().is_empty()
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct CommentThread {
    pub id: String,
    pub content_id: String,
    pub resolved: bool,
}

#[derive(Debug, Default)]
pub struct CollaborationThreadsPlugin;

impl CorePlugin for CollaborationThreadsPlugin {
    fn manifest(&self) -> CorePluginManifest {
        CorePluginManifest {
            id: "archub.collaboration.threads",
            name: "Collaboration Threads",
            version: "1.0.0",
            capability: "collaboration",
            provides: &["comments.threads", "mentions", "reactions"],
        }
    }
}

#[derive(Debug, Default)]
pub struct LiveEditPlugin;

impl CorePlugin for LiveEditPlugin {
    fn manifest(&self) -> CorePluginManifest {
        CorePluginManifest {
            id: "archub.collaboration.live-edit",
            name: "Live Edit",
            version: "1.0.0",
            capability: "live_edit",
            provides: &["live_edit.presence", "live_edit.conflict_detection"],
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use archub_core::CorePlugin;

    #[test]
    fn presence_requires_user_and_content() {
        let presence = Presence {
            user_id: "u1".to_owned(),
            content_id: "page-1".to_owned(),
            cursor: 42,
        };
        assert!(presence.is_active());
    }

    #[test]
    fn collaboration_plugin_manifests_are_stable() {
        assert_eq!(
            CollaborationThreadsPlugin.manifest().id,
            "archub.collaboration.threads"
        );
        assert_eq!(
            LiveEditPlugin.manifest().id,
            "archub.collaboration.live-edit"
        );
    }
}
