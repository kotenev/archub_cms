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

#[derive(Debug, Default)]
pub struct PlatformKernelPlugin;

impl CorePlugin for PlatformKernelPlugin {
    fn manifest(&self) -> CorePluginManifest {
        CorePluginManifest {
            id: "archub.platform.kernel",
            name: "ArcHub Platform Kernel",
            version: "1.0.0",
            capability: "platform_module",
            provides: &["kernel", "events", "mediator", "saga"],
        }
    }
}

#[derive(Debug, Default)]
pub struct HostAuthBridgePlugin;

impl CorePlugin for HostAuthBridgePlugin {
    fn manifest(&self) -> CorePluginManifest {
        CorePluginManifest {
            id: "archub.auth.host",
            name: "Host Auth Bridge",
            version: "1.0.0",
            capability: "auth",
            provides: &["auth.port"],
        }
    }
}

#[derive(Debug, Default)]
pub struct JinjaRendererPlugin;

impl CorePlugin for JinjaRendererPlugin {
    fn manifest(&self) -> CorePluginManifest {
        CorePluginManifest {
            id: "archub.renderer.jinja",
            name: "Jinja Renderer",
            version: "1.0.0",
            capability: "renderer",
            provides: &["rendering"],
        }
    }
}

#[derive(Debug, Default)]
pub struct MaterialDocsThemePlugin;

impl CorePlugin for MaterialDocsThemePlugin {
    fn manifest(&self) -> CorePluginManifest {
        CorePluginManifest {
            id: "archub.theme.material",
            name: "Material Docs Theme",
            version: "1.0.0",
            capability: "theme",
            provides: &["theme.material"],
        }
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

    #[test]
    fn builtin_platform_manifests_are_stable() {
        assert_eq!(PlatformKernelPlugin.manifest().id, "archub.platform.kernel");
        assert_eq!(HostAuthBridgePlugin.manifest().capability, "auth");
        assert_eq!(JinjaRendererPlugin.manifest().capability, "renderer");
        assert_eq!(
            MaterialDocsThemePlugin.manifest().id,
            "archub.theme.material"
        );
    }
}
