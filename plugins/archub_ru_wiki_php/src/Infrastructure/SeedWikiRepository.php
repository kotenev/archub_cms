<?php

declare(strict_types=1);

namespace ArcHub\WikiPlugin\Infrastructure;

use ArcHub\WikiPlugin\Domain\Diagram;
use ArcHub\WikiPlugin\Domain\WikiPage;
use ArcHub\WikiPlugin\Domain\WikiSpace;

final class SeedWikiRepository
{
    public function spaces(): array
    {
        return [
            new WikiSpace('ARCH', 'ArcHub Platform', 'Architecture, roadmap and delivery playbooks.', 'platform-team', false),
            new WikiSpace('OPS', 'Operations', 'Runbooks, incident playbooks and release readiness.', 'sre-team', true),
            new WikiSpace('SITE', 'ArcHub.ru Site', 'Public site content model and editorial workflows.', 'content-team', false),
        ];
    }

    public function pages(): array
    {
        return [
            new WikiPage(
                'platform-overview',
                'ARCH',
                'ArcHub Platform Overview',
                'approved',
                'platform-team',
                ['architecture', 'cms', 'plugins'],
                "# ArcHub Platform\n{status:approved}\n\nArcHub.ru uses a modular knowledge platform where CMS, wiki, diagrams and integrations are installable modules.\n\n## Key capabilities\n\n- Core CMS plugin\n- External PHP wiki module\n- Marketplace distributions\n- Offline and online LLM integration\n\n{drawio:platform-map}\n\nRelated: [[plugin-marketplace|Plugin Marketplace]] and [[site-editorial-flow|Site Editorial Flow]].",
                12,
                '2026-06-12T10:00:00Z',
            ),
            new WikiPage(
                'plugin-marketplace',
                'ARCH',
                'Plugin Marketplace',
                'review',
                'platform-team',
                ['marketplace', 'security', 'plugins'],
                "# Plugin Marketplace\n{status:review}\n\nMarketplace packages preserve plugin metadata, source bundles, hashes and capability contracts.\n\n{toc}\n\n## Governance\n\nEvery install is audited and every executable plugin uses the platform adapter boundary.",
                7,
                '2026-06-12T11:30:00Z',
            ),
            new WikiPage(
                'site-editorial-flow',
                'SITE',
                'ArcHub.ru Editorial Flow',
                'draft',
                'content-team',
                ['site', 'workflow', 'drawio'],
                "# ArcHub.ru Editorial Flow\n{status:draft}\n\nEditors draft public pages, reviewers approve changes, and publishing exports a runtime snapshot.\n\n{drawio:editorial-flow}\n\nChildren: {children:SITE}",
                3,
                '2026-06-12T12:00:00Z',
            ),
            new WikiPage(
                'incident-runbook',
                'OPS',
                'Incident Runbook',
                'approved',
                'sre-team',
                ['runbook', 'ops', 'itil'],
                "# Incident Runbook\n{status:approved}\n\n1. Triage impact.\n2. Open incident room.\n3. Attach timeline diagram.\n4. Publish postmortem.\n\nRelated: [[platform-overview|Platform Overview]].",
                5,
                '2026-06-12T13:15:00Z',
            ),
        ];
    }

    public function page(string $slug): ?WikiPage
    {
        foreach ($this->pages() as $page) {
            if ($page->slug === $slug) {
                return $page;
            }
        }
        return null;
    }

    public function diagrams(): array
    {
        return [
            new Diagram('platform-map', 'ArcHub Platform Map', 'ARCH', $this->mxfile('platform-map', 'ArcHub', 'CMS Core', 'PHP Wiki'), '2026-06-12T10:00:00Z'),
            new Diagram('editorial-flow', 'Editorial Workflow', 'SITE', $this->mxfile('editorial-flow', 'Draft', 'Review', 'Publish'), '2026-06-12T12:00:00Z'),
        ];
    }

    public function diagram(string $id): ?Diagram
    {
        foreach ($this->diagrams() as $diagram) {
            if ($diagram->id === $id) {
                return $diagram;
            }
        }
        return null;
    }

    public function links(): array
    {
        return [
            ['source' => 'platform-overview', 'target' => 'plugin-marketplace', 'type' => 'wiki-link'],
            ['source' => 'platform-overview', 'target' => 'site-editorial-flow', 'type' => 'wiki-link'],
            ['source' => 'incident-runbook', 'target' => 'platform-overview', 'type' => 'wiki-link'],
        ];
    }

    private function mxfile(string $id, string $a, string $b, string $c): string
    {
        return '<mxfile host="ArcHub.ru Wiki"><diagram id="' . $id . '" name="Architecture"><mxCell id="a" value="' . $a . '" vertex="1" parent="1"/><mxCell id="b" value="' . $b . '" vertex="1" parent="1"/><mxCell id="c" value="' . $c . '" vertex="1" parent="1"/></diagram></mxfile>';
    }
}
