workspace "ArcHub CMS" "Architecture model for the standalone ArcHub CMS package." {
    model {
        editor = person "Content Editor" "Creates, reviews, publishes, and manages ArcHub content."
        visitor = person "Public Visitor" "Reads published ArcHub pages and delivery API responses."
        host = softwareSystem "FastAPI Host Application" "Embeds ArcHub CMS and supplies production integrations."
        runtimeConsumer = softwareSystem "Runtime/RAG Consumer" "Consumes exported runtime content and optional rebuilt indexes."

        archub = softwareSystem "ArcHub CMS" "Standalone headless CMS, Content Builder, and delivery API package." {
            routes = container "FastAPI Web Routes" "Admin UI, management APIs, public delivery, preview, feed, sitemap, and runtime actions." "FastAPI"
            cms = container "ArcHubCMSService" "Content model, SQLite persistence, workflow, permissions, delivery payloads, packages, webhooks, and runtime exports." "Python"
            builder = container "Content Builder Service" "Block catalog, blueprint catalog, JSON normalization, preview rendering, audit, and public HTML rendering." "Python"
            runtime = container "Runtime Helpers" "Imports runtime source materials, exports published snapshots, and invokes the RAG rebuild hook." "Python"
            rag = container "RAG Registry" "Registers corpus specs and provides the standalone external-indexer hook." "Python"
            ports = container "Host Integration Ports" "Auth, template, runtime source, cache invalidation, and audit contracts." "Python protocols"
            assets = container "Templates and Static Assets" "Packaged Jinja templates, CSS, and JavaScript used by the standalone UI." "Jinja/CSS/JavaScript"
            db = container "SQLite CMS Store" "Editorial state, published payloads, versions, permissions, workflow, tokens, redirects, domains, and activity." "SQLite" {
                tags "Database"
            }
            exports = container "Runtime Snapshot Files" "Published runtime content snapshots and manifests." "Filesystem" {
                tags "FileSystem"
            }
        }

        editor -> routes "Uses backoffice" "HTTP"
        visitor -> routes "Reads published pages and APIs" "HTTP"
        host -> routes "Includes router" "FastAPI"
        host -> ports "Implements adapters" "Python"
        routes -> cms "Delegates content, model, workflow, permissions, delivery, and package operations" "Python calls"
        routes -> builder "Delegates block catalog, preview, audit, and rendering operations" "Python calls"
        routes -> runtime "Triggers runtime sync, export, and rebuild operations" "Python calls"
        routes -> assets "Renders templates and serves assets"
        runtime -> rag "Loads corpus specs and calls rebuild hook" "Python calls"
        cms -> db "Reads and writes state" "SQLite"
        cms -> exports "Writes published runtime snapshots" "Filesystem"
        runtimeConsumer -> exports "Consumes snapshots or indexes" "Filesystem"
    }

    views {
        systemContext archub "SystemContext" {
            include *
            autolayout lr
        }

        container archub "Containers" {
            include *
            autolayout lr
        }

        styles {
            element "Person" {
                shape Person
                background #0B7285
                color #FFFFFF
            }
            element "Software System" {
                background #2F3E46
                color #FFFFFF
            }
            element "Container" {
                background #52796F
                color #FFFFFF
            }
            element "Database" {
                shape Cylinder
                background #F59F00
                color #1F1F1F
            }
            element "FileSystem" {
                shape Folder
                background #E9ECEF
                color #1F1F1F
            }
        }
    }
}
