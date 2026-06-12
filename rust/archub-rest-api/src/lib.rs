//! Rust REST API module contract for ArcHub.

use archub_core::{CorePlugin, CorePluginManifest};

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RouteDescriptor {
    pub method: &'static str,
    pub path: &'static str,
    pub capability: &'static str,
}

pub const PLATFORM_ROUTES: &[RouteDescriptor] = &[
    RouteDescriptor {
        method: "GET",
        path: "/api/platform/capabilities",
        capability: "platform.read",
    },
    RouteDescriptor {
        method: "GET",
        path: "/api/platform/modules/manage",
        capability: "modules.read",
    },
    RouteDescriptor {
        method: "GET",
        path: "/api/platform/core-plugins",
        capability: "core_plugins.read",
    },
    RouteDescriptor {
        method: "GET",
        path: "/api/platform/core-plugins/rust-workspace",
        capability: "core_plugins.read",
    },
    RouteDescriptor {
        method: "POST",
        path: "/api/platform/modules/install/file",
        capability: "modules.install",
    },
];

#[derive(Debug, Default)]
pub struct RestApiCorePlugin;

impl CorePlugin for RestApiCorePlugin {
    fn manifest(&self) -> CorePluginManifest {
        CorePluginManifest {
            id: "archub.rest.platform",
            name: "Platform REST API",
            version: "1.0.0",
            capability: "rest_api",
            provides: &["api.platform", "api.plugins", "api.modules"],
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use archub_core::CorePlugin;

    #[test]
    fn rest_routes_include_module_install_surface() {
        assert!(PLATFORM_ROUTES
            .iter()
            .any(|route| route.path == "/api/platform/modules/install/file"));
        assert!(PLATFORM_ROUTES
            .iter()
            .any(|route| route.path == "/api/platform/core-plugins/rust-workspace"));
    }

    #[test]
    fn rest_core_plugin_manifest_is_stable() {
        assert_eq!(RestApiCorePlugin.manifest().id, "archub.rest.platform");
    }
}
