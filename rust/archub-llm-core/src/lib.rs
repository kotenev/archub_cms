//! LLM and RAG core plugin contracts for ArcHub.

use archub_core::{CorePlugin, CorePluginManifest};

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum LlmExecutionMode {
    Offline,
    Online,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct LlmRequest {
    pub prompt: String,
    pub context: Vec<String>,
    pub mode: LlmExecutionMode,
}

impl LlmRequest {
    pub fn grounded(prompt: impl Into<String>, context: Vec<String>) -> Self {
        Self {
            prompt: prompt.into(),
            context,
            mode: LlmExecutionMode::Offline,
        }
    }

    pub fn has_grounding(&self) -> bool {
        !self.context.is_empty()
    }
}

pub trait LlmProvider {
    fn mode(&self) -> LlmExecutionMode;

    fn complete(&self, request: &LlmRequest) -> String;
}

#[derive(Debug, Default)]
pub struct OfflineExtractiveLlmPlugin;

impl CorePlugin for OfflineExtractiveLlmPlugin {
    fn manifest(&self) -> CorePluginManifest {
        CorePluginManifest {
            id: "archub.llm.extractive",
            name: "Offline Extractive LLM",
            version: "1.0.0",
            capability: "llm_provider",
            provides: &["llm.offline", "llm.grounded_answers"],
        }
    }
}

#[derive(Debug, Default)]
pub struct OpenAiCompatibleLlmPlugin;

impl CorePlugin for OpenAiCompatibleLlmPlugin {
    fn manifest(&self) -> CorePluginManifest {
        CorePluginManifest {
            id: "archub.llm.openai-compatible",
            name: "OpenAI Compatible LLM",
            version: "1.0.0",
            capability: "llm_provider",
            provides: &["llm.online", "llm.chat_completions"],
        }
    }
}

#[derive(Debug, Default)]
pub struct RagConnectorPlugin;

impl CorePlugin for RagConnectorPlugin {
    fn manifest(&self) -> CorePluginManifest {
        CorePluginManifest {
            id: "archub.connector.rag",
            name: "RAG Connector",
            version: "1.0.0",
            capability: "connector",
            provides: &["connector.rag", "rag.index_rebuild"],
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use archub_core::CorePlugin;

    #[test]
    fn grounded_request_requires_context() {
        let request = LlmRequest::grounded("answer", vec!["source".to_owned()]);
        assert!(request.has_grounding());
        assert_eq!(request.mode, LlmExecutionMode::Offline);
    }

    #[test]
    fn llm_plugin_manifests_are_stable() {
        assert_eq!(
            OfflineExtractiveLlmPlugin.manifest().id,
            "archub.llm.extractive"
        );
        assert_eq!(
            OpenAiCompatibleLlmPlugin.manifest().id,
            "archub.llm.openai-compatible"
        );
        assert_eq!(RagConnectorPlugin.manifest().capability, "connector");
    }
}
