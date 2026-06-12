<?php

declare(strict_types=1);

namespace ArcHub\WikiPlugin\Renderer;

use ArcHub\WikiPlugin\Application\WikiService;

final readonly class WikiRenderer
{
    public function __construct(private WikiService $wiki)
    {
    }

    public function dashboard(): string
    {
        $overview = $this->wiki->overview();
        $cards = '';
        foreach ($this->wiki->pages() as $page) {
            $cards .= '<article class="card" data-search-card><h3><a href="/wiki/' . $this->e($page['slug']) . '">' . $this->e($page['title']) . '</a></h3>'
                . '<p class="muted">' . $this->e($page['space_key']) . ' &middot; v' . $page['version'] . ' &middot; ' . $this->e($page['owner']) . '</p>'
                . '<span class="badge status-' . $this->e($page['status']) . '">' . $this->e($page['status']) . '</span></article>';
        }

        $body = '<div class="toolbar"><div><h1>ArcHub.ru Enterprise Wiki</h1><p class="muted">Spaces, pages, diagrams, macros and graph demo for ArcHub platform plugins.</p></div>'
            . '<input class="search" placeholder="Filter pages" oninput="filterCards(this)" /></div>'
            . '<section class="grid">'
            . '<article class="card"><h2>' . $overview['spaces_total'] . '</h2><p>Spaces</p></article>'
            . '<article class="card"><h2>' . $overview['pages_total'] . '</h2><p>Pages</p></article>'
            . '<article class="card"><h2>' . $overview['diagrams_total'] . '</h2><p>Draw.io diagrams</p></article>'
            . '</section><h2>Knowledge Pages</h2><section class="grid">' . $cards . '</section>';

        return $this->shell($body);
    }

    public function page(array $page): string
    {
        $meta = '<div class="meta"><span class="badge status-' . $this->e($page['status']) . '">' . $this->e($page['status']) . '</span>'
            . '<span class="badge">' . $this->e($page['space_key']) . '</span>'
            . '<span class="muted">Owner: ' . $this->e($page['owner']) . '</span>'
            . '<span class="muted">v' . $page['version'] . '</span></div>';
        $labels = '<p class="muted">Labels: ' . $this->e(implode(', ', $page['labels'])) . '</p>';
        return $this->shell('<article class="page"><h1>' . $this->e($page['title']) . '</h1>' . $meta . $labels . '<div class="page-body">' . $this->renderWiki($page['body']) . '</div></article>');
    }

    public function diagramEditor(string $id): string
    {
        $diagram = $this->wiki->diagram($id);
        $title = $diagram['title'] ?? 'New Diagram';
        $body = '<section class="diagram-shell"><div class="toolbar"><div><h1>' . $this->e($title) . '</h1><p class="muted">Draw.io-compatible mxfile editor demo.</p></div>'
            . '<a class="button" href="/api/wiki/diagrams/' . $this->e($id) . '.drawio">Download .drawio</a></div>'
            . '<div class="diagram-toolbar"><button data-add-shape="page">Page</button><button data-add-shape="decision">Decision</button><button data-add-shape="lane">Swimlane</button><button class="secondary" onclick="navigator.clipboard.writeText(document.querySelector(\'[data-mxfile]\').value)">Copy mxfile</button></div>'
            . '<div class="drawio-grid"><aside class="stencil"><strong>Stencil</strong><p class="muted">Use page, decision and swimlane blocks for architecture and editorial flows.</p></aside><div><div class="canvas" data-diagram-canvas></div><textarea class="mxfile" data-mxfile>' . $this->e($diagram['mxfile'] ?? '') . '</textarea></div></div></section>';
        return $this->shell($body);
    }

    private function renderWiki(string $body): string
    {
        $html = $this->e($body);
        $html = preg_replace('/^# (.+)$/m', '<h1>$1</h1>', $html) ?? $html;
        $html = preg_replace('/^## (.+)$/m', '<h2>$1</h2>', $html) ?? $html;
        $html = preg_replace('/\[\[([^|\]]+)\|([^\]]+)\]\]/', '<a href="/wiki/$1">$2</a>', $html) ?? $html;
        $html = preg_replace_callback('/\{status:([^}]+)\}/', fn ($m) => '<span class="badge status-' . $this->e($m[1]) . '">' . $this->e($m[1]) . '</span>', $html) ?? $html;
        $html = preg_replace_callback('/\{drawio:([^}]+)\}/', fn ($m) => '<p><a class="button" href="/diagrams/' . $this->e($m[1]) . '">Open diagram</a></p>', $html) ?? $html;
        $html = str_replace('{toc}', '<nav class="card"><strong>Table of contents</strong><p class="muted">Generated from headings in the production service.</p></nav>', $html);
        $html = preg_replace('/\{children:([^}]+)\}/', '<span class="muted">Child page list for space $1</span>', $html) ?? $html;
        return nl2br($html);
    }

    private function shell(string $body): string
    {
        return '<!doctype html><html lang="en"><head><meta charset="utf-8" /><meta name="viewport" content="width=device-width, initial-scale=1" />'
            . '<title>ArcHub.ru Wiki</title><link rel="stylesheet" href="/assets/wiki.css" /><script src="/assets/wiki.js" defer></script></head>'
            . '<body><div class="layout"><aside class="sidebar"><div class="brand"><strong>ArcHub.ru Wiki</strong><span>PHP 8.4 / Symfony 8 external module</span></div>'
            . '<nav class="nav"><a href="/">Dashboard</a><a href="/wiki/platform-overview">Platform Overview</a><a href="/wiki/plugin-marketplace">Marketplace</a><a href="/diagrams/platform-map">Draw.io Editor</a><a href="/api/wiki/overview">API</a></nav></aside>'
            . '<main class="content">' . $body . '</main></div></body></html>';
    }

    private function e(string $value): string
    {
        return htmlspecialchars($value, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
    }
}
