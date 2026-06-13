<?php

declare(strict_types=1);

namespace ArcHub\Lite\Renderer;

use ArcHub\Lite\Domain\Page;
use ArcHub\Lite\Domain\ServiceRequest;

/**
 * Renders the authenticated backoffice: dashboard, page authoring and the
 * service-desk queue.
 */
final readonly class AdminRenderer
{
    public function __construct(private Layout $layout)
    {
    }

    /**
     * @param array<string,int> $requestCounts
     */
    public function dashboard(int $pageCount, int $publishedCount, array $requestCounts): string
    {
        $body = '<h1>Dashboard</h1><section class="grid">'
            . $this->stat($pageCount, 'Pages')
            . $this->stat($publishedCount, 'Published')
            . $this->stat($requestCounts['open'] ?? 0, 'Open requests')
            . $this->stat($requestCounts['total'] ?? 0, 'Total requests')
            . '</section>'
            . '<div class="actions"><a class="btn" href="' . $this->u('/admin/pages/new') . '">New page</a> '
            . '<a class="btn btn--ghost" href="' . $this->u('/admin/requests') . '">Service desk</a></div>';
        return $this->layout->render('Dashboard', $body, true);
    }

    /** @param list<Page> $pages */
    public function pages(array $pages): string
    {
        $rows = '';
        foreach ($pages as $page) {
            $indent = $page->parentId !== null ? '<span class="muted">↳ </span>' : '';
            $rows .= '<tr><td>' . $indent . $this->layout->e($page->title)
                . ' <code>' . $this->layout->e($page->slug) . '</code></td>'
                . '<td>' . $this->statusBadge($page->status) . '</td>'
                . '<td class="row-actions">'
                . '<a href="' . $this->u('/admin/pages/' . $page->id . '/edit') . '">Edit</a>'
                . $this->formButton('/admin/pages/' . $page->id . '/' . ($page->isPublished() ? 'unpublish' : 'publish'),
                    $page->isPublished() ? 'Unpublish' : 'Publish')
                . $this->formButton('/admin/pages/' . $page->id . '/delete', 'Delete', true)
                . '</td></tr>';
        }
        if ($rows === '') {
            $rows = '<tr><td colspan="3" class="muted">No pages yet.</td></tr>';
        }
        $body = '<div class="page-head"><h1>Pages</h1>'
            . '<a class="btn" href="' . $this->u('/admin/pages/new') . '">New page</a></div>'
            . '<table class="table"><thead><tr><th>Title</th><th>Status</th><th>Actions</th></tr></thead>'
            . '<tbody>' . $rows . '</tbody></table>';
        return $this->layout->render('Pages', $body, true);
    }

    /**
     * @param list<Page> $allPages
     */
    public function pageForm(array $allPages, ?Page $page = null, ?string $error = null): string
    {
        $isNew = $page === null;
        $action = $this->u($isNew ? '/admin/pages' : '/admin/pages/' . $page->id);
        $notice = $error !== null ? '<div class="notice notice--err">' . $this->layout->e($error) . '</div>' : '';

        $parentOptions = '<option value="">— top level —</option>';
        foreach ($allPages as $candidate) {
            if (!$isNew && $candidate->id === $page->id) {
                continue;
            }
            $sel = (!$isNew && $page->parentId === $candidate->id) ? ' selected' : '';
            $parentOptions .= '<option value="' . $candidate->id . '"' . $sel . '>'
                . $this->layout->e($candidate->title) . '</option>';
        }
        $publishChecked = (!$isNew && $page->isPublished()) ? ' checked' : '';

        $body = '<h1>' . ($isNew ? 'New page' : 'Edit page') . '</h1>' . $notice
            . '<form class="form" method="post" action="' . $action . '">'
            . $this->field('Title', '<input name="title" required value="' . $this->v($page?->title) . '" />')
            . $this->field('Slug', '<input name="slug" placeholder="auto from title" value="' . $this->v($page?->slug) . '" />')
            . $this->field('Parent', '<select name="parent_id">' . $parentOptions . '</select>')
            . $this->field('Sort', '<input name="sort" type="number" value="' . (int) ($page?->sort ?? 0) . '" />')
            . $this->field('Body', '<textarea name="body" rows="12">' . $this->v($page?->body) . '</textarea>');
        if ($isNew) {
            $body .= '<label class="check"><input type="checkbox" name="publish" value="1"' . $publishChecked . ' /> Publish immediately</label>';
        }
        $body .= '<button class="btn" type="submit">Save</button> '
            . '<a class="btn btn--ghost" href="' . $this->u('/admin/pages') . '">Cancel</a></form>';
        return $this->layout->render($isNew ? 'New page' : 'Edit page', $body, true);
    }

    /**
     * @param list<ServiceRequest> $requests
     * @param array<string,int> $counts
     */
    public function requests(array $requests, array $counts): string
    {
        $rows = '';
        foreach ($requests as $r) {
            $rows .= '<tr><td><a href="' . $this->u('/admin/requests/' . $r->key) . '">' . $this->layout->e($r->key) . '</a></td>'
                . '<td>' . $this->layout->e($r->summary) . '</td>'
                . '<td>' . $this->statusBadge($r->status) . '</td>'
                . '<td>' . $this->layout->e($r->priority) . '</td>'
                . '<td>' . $this->layout->e($r->assignee ?? '—') . '</td></tr>';
        }
        if ($rows === '') {
            $rows = '<tr><td colspan="5" class="muted">No requests.</td></tr>';
        }
        $body = '<h1>Service desk</h1><section class="grid">'
            . $this->stat($counts['open'] ?? 0, 'Open')
            . $this->stat($counts['resolved'] ?? 0, 'Resolved')
            . $this->stat($counts['closed'] ?? 0, 'Closed')
            . $this->stat($counts['total'] ?? 0, 'Total')
            . '</section>'
            . '<table class="table"><thead><tr><th>Key</th><th>Summary</th><th>Status</th><th>Priority</th><th>Assignee</th></tr></thead>'
            . '<tbody>' . $rows . '</tbody></table>';
        return $this->layout->render('Service desk', $body, true);
    }

    public function requestDetail(ServiceRequest $r, ?string $error = null): string
    {
        $notice = $error !== null ? '<div class="notice notice--err">' . $this->layout->e($error) . '</div>' : '';
        $transitions = '';
        foreach (ServiceRequest::TRANSITIONS[$r->status] ?? [] as $target) {
            $transitions .= '<form method="post" action="' . $this->u('/admin/requests/' . $r->key . '/transition') . '" class="inline">'
                . '<input type="hidden" name="status" value="' . $this->layout->e($target) . '" />'
                . '<button class="btn btn--ghost" type="submit">→ ' . $this->layout->e(str_replace('_', ' ', $target)) . '</button></form> ';
        }
        if ($transitions === '') {
            $transitions = '<span class="muted">No further transitions.</span>';
        }

        $body = '<a class="muted" href="' . $this->u('/admin/requests') . '">← Service desk</a>'
            . '<h1>' . $this->layout->e($r->key) . '</h1>' . $notice
            . '<div class="meta">' . $this->statusBadge($r->status)
            . '<span class="tag">' . $this->layout->e($r->type) . '</span>'
            . '<span class="tag">' . $this->layout->e($r->priority) . '</span></div>'
            . '<h2>' . $this->layout->e($r->summary) . '</h2>'
            . '<p>' . nl2br($this->layout->e($r->description)) . '</p>'
            . '<dl class="facts"><dt>Requester</dt><dd>' . $this->layout->e($r->requester) . '</dd>'
            . '<dt>Created</dt><dd>' . $this->layout->e((string) $r->createdAt) . '</dd></dl>'
            . '<h2>Workflow</h2><div class="actions">' . $transitions . '</div>'
            . '<h2>Assign</h2><form class="form form--inline" method="post" action="' . $this->u('/admin/requests/' . $r->key . '/assign') . '">'
            . '<input name="assignee" placeholder="agent@example.com" value="' . $this->v($r->assignee) . '" />'
            . '<button class="btn" type="submit">Assign</button></form>';
        return $this->layout->render($r->key, $body, true);
    }

    // ---- helpers --------------------------------------------------------

    private function stat(int $value, string $label): string
    {
        return '<article class="card"><h2>' . $value . '</h2><p>' . $this->layout->e($label) . '</p></article>';
    }

    private function field(string $label, string $control): string
    {
        return '<label class="field"><span>' . $this->layout->e($label) . '</span>' . $control . '</label>';
    }

    private function formButton(string $path, string $label, bool $danger = false): string
    {
        $cls = $danger ? ' class="link-danger"' : '';
        $confirm = $danger ? ' onsubmit="return confirm(\'Are you sure?\')"' : '';
        return '<form method="post" action="' . $this->u($path) . '" class="inline"' . $confirm . '>'
            . '<button type="submit"' . $cls . '>' . $this->layout->e($label) . '</button></form>';
    }

    private function statusBadge(string $status): string
    {
        return '<span class="badge status-' . $this->layout->e($status) . '">'
            . $this->layout->e(str_replace('_', ' ', $status)) . '</span>';
    }

    private function u(string $path): string
    {
        return $this->layout->e($this->layout->url($path));
    }

    private function v(?string $value): string
    {
        return $this->layout->e((string) ($value ?? ''));
    }
}
