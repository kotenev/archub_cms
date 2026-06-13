<?php

declare(strict_types=1);

namespace ArcHub\OloPlugin\Infrastructure;

use ArcHub\OloPlugin\Domain\Context;
use ArcHub\OloPlugin\Domain\Task;

/**
 * In-memory seed data for the OurLifeOrganized demo plugin.
 *
 * Tasks form a hierarchical outline (path/depth), exactly like the OLO read
 * model `rm_task`. The event feed mirrors the OLO domain event stream
 * (TaskCreated, TaskMoved, TaskDueAtSet, TaskCompleted, TaskRecurrenceSet,
 * TaskRecurrenceAdvanced) so the audit surface looks like the real platform.
 */
final class SeedTaskRepository
{
    private const USER_ID = 1001;

    /** @return list<Task> */
    public function tasks(): array
    {
        return [
            // Project: Launch ArcHub.ru
            $this->task('t-launch', null, 'Launch ArcHub.ru', false, 80, 60, false, [], null, null,
                'Top-level outcome grouping the public launch workstreams.'),
            $this->task('t-launch-content', 't-launch', 'Finalise landing content', true, 70, 80, true,
                ['computer'], '2026-06-10T09:00:00Z', '2026-06-12T18:00:00Z',
                'Review hero copy, pricing table and call-to-action.'),
            $this->task('t-launch-seo', 't-launch', 'SEO & metadata pass', true, 55, 40, false,
                ['computer'], null, '2026-06-20T18:00:00Z', 'Open graph tags, sitemap, canonical URLs.'),
            $this->task('t-launch-go', 't-launch', 'Flip production DNS', true, 90, 95, true,
                ['computer'], null, '2026-06-13T08:00:00Z', 'Final go/no-go and DNS cutover.'),

            // Project: Home
            $this->task('t-home', null, 'Home', false, 40, 30, false, [], null, null,
                'Everyday household and errands bucket.'),
            $this->task('t-home-rent', 't-home', 'Pay rent', true, 85, 70, false,
                ['calls'], null, '2026-07-01T12:00:00Z', 'Recurring monthly obligation.',
                ['rrule' => 'FREQ=MONTHLY;INTERVAL=1', 'mode' => 'FROM_DUE']),
            $this->task('t-home-plants', 't-home', 'Water the balcony plants', true, 25, 35, false,
                ['errands'], null, '2026-06-13T19:00:00Z', 'Floating habit, restarts after completion.',
                ['rrule' => 'FREQ=DAILY;INTERVAL=3', 'mode' => 'FROM_COMPLETE']),
            $this->task('t-home-groceries', 't-home', 'Weekly groceries', true, 35, 50, false,
                ['errands'], null, '2026-06-15T11:00:00Z', 'Milk, vegetables, coffee.',
                ['rrule' => 'FREQ=WEEKLY;INTERVAL=1', 'mode' => 'FROM_DUE']),

            // Project: Learning (with a completed leaf)
            $this->task('t-learn', null, 'Learning', false, 50, 20, false, [], null, null,
                'Personal development outline.'),
            $this->task('t-learn-rust', 't-learn', 'Finish Rust async chapter', true, 45, 25, false,
                ['computer'], null, '2026-06-25T20:00:00Z', 'Chapters 8–9 of the async book.'),
            $this->completedTask('t-learn-cqrs', 't-learn', 'Read CQRS primer', true, 40, 10,
                ['computer'], '2026-06-09T21:00:00Z', 'Done — notes captured.'),

            // Inbox (unfiled next actions)
            $this->task('t-inbox-call', null, 'Call dentist to reschedule', true, 60, 75, true,
                ['calls'], null, '2026-06-13T16:00:00Z', 'Captured to inbox, not yet filed into a project.'),
            $this->task('t-inbox-idea', null, 'Idea: weekend hiking trip', true, 20, 10, false,
                [], null, null, 'Someday/maybe item sitting in the inbox.'),
        ];
    }

    public function task(
        string $id,
        ?string $parentId,
        string $title,
        bool $todo,
        int $importance,
        int $urgency,
        bool $starred,
        array $contexts,
        ?string $startAt,
        ?string $dueAt,
        string $notes,
        ?array $recurrence = null,
    ): Task {
        [$path, $depth] = $this->placement($parentId, $id);

        return new Task(
            $id,
            self::USER_ID,
            $parentId,
            $path,
            $depth,
            $title,
            $notes,
            Task::STATUS_ACTIVE,
            $todo,
            $importance,
            $urgency,
            $starred,
            $contexts,
            $startAt,
            $dueAt,
            $dueAt,
            null,
            $recurrence,
            '2026-06-08T08:00:00Z',
            '2026-06-12T08:00:00Z',
        );
    }

    private function completedTask(
        string $id,
        ?string $parentId,
        string $title,
        bool $todo,
        int $importance,
        int $urgency,
        array $contexts,
        string $completedAt,
        string $notes,
    ): Task {
        [$path, $depth] = $this->placement($parentId, $id);

        return new Task(
            $id,
            self::USER_ID,
            $parentId,
            $path,
            $depth,
            $title,
            $notes,
            Task::STATUS_COMPLETED,
            $todo,
            $importance,
            $urgency,
            false,
            $contexts,
            null,
            null,
            null,
            $completedAt,
            null,
            '2026-06-05T08:00:00Z',
            $completedAt,
        );
    }

    /**
     * Materialised-path placement mirroring the OLO projection:
     * roots get "/" + depth 0; children get "<parent_path><id>/".
     *
     * @return array{0:string,1:int}
     */
    private function placement(?string $parentId, string $id): array
    {
        if ($parentId === null) {
            return ['/', 0];
        }
        // Single-level demo data: parent path is "/<parentId>/".
        $parentPath = '/' . $parentId . '/';

        return [$parentPath . $id . '/', substr_count($parentPath, '/') - 1];
    }

    /** @return list<Context> */
    public function contexts(): array
    {
        return [
            new Context('calls', '@Calls', '📞', '#2563eb'),
            new Context('errands', '@Errands', '🛒', '#d97706'),
            new Context('computer', '@Computer', '💻', '#0f766e'),
            new Context('waiting', '@Waiting', '⏳', '#9333ea'),
        ];
    }

    /**
     * Event-sourced audit feed mirroring OLO's domain event types.
     *
     * @return list<array<string,string>>
     */
    public function events(): array
    {
        return [
            $this->event('TaskCreated', 't-launch', 'Created project "Launch ArcHub.ru"', '2026-06-08T08:00:00Z', 1),
            $this->event('TaskMoved', 't-launch-content', 'Filed "Finalise landing content" under Launch', '2026-06-08T08:05:00Z', 2),
            $this->event('TaskDueAtSet', 't-launch-go', 'Due date set to 2026-06-13 for "Flip production DNS"', '2026-06-09T10:00:00Z', 2),
            $this->event('TaskRecurrenceSet', 't-home-rent', 'Recurrence FREQ=MONTHLY set on "Pay rent" (FROM_DUE)', '2026-06-09T11:30:00Z', 3),
            $this->event('TaskRecurrenceSet', 't-home-plants', 'Recurrence FREQ=DAILY;INTERVAL=3 on "Water the balcony plants" (FROM_COMPLETE)', '2026-06-09T11:35:00Z', 2),
            $this->event('TaskCompleted', 't-learn-cqrs', 'Completed "Read CQRS primer"', '2026-06-09T21:00:00Z', 4),
            $this->event('TaskRecurrenceAdvanced', 't-home-plants', 'Advanced "Water the balcony plants" to next occurrence', '2026-06-10T19:00:00Z', 3),
        ];
    }

    /** @return array<string,string> */
    private function event(string $type, string $streamId, string $summary, string $at, int $version): array
    {
        return [
            'type' => $type,
            'stream_id' => $streamId,
            'stream_type' => 'Task',
            'summary' => $summary,
            'occurred_at' => $at,
            'stream_version' => (string) $version,
        ];
    }
}
