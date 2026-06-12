//! Automation, notification and analytics core plugin contracts for ArcHub.

use archub_core::{CorePlugin, CorePluginManifest};

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Trigger {
    IntervalSeconds(u64),
    Cron(String),
    Event(String),
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct AutomationJob {
    pub id: String,
    pub trigger: Trigger,
    pub enabled: bool,
}

impl AutomationJob {
    pub fn can_run(&self) -> bool {
        self.enabled && !self.id.trim().is_empty()
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct NotificationEnvelope {
    pub channel: String,
    pub subject: String,
    pub body: String,
}

#[derive(Debug, Default)]
pub struct MaintenanceJobsPlugin;

impl CorePlugin for MaintenanceJobsPlugin {
    fn manifest(&self) -> CorePluginManifest {
        CorePluginManifest {
            id: "archub.automation.maintenance",
            name: "Maintenance Jobs",
            version: "1.0.0",
            capability: "automation",
            provides: &["jobs.maintenance", "jobs.scheduler"],
        }
    }
}

#[derive(Debug, Default)]
pub struct WebhookNotificationPlugin;

impl CorePlugin for WebhookNotificationPlugin {
    fn manifest(&self) -> CorePluginManifest {
        CorePluginManifest {
            id: "archub.notification.webhook",
            name: "Webhook Notifications",
            version: "1.0.0",
            capability: "notification",
            provides: &["notification.webhook", "notification.signed_delivery"],
        }
    }
}

#[derive(Debug, Default)]
pub struct ContentHealthAnalyticsPlugin;

impl CorePlugin for ContentHealthAnalyticsPlugin {
    fn manifest(&self) -> CorePluginManifest {
        CorePluginManifest {
            id: "archub.analytics.health",
            name: "Content Health Analytics",
            version: "1.0.0",
            capability: "analytics",
            provides: &["analytics.health", "analytics.quality_score"],
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use archub_core::CorePlugin;

    #[test]
    fn automation_job_requires_enabled_id() {
        let job = AutomationJob {
            id: "runtime-cleanup".to_owned(),
            trigger: Trigger::IntervalSeconds(300),
            enabled: true,
        };
        assert!(job.can_run());
    }

    #[test]
    fn automation_plugin_manifests_are_stable() {
        assert_eq!(
            MaintenanceJobsPlugin.manifest().id,
            "archub.automation.maintenance"
        );
        assert_eq!(
            WebhookNotificationPlugin.manifest().id,
            "archub.notification.webhook"
        );
        assert_eq!(
            ContentHealthAnalyticsPlugin.manifest().id,
            "archub.analytics.health"
        );
    }
}
