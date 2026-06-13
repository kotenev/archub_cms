<?php

declare(strict_types=1);

namespace ArcHub\Lite\Renderer;

use ArcHub\Lite\Kernel\Config;

/**
 * Shared HTML chrome (sidebar + shell) for the public site and the admin surface.
 */
final readonly class Layout
{
    public function __construct(private Config $config)
    {
    }

    public function url(string $path = '/'): string
    {
        return $this->config->url($path);
    }

    public function render(string $title, string $body, bool $admin = false): string
    {
        $site = $this->e($this->config->str('site_name', 'ArcHub Lite'));
        $nav = $admin ? $this->adminNav() : $this->siteNav();
        $badge = $admin ? '<span class="tag">admin</span>' : '';

        return '<!doctype html><html lang="en"><head><meta charset="utf-8" />'
            . '<meta name="viewport" content="width=device-width, initial-scale=1" />'
            . '<title>' . $this->e($title) . ' · ' . $site . '</title>'
            . '<link rel="stylesheet" href="' . $this->e($this->url('/assets/lite.css')) . '" />'
            . '</head><body><div class="layout">'
            . '<aside class="sidebar"><div class="brand"><strong>' . $site . '</strong>'
            . '<span>ArcHub Lite · PHP + Postgres</span>' . $badge . '</div>'
            . '<nav class="nav">' . $nav . '</nav></aside>'
            . '<main class="content">' . $body . '</main></div></body></html>';
    }

    private function siteNav(): string
    {
        return $this->link('/', 'Home')
            . '<span class="nav__label">Knowledge</span>'
            . $this->link('/search', 'Search')
            . '<span class="nav__label">Service Desk</span>'
            . $this->link('/support', 'Raise a request')
            . '<span class="nav__label">Developers</span>'
            . $this->link('/api/content/tree', 'Delivery API')
            . $this->link('/admin', 'Admin');
    }

    private function adminNav(): string
    {
        return $this->link('/', '← Public site')
            . '<span class="nav__label">Backoffice</span>'
            . $this->link('/admin', 'Dashboard')
            . $this->link('/admin/pages', 'Pages')
            . $this->link('/admin/pages/new', 'New page')
            . $this->link('/admin/requests', 'Service desk')
            . $this->link('/admin/logout', 'Log out');
    }

    private function link(string $path, string $label): string
    {
        return '<a href="' . $this->e($this->url($path)) . '">' . $this->e($label) . '</a>';
    }

    public function e(string $value): string
    {
        return htmlspecialchars($value, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
    }

    /** Very small, safe Markdown-ish renderer (escaped first). */
    public function renderBody(string $body): string
    {
        $html = $this->e($body);
        $html = preg_replace('/^### (.+)$/m', '<h3>$1</h3>', $html) ?? $html;
        $html = preg_replace('/^## (.+)$/m', '<h2>$1</h2>', $html) ?? $html;
        $html = preg_replace('/^# (.+)$/m', '<h2>$1</h2>', $html) ?? $html;
        $html = preg_replace('/\*\*(.+?)\*\*/s', '<strong>$1</strong>', $html) ?? $html;
        $blocks = preg_split('/\n{2,}/', $html) ?: [$html];
        $out = '';
        foreach ($blocks as $block) {
            $block = trim($block);
            if ($block === '') {
                continue;
            }
            $out .= str_starts_with($block, '<h2') || str_starts_with($block, '<h3')
                ? $block
                : '<p>' . nl2br($block) . '</p>';
        }
        return $out;
    }
}
