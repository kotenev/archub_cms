<?php

declare(strict_types=1);

namespace ArcHub\OloPlugin\Renderer;

use ArcHub\OloPlugin\Application\TaskService;

final readonly class TaskRenderer
{
    public function __construct(private TaskService $tasks)
    {
    }

    public function dashboard(): string
    {
        $overview = $this->tasks->overview();

        $stats = '<section class="grid">'
            . $this->stat($overview['active_total'], 'Active tasks')
            . $this->stat($overview['due_today_total'], 'Due today')
            . $this->stat($overview['overdue_total'], 'Overdue')
            . $this->stat($overview['projects_total'], 'Projects')
            . '</section>';

        $body = '<div class="toolbar"><div><h1>OurLifeOrganized</h1>'
            . '<p class="muted">' . $this->e($overview['tagline']) . '</p></div>'
            . '<input class="search" placeholder="Filter tasks" oninput="filterCards(this)" /></div>'
            . $stats
            . '<h2>To-Do — by computed priority</h2>'
            . $this->taskList($this->tasks->todo())
            . '<h2>Project outline</h2>'
            . '<div class="outline">' . $this->tree($this->tasks->outline()) . '</div>';

        return $this->shell($body);
    }

    public function view(string $view, array $items): string
    {
        $titles = [
            'todo' => 'To-Do (computed priority)',
            'next-actions' => 'Next Actions',
            'inbox' => 'Inbox',
            'today' => 'Today',
            'overdue' => 'Overdue',
            'starred' => 'Starred',
        ];
        $title = $titles[$view] ?? ucfirst($view);
        $body = '<div class="toolbar"><div><h1>' . $this->e($title) . '</h1>'
            . '<p class="muted">' . count($items) . ' task(s).</p></div></div>'
            . $this->taskList($items);

        return $this->shell($body);
    }

    public function contextView(string $key): string
    {
        $items = $this->tasks->tasksInContext($key);
        $body = '<div class="toolbar"><div><h1>@' . $this->e($key) . '</h1>'
            . '<p class="muted">GTD context — ' . count($items) . ' active task(s).</p></div></div>'
            . $this->taskList($items);

        return $this->shell($body);
    }

    public function task(array $task): string
    {
        $priority = $task['priority'];
        $meta = '<div class="meta">'
            . $this->stars($priority['stars'])
            . '<span class="badge ' . $this->dueClass($priority['due_state']) . '">' . $this->e($this->dueLabel($priority['due_state'], $priority['days_to_due'])) . '</span>'
            . '<span class="badge">' . $this->e($task['todo'] ? 'to-do' : 'project') . '</span>'
            . '<span class="muted">importance ' . (int) $task['importance'] . ' · urgency ' . (int) $task['urgency'] . '</span>'
            . '</div>';

        $facts = '<dl class="facts">';
        $facts .= $this->fact('Status', $task['status']);
        $facts .= $this->fact('Computed score', (string) $priority['score']);
        $facts .= $this->fact('Contexts', $task['contexts'] === [] ? '—' : implode(', ', array_map(static fn ($c) => '@' . $c, $task['contexts'])));
        $facts .= $this->fact('Start', $task['start_at'] ?? '—');
        $facts .= $this->fact('Due', $task['due_at'] ?? '—');
        $facts .= $this->fact('Reminder', $task['reminder_at'] ?? '—');
        if ($task['recurrence_human'] !== null) {
            $facts .= $this->fact('Recurrence', $task['recurrence_human']);
        }
        $facts .= '</dl>';

        $children = '';
        if (!empty($task['children'])) {
            $children = '<h2>Sub-tasks</h2>' . $this->taskList($task['children']);
        }

        $recurrence = '';
        if ($task['recurrence_human'] !== null) {
            $preview = $this->tasks->recurrencePreview($task['id']);
            if ($preview !== null && !empty($preview['occurrences'])) {
                $occ = implode('', array_map(fn ($o) => '<li>' . $this->e($o) . '</li>', $preview['occurrences']));
                $recurrence = '<h2>Next occurrences</h2><ul class="occurrences">' . $occ . '</ul>';
            }
        }

        $body = '<article class="page"><a class="muted" href="/">← Dashboard</a>'
            . '<h1>' . $this->e($task['title']) . '</h1>' . $meta
            . '<p class="notes">' . nl2br($this->e($task['notes'])) . '</p>'
            . $facts . $recurrence . $children . '</article>';

        return $this->shell($body);
    }

    // ---- partials --------------------------------------------------------

    private function taskList(array $items): string
    {
        if ($items === []) {
            return '<p class="muted">Nothing here. 🎉</p>';
        }
        $rows = '';
        foreach ($items as $task) {
            $priority = $task['priority'];
            $contexts = implode('', array_map(
                fn ($c) => '<span class="ctx">@' . $this->e($c) . '</span>',
                $task['contexts']
            ));
            $rec = $task['recurrence_human'] !== null
                ? '<span class="ctx ctx--rec">⟳ ' . $this->e($task['recurrence_human']) . '</span>'
                : '';
            $star = $task['starred'] ? '<span class="flag">★</span>' : '';
            $rows .= '<article class="task" data-search-card>'
                . '<div class="task__main">'
                . $this->stars($priority['stars'])
                . '<a class="task__title" href="/tasks/' . $this->e($task['id']) . '">' . $this->e($task['title']) . '</a>'
                . $star . '</div>'
                . '<div class="task__meta">'
                . '<span class="badge ' . $this->dueClass($priority['due_state']) . '">' . $this->e($this->dueLabel($priority['due_state'], $priority['days_to_due'])) . '</span>'
                . '<span class="muted">score ' . $priority['score'] . '</span>'
                . $contexts . $rec . '</div></article>';
        }
        return '<section class="tasks">' . $rows . '</section>';
    }

    private function tree(array $nodes): string
    {
        if ($nodes === []) {
            return '';
        }
        $html = '<ul class="tree">';
        foreach ($nodes as $node) {
            $tag = $node['todo'] ? '<span class="leaf">•</span>' : '<span class="folder">▸</span>';
            $done = $node['completed'] ? ' tree__done' : '';
            $badge = '<span class="muted">score ' . $node['priority']['score'] . '</span>';
            $html .= '<li class="tree__item' . $done . '">' . $tag
                . '<a href="/tasks/' . $this->e($node['id']) . '">' . $this->e($node['title']) . '</a> ' . $badge;
            if (!empty($node['children'])) {
                $html .= $this->tree($node['children']);
            }
            $html .= '</li>';
        }
        return $html . '</ul>';
    }

    private function stat(int|string $value, string $label): string
    {
        return '<article class="card"><h2>' . $this->e((string) $value) . '</h2><p>' . $this->e($label) . '</p></article>';
    }

    private function stars(int $count): string
    {
        $count = max(0, min(5, $count));
        return '<span class="stars" title="computed priority">'
            . str_repeat('★', $count) . str_repeat('☆', 5 - $count) . '</span>';
    }

    private function fact(string $label, string $value): string
    {
        return '<dt>' . $this->e($label) . '</dt><dd>' . $this->e($value) . '</dd>';
    }

    private function dueClass(string $state): string
    {
        return match ($state) {
            'overdue' => 'due-overdue',
            'due_today' => 'due-today',
            'due_soon' => 'due-soon',
            'done' => 'due-done',
            default => 'due-none',
        };
    }

    private function dueLabel(string $state, ?int $days): string
    {
        return match ($state) {
            'overdue' => 'overdue ' . abs((int) $days) . 'd',
            'due_today' => 'due today',
            'due_soon' => 'due in ' . (int) $days . 'd',
            'upcoming' => 'in ' . (int) $days . 'd',
            'done' => 'done',
            default => 'no due date',
        };
    }

    private function shell(string $body): string
    {
        return '<!doctype html><html lang="en"><head><meta charset="utf-8" /><meta name="viewport" content="width=device-width, initial-scale=1" />'
            . '<title>OurLifeOrganized — ArcHub plugin</title><link rel="stylesheet" href="/assets/olo.css" /><script src="/assets/olo.js" defer></script></head>'
            . '<body><div class="layout"><aside class="sidebar"><div class="brand"><strong>OurLifeOrganized</strong><span>PHP 8.4 / Symfony 8 external module</span></div>'
            . '<nav class="nav">'
            . '<a href="/">Dashboard</a>'
            . '<span class="nav__label">Smart views</span>'
            . '<a href="/view/todo">★ To-Do</a>'
            . '<a href="/view/next-actions">Next Actions</a>'
            . '<a href="/view/inbox">Inbox</a>'
            . '<a href="/view/today">Today</a>'
            . '<a href="/view/overdue">Overdue</a>'
            . '<a href="/view/starred">Starred</a>'
            . '<span class="nav__label">Contexts</span>'
            . $this->contextNav()
            . '<span class="nav__label">API</span>'
            . '<a href="/api/olo/overview">Overview JSON</a>'
            . '<a href="/api/olo/todo">To-Do JSON</a>'
            . '</nav></aside>'
            . '<main class="content">' . $body . '</main></div></body></html>';
    }

    private function contextNav(): string
    {
        $links = '';
        foreach ($this->tasks->contexts() as $context) {
            $links .= '<a href="/context/' . $this->e($context['key']) . '">' . $this->e($context['icon'] . ' ' . $context['name'])
                . ' <span class="pill">' . (int) $context['active_tasks'] . '</span></a>';
        }
        return $links;
    }

    private function e(string $value): string
    {
        return htmlspecialchars($value, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
    }
}
