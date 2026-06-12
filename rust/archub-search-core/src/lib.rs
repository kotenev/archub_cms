//! Search core plugin contracts for ArcHub.

use archub_core::{CorePlugin, CorePluginManifest};

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SearchDocument {
    pub id: String,
    pub title: String,
    pub body: String,
    pub tags: Vec<String>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SearchQuery {
    pub terms: Vec<String>,
    pub limit: usize,
}

impl SearchQuery {
    pub fn parse(input: &str, limit: usize) -> Self {
        let terms = input
            .split_whitespace()
            .map(str::to_lowercase)
            .filter(|term| !term.is_empty())
            .collect();
        Self { terms, limit }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SearchHit {
    pub document_id: String,
    pub score: usize,
}

pub trait SearchIndex {
    fn upsert(&mut self, document: SearchDocument);

    fn search(&self, query: &SearchQuery) -> Vec<SearchHit>;
}

#[derive(Debug, Default)]
pub struct LexicalSearchPlugin;

impl CorePlugin for LexicalSearchPlugin {
    fn manifest(&self) -> CorePluginManifest {
        CorePluginManifest {
            id: "archub.search.lexical",
            name: "Lexical Search",
            version: "1.0.0",
            capability: "search",
            provides: &["search.lexical", "search.facets", "search.index"],
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use archub_core::CorePlugin;

    #[test]
    fn query_parser_normalizes_terms() {
        let query = SearchQuery::parse(" Knowledge  Graph ", 10);
        assert_eq!(query.terms, vec!["knowledge", "graph"]);
    }

    #[test]
    fn lexical_plugin_manifest_is_stable() {
        let manifest = LexicalSearchPlugin.manifest();
        assert_eq!(manifest.id, "archub.search.lexical");
        assert!(manifest.provides.contains(&"search.index"));
    }
}
