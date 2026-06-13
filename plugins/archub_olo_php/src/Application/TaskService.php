<?php

declare(strict_types=1);

namespace ArcHub\OloPlugin\Application;

use ArcHub\OloPlugin\Domain\PriorityCalculator;
use ArcHub\OloPlugin\Domain\Recurrence;
use ArcHub\OloPlugin\Domain\Task;
use ArcHub\OloPlugin\Infrastructure\SeedTaskRepository;
use DateTimeImmutable;

/**
 * Read-oriented application service over the OurLifeOrganized outline.
 *
 * Provides the smart "views" that define MyLifeOrganized — the computed
 * priority To-Do list, Today, Overdue, Next Actions, contexts and the project
 * outline — plus operator reports mirroring the OLO `admin-cli` and a
 * recurrence preview mirroring the Temporal recurrence workflow.
 */
final readonly class TaskService
{
    private PriorityCalculator $priority;

    public function __construct(
        private SeedTaskRepository $repository,
        private DateTimeImmutable $now,
    ) {
        $this->priority = new PriorityCalculator($this->now);
    }

    public function overview(): array
    {
        $tasks = $this->repository->tasks();
        $active = array_filter($tasks, static fn (Task $t) => !$t->isCompleted());

        return [
            'product' => 'OurLifeOrganized (OLO)',
            'tagline' => 'GTD outliner with computed star priority, contexts and recurrence.',
            'tasks_total' => count($tasks),
            'active_total' => count($active),
            'completed_total' => count($tasks) - count($active),
            'projects_total' => count(array_filter($tasks, static fn (Task $t) => !$t->todo)),
            'contexts_total' => count($this->repository->contexts()),
            'overdue_total' => count($this->overdue()),
            'due_today_total' => count($this->today()),
            'features' => [
                'task_outline',
                'computed_priority',
                'gtd_contexts',
                'due_and_start_dates',
                'recurrence',
                'reminders',
                'smart_views',
                'operator_reports',
                'event_sourced_audit',
            ],
        ];
    }

    /** Flat list of every task, enriched with computed priority. */
    public function tasks(): array
    {
        return array_map($this->enrich(...), $this->repository->tasks());
    }

    public function task(string $id): ?array
    {
        foreach ($this->repository->tasks() as $task) {
            if ($task->id === $id) {
                return $this->enrich($task) + ['children' => $this->childrenOf($id)];
            }
        }
        return null;
    }

    /** Nested project outline (the MLO tree view). */
    public function outline(): array
    {
        return $this->buildTree(null);
    }

    public function contexts(): array
    {
        $counts = [];
        foreach ($this->repository->tasks() as $task) {
            if ($task->isCompleted()) {
                continue;
            }
            foreach ($task->contexts as $key) {
                $counts[$key] = ($counts[$key] ?? 0) + 1;
            }
        }
        return array_map(
            static fn ($context) => $context->toArray() + ['active_tasks' => $counts[$context->key] ?? 0],
            $this->repository->contexts(),
        );
    }

    public function tasksInContext(string $contextKey): array
    {
        $items = [];
        foreach ($this->repository->tasks() as $task) {
            if (!$task->isCompleted() && in_array($contextKey, $task->contexts, true)) {
                $items[] = $this->enrich($task);
            }
        }
        return $this->byPriority($items);
    }

    /**
     * The flagship MLO "To-Do" list: actionable leaf tasks, ordered by
     * computed priority. Projects and completed tasks are excluded.
     */
    public function todo(): array
    {
        $items = [];
        foreach ($this->repository->tasks() as $task) {
            if ($task->todo && !$task->isCompleted()) {
                $items[] = $this->enrich($task);
            }
        }
        return $this->byPriority($items);
    }

    /** GTD "Next Actions": actionable tasks already started (no future start date). */
    public function nextActions(): array
    {
        $items = [];
        foreach ($this->repository->tasks() as $task) {
            if (!$task->todo || $task->isCompleted()) {
                continue;
            }
            if ($task->startAt !== null && new DateTimeImmutable($task->startAt) > $this->now) {
                continue;
            }
            $items[] = $this->enrich($task);
        }
        return $this->byPriority($items);
    }

    /** Inbox: unfiled active tasks at the root with no context yet. */
    public function inbox(): array
    {
        $items = [];
        foreach ($this->repository->tasks() as $task) {
            if ($task->isRoot() && $task->todo && !$task->isCompleted() && $task->contexts === []) {
                $items[] = $this->enrich($task);
            }
        }
        return $items;
    }

    public function today(): array
    {
        return $this->dueWithin(0);
    }

    /** Active tasks due within the next $days days (inclusive of today). */
    public function dueSoon(int $days = 7): array
    {
        return $this->dueWithin($days);
    }

    public function overdue(): array
    {
        $items = [];
        foreach ($this->repository->tasks() as $task) {
            if ($task->isCompleted() || $task->dueAt === null) {
                continue;
            }
            if (new DateTimeImmutable($task->dueAt) < $this->startOfDay()) {
                $items[] = $this->enrich($task);
            }
        }
        return $this->byPriority($items);
    }

    public function starred(): array
    {
        $items = [];
        foreach ($this->repository->tasks() as $task) {
            if ($task->starred && !$task->isCompleted()) {
                $items[] = $this->enrich($task);
            }
        }
        return $this->byPriority($items);
    }

    /**
     * Operator summary report (mirrors OLO `admin-cli reports summary`):
     * one row per user with active/completed/overdue counts.
     */
    public function summaryReport(): array
    {
        $byUser = [];
        foreach ($this->repository->tasks() as $task) {
            $row = &$byUser[$task->userId];
            $row['user_id'] = $task->userId;
            $row['total'] = ($row['total'] ?? 0) + 1;
            if ($task->isCompleted()) {
                $row['completed'] = ($row['completed'] ?? 0) + 1;
            } else {
                $row['active'] = ($row['active'] ?? 0) + 1;
            }
            unset($row);
        }
        $overdueByUser = [];
        foreach ($this->overdue() as $task) {
            $overdueByUser[$task['user_id']] = ($overdueByUser[$task['user_id']] ?? 0) + 1;
        }
        return array_values(array_map(static function (array $row) use ($overdueByUser) {
            return [
                'user_id' => $row['user_id'],
                'total' => $row['total'] ?? 0,
                'active' => $row['active'] ?? 0,
                'completed' => $row['completed'] ?? 0,
                'overdue' => $overdueByUser[$row['user_id']] ?? 0,
            ];
        }, $byUser));
    }

    /**
     * Preview the next occurrences of a recurring task, mirroring the OLO
     * Temporal recurrence workflow (TaskRecurrenceAdvanced).
     */
    public function recurrencePreview(string $id, int $count = 3): ?array
    {
        foreach ($this->repository->tasks() as $task) {
            if ($task->id !== $id) {
                continue;
            }
            $recurrence = Recurrence::fromArray($task->recurrence);
            if ($recurrence === null || $task->dueAt === null) {
                return ['id' => $id, 'recurring' => false, 'occurrences' => []];
            }
            $occurrences = [];
            $base = new DateTimeImmutable($task->dueAt);
            for ($i = 0; $i < max(1, $count); $i++) {
                $base = $recurrence->next($base);
                $occurrences[] = $base->format(DATE_ATOM);
            }
            return [
                'id' => $id,
                'recurring' => true,
                'rule' => $recurrence->toArray(),
                'human' => $recurrence->humanReadable(),
                'occurrences' => $occurrences,
            ];
        }
        return null;
    }

    public function events(): array
    {
        return $this->repository->events();
    }

    public function search(string $query): array
    {
        $clean = strtolower(trim($query));
        $items = [];
        foreach ($this->repository->tasks() as $task) {
            $haystack = strtolower($task->title . ' ' . $task->notes . ' ' . implode(' ', $task->contexts));
            if ($clean === '' || str_contains($haystack, $clean)) {
                $enriched = $this->enrich($task);
                $items[] = [
                    'id' => $task->id,
                    'title' => $task->title,
                    'excerpt' => substr($task->notes, 0, 160),
                    'status' => $task->status,
                    'priority' => $enriched['priority'],
                    'score' => $clean === '' ? 0.5 : 1.0,
                ];
            }
        }
        return ['query' => $query, 'items' => $items, 'total' => count($items)];
    }

    // ---- internals -------------------------------------------------------

    private function enrich(Task $task): array
    {
        $recurrence = Recurrence::fromArray($task->recurrence);
        return $task->toArray() + [
            'priority' => $this->priority->evaluate($task),
            'recurrence_human' => $recurrence?->humanReadable(),
        ];
    }

    /** @return list<array<string,mixed>> */
    private function childrenOf(string $parentId): array
    {
        $items = [];
        foreach ($this->repository->tasks() as $task) {
            if ($task->parentId === $parentId) {
                $items[] = $this->enrich($task);
            }
        }
        return $items;
    }

    private function buildTree(?string $parentId): array
    {
        $nodes = [];
        foreach ($this->repository->tasks() as $task) {
            if ($task->parentId === $parentId) {
                $nodes[] = $this->enrich($task) + ['children' => $this->buildTree($task->id)];
            }
        }
        return $nodes;
    }

    private function dueWithin(int $days): array
    {
        $start = $this->startOfDay();
        $end = $start->modify('+' . ($days + 1) . ' days');
        $items = [];
        foreach ($this->repository->tasks() as $task) {
            if ($task->isCompleted() || $task->dueAt === null) {
                continue;
            }
            $due = new DateTimeImmutable($task->dueAt);
            if ($due >= $start && $due < $end) {
                $items[] = $this->enrich($task);
            }
        }
        return $this->byPriority($items);
    }

    private function startOfDay(): DateTimeImmutable
    {
        return $this->now->setTime(0, 0);
    }

    /**
     * @param list<array<string,mixed>> $items
     * @return list<array<string,mixed>>
     */
    private function byPriority(array $items): array
    {
        usort($items, static fn ($a, $b) => $b['priority']['score'] <=> $a['priority']['score']);
        return $items;
    }
}
