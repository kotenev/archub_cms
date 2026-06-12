//! Workflow core plugin contracts for ArcHub.

use archub_core::{CorePlugin, CorePluginManifest};

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum PublishingState {
    Draft,
    InReview,
    Approved,
    Scheduled,
    Published,
    Archived,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct WorkflowTransition {
    pub from: PublishingState,
    pub to: PublishingState,
    pub action: &'static str,
}

impl WorkflowTransition {
    pub fn is_publish_transition(&self) -> bool {
        matches!(
            (self.from, self.to),
            (PublishingState::Approved, PublishingState::Published)
                | (PublishingState::Scheduled, PublishingState::Published)
        )
    }
}

#[derive(Debug, Default)]
pub struct PublishingWorkflowPlugin;

impl CorePlugin for PublishingWorkflowPlugin {
    fn manifest(&self) -> CorePluginManifest {
        CorePluginManifest {
            id: "archub.workflow.publish",
            name: "Publishing Workflow",
            version: "1.0.0",
            capability: "workflow",
            provides: &["workflow.publish", "workflow.approval", "workflow.schedule"],
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use archub_core::CorePlugin;

    #[test]
    fn publish_transition_is_detected() {
        let transition = WorkflowTransition {
            from: PublishingState::Approved,
            to: PublishingState::Published,
            action: "publish",
        };
        assert!(transition.is_publish_transition());
    }

    #[test]
    fn workflow_plugin_manifest_is_stable() {
        assert_eq!(
            PublishingWorkflowPlugin.manifest().id,
            "archub.workflow.publish"
        );
    }
}
