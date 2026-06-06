workspace "ArcHub CMS" "Architecture model for the standalone ArcHub CMS package (current DDD architecture)." {
    model {
        editor = person "Content Editor" "Creates, reviews, publishes, and manages ArcHub content."
        visitor = person "Public Visitor" "Reads published ArcHub pages and delivery API responses."
        host = softwareSystem "FastAPI Host Application" "Embeds ArcHub CMS and supplies production integrations."
        runtimeConsumer = softwareSystem "Runtime/RAG Consumer" "Consumes exported runtime content and optional rebuilt indexes."
        pluginDev = person "Plugin Developer" "Develops ArcHub plugins via plugin.json manifests."
        agentClient = softwareSystem "Agent/LLM Client" "Consumes knowledge platform API for tool-augmented answers."

        archub = softwareSystem "ArcHub CMS" "Standalone headless CMS, Content Builder, and delivery API package with DDD bounded contexts." {
            routes = container "Legacy Web Routes" "Public delivery, backoffice CRUD, content builder, runtime export (HTML + JSON)." "FastAPI/Jinja2"
            platformRoutes = container "Platform Routes" "/api/platform/* JSON API covering all 20 bounded contexts." "FastAPI"
            collabRoutes = container "Collaboration Routes" "/api/platform/collaboration/* for comments, mentions, reactions." "FastAPI"
            adminRoutes = container "Admin Dashboard" "/admin/platform HTML single-pane-of-glass over capabilities, plugins, health." "FastAPI/Jinja2"

            platform = container "ArcHubPlatform" "Composition root wiring 20 bounded-context services onto shared CMS + EventBus + PluginHost." "Python"

            contentSvc = container "Content Service" "CQRS service for ContentNode aggregate (create, update, publish, delete)." "Python"
            modelingSvc = container "Modeling Service" "Query service for ContentTypeModel, DataType, Template, Compositions." "Python"
            deliverySvc = container "Delivery Read Service" "Sitemap, feed, tags, redirects, published document queries." "Python"
            publishingSvc = container "Publishing Service" "Lifecycle commands: publish, unpublish, workflow, trash, runtime export." "Python"
            workflowSvc = container "Workflow Service" "CQRS for Workflow state machine (draft→review→approved→scheduled→published)." "Python"
            governanceSvc = container "Governance Service" "CQRS for AccessRule, PermissionRule, RBAC, public access." "Python"
            versioningSvc = container "Versioning Service" "CQRS for Version history, diff, restore, cleanup." "Python"
            mediaSvc = container "Media Service" "CQRS for MediaAsset, folder reports, duplicate detection, usage." "Python"
            packageSvc = container "Packaging Service" "Export, inspect, dry-run plan, import content packages." "Python"
            webhookSvc = container "Webhooks Service" "CQRS for Webhook subscriptions, delivery, dispatch." "Python"
            searchSvc = container "Search Service" "Federated faceted search (lexical + semantic + plugin)." "Python"
            ftsSvc = container "FTS5 Search Service" "SQLite FTS5 full-text search with BM25 ranking." "Python"
            agentSvc = container "Agent Service" "Tool-augmented answering via LLMToolExt plugins." "Python"
            collabSvc = container "Collaboration Service" "Comments, mentions, reactions, threaded discussions." "Python"
            graphSvc = container "Graph Service" "Knowledge graph: backlinks, metrics, canvas layout." "Python"
            runtimeSvc = container "Runtime Service" "CQRS for runtime snapshots, RAG search, index rebuild." "Python"
            locSvc = container "Localization Service" "CQRS for dictionary, culture variants, translations." "Python"
            analyticsSvc = container "Analytics Service" "Health reports, audit, activity, cache reports." "Python"
            subSvc = container "Subscription Service" "CQRS for watch/unwatch, inbox, watchers." "Python"
            lockSvc = container "Lock Service" "CQRS for edit locks: acquire, release, list active." "Python"
            trashSvc = container "Trash Service" "CQRS for trashed items: restore, purge, empty." "Python"
            blueprintSvc = container "Blueprint Service" "CQRS for content blueprints: create, instantiate." "Python"
            pluginMgmtSvc = container "Plugin Management Service" "Catalog, enable, disable, configure plugins." "Python"
            ingestionSvc = container "Ingestion Service" "Bulk markdown corpus import via ImporterExt plugins." "Python"
            resilientLLM = container "Resilient LLM Provider" "Circuit-breaker wrapping online/offline LLM failover." "Python"

            pluginHost = container "Plugin Host" "Lifecycle manager: discover → permission-check → load → wire. 11 extension points." "Python"

            eventBus = container "Event Bus" "Synchronous in-process pub/sub with wildcard subscriptions." "Python"
            unitOfWork = container "Unit of Work" "Transaction boundary with post-commit event publishing." "Python"

            cmsLegacy = container "ArcHubCMSService" "Legacy monolithic service still used as SQLite persistence engine." "Python"

            ports = container "Host Integration Ports" "Auth, Template, Runtime, LLM, Embedding, Search, Cache, Audit Protocol contracts." "Python protocols"
            assets = container "Templates and Static Assets" "Packaged Jinja templates, CSS, and JavaScript." "Jinja/CSS/JavaScript"

            db = container "SQLite CMS Store" "Editorial state, published payloads, versions, permissions, workflow, tokens, redirects, domains, activity, plugin config." "SQLite" {
                tags "Database"
            }
            ftsIndex = container "FTS5 Index" "SQLite FTS5 full-text search index." "SQLite" {
                tags "Database"
            }
            exports = container "Runtime Snapshot Files" "Published runtime content snapshots and manifests." "Filesystem" {
                tags "FileSystem"
            }
            pluginFiles = container "Plugin Manifests" "plugin.json files discovered from ARCHUB_PLUGIN_DIRS." "Filesystem" {
                tags "FileSystem"
            }
        }

        editor -> routes "Uses backoffice" "HTTP"
        editor -> collabRoutes "Comments, mentions" "HTTP"
        visitor -> routes "Reads published pages and APIs" "HTTP"
        agentClient -> platformRoutes "Knowledge search, agent answers" "HTTP"
        host -> routes "Includes router" "FastAPI"
        host -> ports "Implements adapters" "Python"

        routes -> platform "Delegates" "Python calls"
        platformRoutes -> platform "Delegates" "Python calls"
        collabRoutes -> platform "Delegates" "Python calls"
        adminRoutes -> platform "Delegates" "Python calls"

        platform -> contentSvc "Wires" "Python"
        platform -> modelingSvc "Wires" "Python"
        platform -> deliverySvc "Wires" "Python"
        platform -> publishingSvc "Wires" "Python"
        platform -> workflowSvc "Wires" "Python"
        platform -> governanceSvc "Wires" "Python"
        platform -> agentSvc "Wires" "Python"
        platform -> searchSvc "Wires" "Python"
        platform -> collabSvc "Wires" "Python"
        platform -> pluginHost "Wires" "Python"
        platform -> cmsLegacy "Wires (legacy compat)" "Python"
        platform -> eventBus "Wires" "Python"

        contentSvc -> cmsLegacy "SQLite operations" "Python calls"
        modelingSvc -> cmsLegacy "SQLite operations" "Python calls"
        deliverySvc -> cmsLegacy "SQLite operations" "Python calls"
        publishingSvc -> cmsLegacy "SQLite operations" "Python calls"
        workflowSvc -> cmsLegacy "SQLite operations" "Python calls"
        governanceSvc -> cmsLegacy "SQLite operations" "Python calls"
        searchSvc -> ftsSvc "Full-text search" "Python calls"
        agentSvc -> searchSvc "Relevant docs" "Python calls"
        agentSvc -> resilientLLM "LLM completion" "Python calls"
        collabSvc -> cmsLegacy "SQLite operations" "Python calls"

        cmsLegacy -> db "Reads and writes state" "SQLite"
        ftsSvc -> ftsIndex "Reads and writes" "SQLite"
        publishingSvc -> exports "Writes runtime snapshots" "Filesystem"
        pluginHost -> pluginFiles "Discovers manifests" "Filesystem"
        pluginHost -> db "Plugin config" "SQLite"
        routes -> assets "Renders templates" "Jinja2"

        runtimeConsumer -> exports "Consumes snapshots or indexes" "Filesystem"
        pluginDev -> pluginFiles "Writes plugin.json" "Filesystem"

        pluginHost -> eventBus "Subscribes EventHookExt" "Python calls"
        publishingSvc -> eventBus "Publishes domain events" "Python calls"
    }

    views {
        systemContext archub "SystemContext" {
            include *
            autolayout lr
        }

        container archub "Containers" {
            include *
            autolayout tb
        }

        container archub "PlatformServices" "Platform composition root and bounded-context services" {
            include
                platform
                contentSvc
                modelingSvc
                deliverySvc
                publishingSvc
                workflowSvc
                governanceSvc
                versioningSvc
                mediaSvc
                packageSvc
                webhookSvc
                searchSvc
                ftsSvc
                agentSvc
                collabSvc
                graphSvc
                runtimeSvc
                locSvc
                analyticsSvc
                subSvc
                lockSvc
                trashSvc
                blueprintSvc
                pluginMgmtSvc
                ingestionSvc
                resilientLLM
                pluginHost
                cmsLegacy
                eventBus
                unitOfWork
            autolayout lr
        }

        container archub "WebRoutes" "Web route adapters and their dependencies" {
            include
                editor
                visitor
                agentClient
                routes
                platformRoutes
                collabRoutes
                adminRoutes
                platform
                assets
            autolayout tb
        }

        container archub "PluginSystem" "Plugin host, extension points, and data stores" {
            include
                pluginDev
                pluginHost
                pluginFiles
                eventBus
                agentSvc
                searchSvc
                ingestionSvc
                db
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
