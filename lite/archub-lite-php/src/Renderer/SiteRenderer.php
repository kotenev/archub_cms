<?php

declare(strict_types=1);

namespace ArcHub\Lite\Renderer;

use ArcHub\Lite\Domain\Page;
use ArcHub\Lite\Domain\ServiceRequest;

/**
 * Renders the public (visitor-facing) surface: home, pages, search and the
 * self-service desk.
 */
final readonly class SiteRenderer
{
    public function __construct(private Layout $layout)
    {
    }

    /** @param list<array<string,mixed>> $tree */
    public function home(array $tree): string
    {
        $body = '<div class="hero"><h1>' . $this->layout->e($this->title()) . '</h1>'
            . '<p class="muted">A headless CMS, full-text knowledge base and lite ITIL service desk '
            . 'on shared hosting — PHP-FPM + nginx + PostgreSQL.</p>'
            . '<form class="search" action="' . $this->layout->e($this->layout->url('/search')) . '" method="get">'
            . '<input name="q" placeholder="Search the knowledge base…" /><button>Search</button></form></div>'
            . '<h2>Contents</h2>' . $this->tree($tree);
        return $this->layout->render('Home', $body);
    }

    /**
     * @param list<Page> $children
     */
    public function page(Page $page, array $children): string
    {
        $body = '<article class="page"><a class="muted" href="' . $this->layout->e($this->layout->url('/')) . '">← Home</a>'
            . '<h1>' . $this->layout->e($page->title) . '</h1>'
            . '<div class="page-body">' . $this->layout->renderBody($page->body) . '</div>';
        if ($children !== []) {
            $body .= '<h2>In this section</h2><ul class="list">';
            foreach ($children as $child) {
                $body .= '<li><a href="' . $this->layout->e($this->layout->url('/p/' . $child->slug)) . '">'
                    . $this->layout->e($child->title) . '</a></li>';
            }
            $body .= '</ul>';
        }
        $body .= '</article>';
        return $this->layout->render($page->title, $body);
    }

    /** @param list<array{page:Page,rank:float,excerpt:string}> $results */
    public function search(string $query, array $results): string
    {
        $body = '<h1>Search</h1>'
            . '<form class="search" action="' . $this->layout->e($this->layout->url('/search')) . '" method="get">'
            . '<input name="q" value="' . $this->layout->e($query) . '" placeholder="Search…" /><button>Search</button></form>';
        if ($query === '') {
            $body .= '<p class="muted">Type a query to search published content.</p>';
        } elseif ($results === []) {
            $body .= '<p class="muted">No results for “' . $this->layout->e($query) . '”.</p>';
        } else {
            $body .= '<p class="muted">' . count($results) . ' result(s).</p><ul class="list">';
            foreach ($results as $hit) {
                $page = $hit['page'];
                $body .= '<li><a href="' . $this->layout->e($this->layout->url('/p/' . $page->slug)) . '">'
                    . $this->layout->e($page->title) . '</a>'
                    . '<p class="muted">' . $this->layout->e(strip_tags($hit['excerpt'])) . '</p></li>';
            }
            $body .= '</ul>';
        }
        return $this->layout->render('Search', $body);
    }

    public function supportForm(?string $error = null, ?ServiceRequest $created = null): string
    {
        $notice = '';
        if ($created !== null) {
            $notice = '<div class="notice notice--ok">Request <strong>' . $this->layout->e($created->key)
                . '</strong> created. Track it at <a href="' . $this->layout->e($this->layout->url('/support/' . $created->key))
                . '">' . $this->layout->e($created->key) . '</a>.</div>';
        }
        if ($error !== null) {
            $notice .= '<div class="notice notice--err">' . $this->layout->e($error) . '</div>';
        }

        $types = $this->options(ServiceRequest::TYPES);
        $prios = $this->options(ServiceRequest::PRIORITIES, 'medium');
        $action = $this->layout->e($this->layout->url('/support'));
        $body = '<h1>Service Desk</h1><p class="muted">Raise an incident, service request or question.</p>'
            . $notice
            . '<form class="form" method="post" action="' . $action . '">'
            . $this->field('Your email', '<input name="requester" type="email" placeholder="you@example.com" />')
            . $this->field('Type', '<select name="type">' . $types . '</select>')
            . $this->field('Priority', '<select name="priority">' . $prios . '</select>')
            . $this->field('Summary', '<input name="summary" required maxlength="200" />')
            . $this->field('Description', '<textarea name="description" rows="5"></textarea>')
            . '<button class="btn" type="submit">Submit request</button></form>';
        return $this->layout->render('Service Desk', $body);
    }

    public function requestStatus(ServiceRequest $request): string
    {
        $r = $request;
        $body = '<article class="page"><a class="muted" href="' . $this->layout->e($this->layout->url('/support')) . '">← Service desk</a>'
            . '<h1>' . $this->layout->e($r->key) . '</h1>'
            . '<div class="meta">' . $this->statusBadge($r->status)
            . '<span class="tag">' . $this->layout->e($r->type) . '</span>'
            . '<span class="tag">' . $this->layout->e($r->priority) . '</span></div>'
            . '<h2>' . $this->layout->e($r->summary) . '</h2>'
            . '<p>' . nl2br($this->layout->e($r->description)) . '</p>'
            . '<dl class="facts"><dt>Requester</dt><dd>' . $this->layout->e($r->requester) . '</dd>'
            . '<dt>Assignee</dt><dd>' . $this->layout->e($r->assignee ?? '—') . '</dd>'
            . '<dt>Created</dt><dd>' . $this->layout->e((string) $r->createdAt) . '</dd></dl></article>';
        return $this->layout->render($r->key, $body);
    }

    public function login(?string $error = null): string
    {
        $notice = $error !== null
            ? '<div class="notice notice--err">' . $this->layout->e($error) . '</div>' : '';
        $body = '<h1>Admin sign in</h1>' . $notice
            . '<form class="form" method="post" action="' . $this->layout->e($this->layout->url('/admin/login')) . '">'
            . $this->field('Password', '<input name="password" type="password" required autofocus />')
            . '<button class="btn" type="submit">Sign in</button></form>';
        return $this->layout->render('Sign in', $body);
    }

    public function adminLocked(): string
    {
        $body = '<h1>Admin locked</h1><div class="notice notice--err">No <code>admin_password_hash</code> is '
            . 'configured. Set one in <code>config.php</code> to enable the backoffice.</div>'
            . '<p class="muted">Generate a hash:</p>'
            . '<pre>php -r "echo password_hash(\'your-password\', PASSWORD_DEFAULT), PHP_EOL;"</pre>';
        return $this->layout->render('Admin locked', $body);
    }

    // ---- helpers --------------------------------------------------------

    /** @param list<array<string,mixed>> $nodes */
    private function tree(array $nodes): string
    {
        if ($nodes === []) {
            return '<p class="muted">No published pages yet.</p>';
        }
        $html = '<ul class="tree">';
        foreach ($nodes as $node) {
            $html .= '<li><a href="' . $this->layout->e($this->layout->url('/p/' . $node['slug'])) . '">'
                . $this->layout->e((string) $node['title']) . '</a>';
            if (!empty($node['children'])) {
                $html .= $this->tree($node['children']);
            }
            $html .= '</li>';
        }
        return $html . '</ul>';
    }

    private function field(string $label, string $control): string
    {
        return '<label class="field"><span>' . $this->layout->e($label) . '</span>' . $control . '</label>';
    }

    /** @param list<string> $values */
    private function options(array $values, string $selected = ''): string
    {
        $html = '';
        foreach ($values as $value) {
            $sel = $value === $selected ? ' selected' : '';
            $html .= '<option value="' . $this->layout->e($value) . '"' . $sel . '>'
                . $this->layout->e($value) . '</option>';
        }
        return $html;
    }

    private function statusBadge(string $status): string
    {
        return '<span class="badge status-' . $this->layout->e($status) . '">'
            . $this->layout->e(str_replace('_', ' ', $status)) . '</span>';
    }

    private function title(): string
    {
        return 'Welcome';
    }
}
