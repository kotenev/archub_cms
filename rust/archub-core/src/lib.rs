//! Rust contracts for ArcHub core plugins.

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct CorePluginManifest {
    pub id: &'static str,
    pub name: &'static str,
    pub version: &'static str,
    pub capability: &'static str,
    pub provides: &'static [&'static str],
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum CorePluginState {
    Ready,
    Degraded(&'static str),
    Unavailable(&'static str),
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct CorePluginHealth {
    pub state: CorePluginState,
    pub details: &'static str,
}

impl CorePluginHealth {
    pub const fn ready(details: &'static str) -> Self {
        Self {
            state: CorePluginState::Ready,
            details,
        }
    }
}

pub trait CorePlugin {
    fn manifest(&self) -> CorePluginManifest;

    fn health(&self) -> CorePluginHealth {
        CorePluginHealth::ready("ready")
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    struct TestPlugin;

    impl CorePlugin for TestPlugin {
        fn manifest(&self) -> CorePluginManifest {
            CorePluginManifest {
                id: "archub.test",
                name: "Test",
                version: "1.0.0",
                capability: "platform_module",
                provides: &["test"],
            }
        }
    }

    #[test]
    fn core_plugin_exposes_manifest_and_health() {
        let plugin = TestPlugin;
        assert_eq!(plugin.manifest().id, "archub.test");
        assert_eq!(plugin.health().state, CorePluginState::Ready);
    }
}
